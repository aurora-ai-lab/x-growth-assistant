"""Rule-based chat router for the local website.

The website does not ship an LLM. This router recognises the three jobs
the assistant does (growth advice, post review, limit-check explanation),
refuses the things it must not do, and answers from the same rules as
PROMPT.md and docs/. To get free-form answers, load PROMPT.md as the
system prompt in an LLM of your choice.
"""

import re

import limit_check
import post_review

GREETING = (
    "Hi! I'm your X traffic and content compliance assistant. I can help with three things:\n"
    "1. Growth: type \"how do I grow\" for this week's 3 actions.\n"
    "2. Post review: type \"review: <your draft post>\".\n"
    "3. Limit check: type \"check @yourhandle\" or use the form on the right.\n"
    "I never ask for your password, and I don't buy followers, automate spam or bypass bans."
)

REFUSE_RE = re.compile(
    r"\b(buy|purchase|get cheap) (followers|likes|retweets|reposts|views|engagement)\b"
    r"|\b(hack|crack|steal|take over|hijack)\b.{0,30}\b(account|password)\b"
    r"|\b(ban evasion|evade (a |the )?ban|bypass (a |the )?(ban|suspension)|unsuspend trick)\b"
    r"|\b(bot farm|mass (follow|dm|reply) bot|auto[- ]?(follow|like|reply) (bot|tool|script))\b"
    r"|\b(fake (accounts|engagement|reviews)|sockpuppets?)\b"
    r"|\b(scrape|scraping)\b.{0,30}\b(without|bypass|around)\b.{0,20}\b(api|limit)",
    re.I,
)
PASSWORD_RE = re.compile(r"\b(password|passcode|2fa code|backup code)\b\s*[:=]?\s*\S+", re.I)
REVIEW_RE = re.compile(r"^\s*(review|check (this|my) post|can i post( this)?|is this ok|duyet)\s*[:\-]?\s*", re.I)
LIMIT_RE = re.compile(r"\b(shadow ?ban\w*|limited|restricted|throttled|deboosted|limit check|visibility)\b", re.I)
HANDLE_RE = re.compile(r"(?:^|\s)@([A-Za-z0-9_]{1,15})\b|\bcheck\s+([A-Za-z0-9_]{1,15})\b", re.I)
GROWTH_RE = re.compile(r"\b(grow|growth|traffic|followers|reach|impressions|engagement|audience)\b", re.I)
HELLO_RE = re.compile(r"^\s*(hi|hello|hey|help|start|menu|xin chao|chao)\b", re.I)

THIS_WEEK = (
    "Diagnosis: without your numbers I'll assume a small account (<1k followers) with uneven reach.\n"
    "3 things this week:\n"
    "1. Fix the profile: clear avatar, a bio that says who you help and how, one CTA link, and pin your best post.\n"
    "2. Publish 5 original posts and 1 thread (hook, proof, action; link at the end or in a reply).\n"
    "3. Every day, leave 5 thoughtful replies on larger accounts in your niche within 30-60 minutes of their post.\n"
    "Expectation: track profile visits per 1k impressions and follows per 100 profile visits; judge after 7 days, not daily.\n"
    "Full plan: docs/growth-playbook.md."
)


def respond(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("'message' is required and must be a non-empty string.")
    message = message.strip()[:5000]

    if PASSWORD_RE.search(message):
        return {
            "intent": "password_warning",
            "reply": (
                "Please don't share passwords or 2FA codes here, and change that password now if it was real. "
                "This assistant never needs them. Account access, if ever needed, goes through X's official OAuth only."
            ),
        }

    if REFUSE_RE.search(message):
        return {
            "intent": "refused",
            "reply": (
                "I can't help with that: bought engagement, account takeover, ban evasion and automation "
                "spam break X's rules and put the account at risk.\n"
                "What I can do instead: a 7-day organic growth plan (type \"how do I grow\"), or a review of "
                "your next post (type \"review: <draft>\")."
            ),
        }

    review_match = REVIEW_RE.match(message)
    if review_match:
        draft = message[review_match.end():].strip().strip('"').strip()
        if not draft:
            return {"intent": "post_review", "reply": "Paste the draft after \"review:\", e.g. review: My new thread on..."}
        result = post_review.review(draft)
        lines = ["Verdict: {} (risk: {})".format(result["verdict_label"], result["risk"])]
        lines.append("Why:")
        lines += ["- " + r for r in result["reasons"]]
        if result["suggestions"]:
            lines.append("How to fix:")
            lines += ["- " + s for s in result["suggestions"]]
        lines.append(result["disclaimer"])
        return {"intent": "post_review", "reply": "\n".join(lines), "data": result}

    handle_match = HANDLE_RE.search(message)
    if LIMIT_RE.search(message) or (handle_match and message.lower().startswith("check")):
        if not handle_match:
            return {
                "intent": "limit_check",
                "reply": "Which account? Type \"check @yourhandle\", or fill in the limit-check form for a fuller result.",
            }
        handle = handle_match.group(1) or handle_match.group(2)
        result = limit_check.evaluate(handle)
        lines = [
            "Status: {} (confidence {}).".format(result["status"], result["confidence"]),
            result["summary"],
            "Manual checks (about 10 minutes):",
        ]
        lines += ["{}. {}".format(i + 1, c) for i, c in enumerate(result["manual_checks"])]
        return {"intent": "limit_check", "reply": "\n".join(lines), "data": result}

    if GROWTH_RE.search(message):
        return {"intent": "growth", "reply": THIS_WEEK}

    if HELLO_RE.match(message):
        return {"intent": "greeting", "reply": GREETING}

    return {
        "intent": "fallback",
        "reply": (
            "I didn't recognise that request. This local assistant is rule-based and covers:\n"
            "- \"how do I grow\" (this week's 3 actions)\n"
            "- \"review: <draft post>\" (allowed / revise / do not post)\n"
            "- \"check @handle\" (visibility-limit check)\n"
            "For open-ended questions, load PROMPT.md into an LLM as its system prompt."
        ),
    }

