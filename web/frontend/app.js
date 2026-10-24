// Frontend for the local X Growth Assistant.
// It only renders JSON returned by the backend. It never decides a status itself.

(function () {
  "use strict";

  const KNOWN_STATUSES = ["normal", "suspected", "limited", "unknown"];
  const STATUS_TEXT = {
    normal: "Normal: no restriction indicated",
    suspected: "Suspected: possible reduced visibility",
    limited: "Limited: restriction reported",
    unknown: "Unknown: cannot determine",
  };
  const GREETING =
    "Hi! I'm your X traffic and content compliance assistant. I can help with:\n" +
    "1. Growth: type \"how do I grow\" for this week's 3 actions.\n" +
    "2. Post review: type \"review: <your draft post>\".\n" +
    "3. Limit check: type \"check @yourhandle\" or use the form.\n" +
    "I never ask for your password.";

  const $ = (id) => document.getElementById(id);

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    });
    (children || []).forEach((c) => node.append(c instanceof Node ? c : document.createTextNode(String(c))));
    return node;
  }

  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    };
    const res = await fetch(path, opts);
    let data;
    try {
      data = await res.json();
    } catch (e) {
      throw new Error("Server returned a non-JSON response (HTTP " + res.status + ").");
    }
    if (!res.ok) {
      const msg = data && data.error ? data.error.message : "HTTP " + res.status;
      throw new Error(msg);
    }
    return data;
  }

  // ---- chat -------------------------------------------------------------
  function addMessage(text, who) {
    const log = $("chat-log");
    log.append(el("div", { class: "msg " + who }, [text]));
    log.scrollTop = log.scrollHeight;
  }

  $("chat-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const input = $("chat-input");
    const message = input.value.trim();
    if (!message) return;
    addMessage(message, "user");
    input.value = "";
    try {
      const data = await api("/api/chat", { message });
      addMessage(data.reply, "bot");
    } catch (err) {
      addMessage("Error: " + err.message, "bot");
    }
  });

  // ---- limit-check form -----------------------------------------------
  async function buildBoolFields() {
    const grid = $("bool-fields");
    try {
      const schema = await api("/api/limit-check/schema");
      Object.entries(schema.evidence_fields)
        .filter(([, f]) => f.type.startsWith("boolean"))
        .forEach(([key, f]) => {
          const select = el("select", { "data-bool": key }, [
            el("option", { value: "" }, ["not checked"]),
            el("option", { value: "true" }, ["yes"]),
            el("option", { value: "false" }, ["no"]),
          ]);
          grid.append(el("label", {}, [f.description, select]));
        });
    } catch (err) {
      grid.append(el("p", { class: "error" }, ["Could not load fields: " + err.message]));
    }
  }

  function collectEvidence() {
    const evidence = {};
    document.querySelectorAll("[data-bool]").forEach((s) => {
      if (s.value !== "") evidence[s.dataset.bool] = s.value === "true";
    });
    document.querySelectorAll("[data-int]").forEach((i) => {
      if (i.value !== "") evidence[i.dataset.int] = parseInt(i.value, 10);
    });
    const notice = $("notice").value.trim();
    if (notice) evidence.official_notice_text = notice;
    const raw = $("evidence-json").value.trim();
    if (raw) {
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (e) {
        throw new Error("Evidence JSON is not valid JSON.");
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Evidence JSON must be an object.");
      }
      // Accept either the evidence object itself or a full request body.
      Object.assign(evidence, parsed.evidence && typeof parsed.evidence === "object" ? parsed.evidence : parsed);
    }
    return evidence;
  }

  function list(tag, items) {
    return el(tag, {}, items.map((t) => el("li", {}, [t])));
  }

  function renderResult(data) {
    const box = $("limit-result");
    box.hidden = false;
    box.replaceChildren();
    const status = KNOWN_STATUSES.includes(data.status) ? data.status : null;
    if (!status) {
      box.className = "result";
      box.append(el("p", { class: "error" }, ["Unexpected response from the server (no valid status)."]));
      return;
    }
    box.className = "result status-" + status;
    box.append(
      el("h3", {}, [el("span", { class: "badge " + status }, [status]), " ", STATUS_TEXT[status]]),
      el("p", { class: "meta" }, [
        "@" + data.handle + " · confidence " + data.confidence + " · checked " + data.checked_at +
        " · evidence: " + data.evidence_source,
      ]),
      el("p", {}, [data.summary]),
    );

    box.append(el("h4", {}, ["Evidence (signals)"]));
    box.append(el("ul", {}, data.signals.map((s) => {
      const mark = s.observed === true ? "● observed" : s.observed === false ? "○ not observed" : "– n/a";
      const cls = s.observed === true ? "sig-on" : s.observed === false ? "sig-off" : "sig-na";
      return el("li", {}, [
        el("span", { class: cls }, [mark]), " ", s.label + " [" + s.weight + ", " + s.source + "]: " + s.detail,
      ]);
    })));

    if (data.likely_causes.length) {
      box.append(el("h4", {}, ["Likely causes"]), list("ul", data.likely_causes));
    }
    box.append(el("h4", {}, ["48-hour action list"]), list("ol", data.action_48h));
    box.append(el("p", {}, ["Recheck in " + data.recheck_interval_hours + " hours."]));
    if (status === "unknown") {
      box.append(el("h4", {}, ["Manual checks"]), list("ol", data.manual_checks));
    }
    if (data.warnings.length) {
      box.append(el("h4", {}, ["Warnings"]), list("ul", data.warnings));
    }
    box.append(el("p", { class: "meta" }, [data.disclaimer]));
  }

  $("limit-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const button = ev.target.querySelector("button[type=submit]");
    const box = $("limit-result");
    let body;
    try {
      body = {
        handle: $("handle").value,
        evidence: collectEvidence(),
        description: $("description").value,
      };
    } catch (err) {
      box.hidden = false;
      box.className = "result";
      box.replaceChildren(el("p", { class: "error" }, [err.message]));
      return;
    }
    button.disabled = true;
    try {
      renderResult(await api("/api/limit-check", body));
    } catch (err) {
      box.hidden = false;
      box.className = "result";
      box.replaceChildren(el("p", { class: "error" }, ["Error: " + err.message]));
    } finally {
      button.disabled = false;
    }
  });

  // ---- startup ----------------------------------------------------------
  addMessage(GREETING, "bot");
  buildBoolFields();
  api("/api/health")
    .then((h) => { $("api-state").textContent = "API v" + h.version + " · X API: " + h.x_api; })
    .catch(() => { $("api-state").textContent = "API offline"; });
})();

