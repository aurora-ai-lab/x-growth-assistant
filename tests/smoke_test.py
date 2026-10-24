"""Smoke test against a RUNNING server.

    python3 web/backend/server.py &          # terminal 1
    python3 tests/smoke_test.py              # terminal 2
    python3 tests/smoke_test.py http://127.0.0.1:9000

Calls the documented cases, checks the JSON shape and prints each response.
Exits with code 1 if any check fails.
"""

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
REQUIRED = {"status", "signals", "checked_at", "confidence"}
STATUSES = {"normal", "suspected", "limited", "unknown"}


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def limit_ok(code, data, expect_status):
    return (code == 200 and REQUIRED <= set(data) and data["status"] in STATUSES
            and data["status"] == expect_status and isinstance(data["signals"], list))


CASES = [
    ("1. normal handle, no evidence", "/api/limit-check?handle=jack", None,
     lambda c, d: limit_ok(c, d, "unknown")),
    ("2. well-formed handle that may not exist", "/api/limit-check?handle=zz_nosuchuser99", None,
     lambda c, d: limit_ok(c, d, "unknown")
     and any(s["id"] == "handle_existence_unverified" for s in d["signals"])),
    ("3. missing parameter", "/api/limit-check", None,
     lambda c, d: c == 400 and d["error"]["code"] == "missing_handle"),
    ("4. malformed handle", "/api/limit-check?handle=bad-handle!", None,
     lambda c, d: c == 400 and d["error"]["code"] == "invalid_handle"),
    ("5. user evidence: official notice", "/api/limit-check",
     {"handle": "@jack", "evidence": {"action_blocked_notice": True}},
     lambda c, d: limit_ok(c, d, "limited") and d["confidence"] <= 0.6),
    ("6. user evidence: two visibility signals", "/api/limit-check",
     {"handle": "jack", "evidence": {"followers_only_visibility": True, "search_visible_logged_out": False}},
     lambda c, d: limit_ok(c, d, "suspected")),
    ("7. post review: scam pattern", "/api/post-review",
     {"text": "Guaranteed returns! Send 1 ETH and get 2 back"},
     lambda c, d: c == 200 and d["verdict"] == "do_not_post"),
    ("8. health", "/api/health", None, lambda c, d: c == 200 and d["ok"] is True),
]


def main():
    failed = 0
    for name, path, body, check in CASES:
        try:
            code, data = call(path, body)
            ok = check(code, data)
        except Exception as exc:  # noqa: BLE001 - report any failure
            code, data, ok = None, {"exception": str(exc)}, False
        failed += 0 if ok else 1
        print("=" * 72)
        print("{} {}  ->  HTTP {}  [{}]".format(
            "POST" if body is not None else "GET", path, code, "PASS" if ok else "FAIL"))
        print("# " + name)
        if isinstance(data, dict) and "signals" in data:
            brief = {k: data[k] for k in ("status", "confidence", "checked_at", "handle", "summary")}
            brief["signals"] = [{k: s[k] for k in ("id", "source", "observed", "weight")} for s in data["signals"]]
            print(json.dumps(brief, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1200])
    print("=" * 72)
    print("{} passed, {} failed".format(len(CASES) - failed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

