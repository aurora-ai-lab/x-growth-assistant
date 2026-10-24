"""Visibility-limit ("shadowban") check logic.

Honesty rules this module enforces:
  * Without verifiable data the status is "unknown". There is no default
    "normal".
  * The X API integration is a stub (see xapi.py), so the only evidence
    available is what the user reports. Every signal records its source,
    and confidence is capped because user reports cannot be verified.
  * Free-text descriptions (for example a screenshot described in words)
    are only used to fill evidence fields the user left empty, and every
    match is listed as its own signal so the user can see why.
"""

import re
from datetime import datetime, timezone

import xapi

STATUSES = ("normal", "suspected", "limited", "unknown")

HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")

# Confidence ceilings. User-reported evidence is never treated as certain.
MAX_CONFIDENCE_USER_REPORTED = 0.6
CONFIDENCE_UNKNOWN = 0.1

# Evidence fields accepted from the user. Value types:
#   bool -> True (observed), False (checked, not observed), None (not checked)
#   int  -> non-negative count, None if unknown
BOOL_FIELDS = {
    "action_blocked_notice": "X showed an 'action blocked' / 'temporarily restricted' notice",
    "captcha_or_temporary_lock": "X asked for a captcha, phone verification or locked the account",
    "rate_limit_notice": "X showed a rate-limit message ('you are over the limit', 'try again later')",
    "button_errors": "Like / repost / follow buttons fail or revert",
    "followers_only_visibility": "Posts or replies are visible to followers only (checked from a logged-out or non-following account)",
    "search_visible_logged_out": "The account appears in search when logged out or from a non-following account",
    "replies_hidden_behind_show_more": "Replies are collapsed under 'Show more replies' / 'Show probable spam'",
}
INT_FIELDS = {
    "impressions_last_7d": "Total impressions in the last 7 days",
    "avg_weekly_impressions_prev_4w": "Average weekly impressions over the 4 weeks before that",
    "posts_last_7d": "Number of posts and replies published in the last 7 days",
    "followers": "Follower count",
}
TEXT_FIELDS = {
    "official_notice_text": "Exact text of any notice X showed (copy it, do not paraphrase)",
}

# Free-text patterns -> evidence field they support.
# English plus a few common Vietnamese phrases (accents stripped and kept).
TEXT_PATTERNS = [
    ("action_blocked_notice", re.compile(
        r"action blocked|temporarily (restricted|limited)|some of your account features are"
        r"|looks like it might be automated|your account (has been|is) (restricted|limited)"
        r"|bị hạn chế|bi han che|bị chặn thao tác|bi chan thao tac", re.I)),
    ("captcha_or_temporary_lock", re.compile(
        r"captcha|arkose|verify your phone|phone verification|account (is )?locked"
        r"|we've temporarily limited|unlock your account|bị khóa|bi khoa|xác minh số điện thoại", re.I)),
    ("rate_limit_notice", re.compile(
        r"rate limit|over the (daily )?limit|try again later|you are over|too many requests"
        r"|vượt giới hạn|vuot gioi han", re.I)),
    ("button_errors", re.compile(
        r"(like|follow|repost|retweet)s? (buttons? )?(\w+ )?(doesn't|does not|won't|fails?|reverts?|undoes|keeps undoing)"
        r"|nút .* (lỗi|không hoạt động)", re.I)),
    ("followers_only_visibility", re.compile(
        r"only (my )?followers (can )?see|followers only|not visible (when )?logged out"
        r"|chỉ follower|chi follower", re.I)),
    ("replies_hidden_behind_show_more", re.compile(
        r"show (more|additional) replies|probable spam|replies (are )?hidden", re.I)),
]

# Signal weights used to decide the status.
STRONG = ("action_blocked_notice", "captcha_or_temporary_lock")
MODERATE = (
    "followers_only_visibility",
    "search_not_visible_logged_out",
    "impressions_near_zero",
    "replies_hidden_behind_show_more",
    "rate_limit_notice",
)
WEAK = ("button_errors",)

CORE_NEGATIVE_CHECKS = ("followers_only_visibility", "search_visible_logged_out")

MANUAL_CHECKS = [
    "Open a private/incognito browser window (logged out) and visit x.com/<handle>. Note whether the profile and latest posts load.",
    "From a second account that does NOT follow you, search for your exact @handle and for a distinctive phrase from your latest post. Note whether you appear in 'Top' and 'Latest'.",
    "From that same account, open a recent reply of yours under someone else's post. Note whether it is shown normally or collapsed under 'Show more replies' / 'Show probable spam'.",
    "Write down impressions for the last 7 days, the average week of the 4 weeks before, and how many posts and replies you published. Account analytics needs X Premium; without it, add up the view counts shown under each post.",
    "Check Notifications and Settings > Your account for any notice from X. Copy the exact wording; do not paraphrase.",
    "Try one normal action (like a post from a friend). Note whether it fails, reverts, or shows a rate-limit or captcha prompt.",
    "Paste the results into the form (or as JSON) and run the check again.",
]

CAUSES = {
    "action_blocked_notice": "Activity pattern that looks automated: bursts of follows, likes, replies or DMs in a short time.",
    "captcha_or_temporary_lock": "Security or automation check triggered: new device or IP, third-party automation tool, or a burst of actions.",
    "rate_limit_notice": "Daily action or reading limits reached. Usually temporary and not a visibility penalty.",
    "button_errors": "Often a client or network bug; can also accompany a temporary action restriction.",
    "followers_only_visibility": "Possible reply or search de-ranking after reports, repeated identical replies, or many links.",
    "search_not_visible_logged_out": "Possible search suggestion/search ranking restriction. New or recently renamed accounts can also be missing from search for a while.",
    "impressions_near_zero": "Reach dropped sharply. Check content changes and posting frequency before assuming a penalty.",
    "replies_hidden_behind_show_more": "Replies ranked as low quality or probable spam: repeated text, links in replies, many mentions, low account history.",
}

ACTIONS = {
    "limited": [
        "Stop all automation tools and third-party apps with write access (Settings > Security and account access > Apps and sessions).",
        "Complete any captcha or phone verification X asks for, from your usual device and network.",
        "Pause follows, mass likes and DMs for 48 hours. Post at most 1-2 original posts per day.",
        "Read the exact notice and follow its instructions. If you believe it is a mistake, use X's official appeal form (help.x.com).",
        "Remove or edit recent posts that repeat the same text or links.",
    ],
    "suspected": [
        "Pause bulk actions (follow/unfollow, repeated replies, many links) for 48 hours.",
        "Publish 1-2 original posts per day without external links and without mass mentions.",
        "Repeat the logged-out and second-account checks after 24 hours and compare.",
        "Compare impressions with your posting frequency; fewer posts explain lower reach.",
    ],
    "normal": [
        "No visibility restriction indicated by the checks you reported. Focus on content quality.",
        "Keep weekly metrics (impressions, profile visits, follows) to spot sudden changes early.",
    ],
    "unknown": [
        "Run the manual checks listed below (about 10 minutes).",
        "Do not change your behaviour drastically based on a guess.",
        "Paste the results into the form and re-run the check.",
    ],
}

RECHECK_HOURS = {"limited": 48, "suspected": 24, "normal": 168, "unknown": 24}

DISCLAIMER = (
    "This tool cannot see X's internal moderation state. Results are based on "
    "the evidence provided and may be wrong. Official notices from X are the "
    "authority."
)


class ValidationError(ValueError):
    """Raised for malformed input. The server turns it into HTTP 400."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def normalize_handle(raw):
    if raw is None:
        raise ValidationError("missing_handle", "Parameter 'handle' is required, e.g. ?handle=jack")
    if not isinstance(raw, str):
        raise ValidationError("invalid_handle", "'handle' must be a string.")
    handle = raw.strip()
    # Accept profile URLs and a leading @ for convenience.
    handle = re.sub(r"^https?://(www\.)?(x|twitter)\.com/", "", handle, flags=re.I)
    handle = handle.lstrip("@").split("/")[0].split("?")[0]
    if not handle:
        raise ValidationError("missing_handle", "Parameter 'handle' is required, e.g. ?handle=jack")
    if not HANDLE_RE.match(handle):
        raise ValidationError(
            "invalid_handle",
            "A handle is 1-15 characters: letters, digits and underscore only.",
        )
    return handle


def _parse_evidence(evidence):
    """Validate user evidence. Returns (clean_dict, warnings)."""
    clean = {}
    warnings = []
    if evidence is None:
        return clean, warnings
    if not isinstance(evidence, dict):
        raise ValidationError("invalid_evidence", "'evidence' must be a JSON object.")
    for key, value in evidence.items():
        if value is None or value == "":
            continue
        if key in BOOL_FIELDS:
            if not isinstance(value, bool):
                raise ValidationError("invalid_evidence", "'{}' must be true, false or null.".format(key))
            clean[key] = value
        elif key in INT_FIELDS:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError("invalid_evidence", "'{}' must be a non-negative integer.".format(key))
            clean[key] = value
        elif key in TEXT_FIELDS:
            if not isinstance(value, str):
                raise ValidationError("invalid_evidence", "'{}' must be a string.".format(key))
            clean[key] = value.strip()[:2000]
        else:
            warnings.append("Ignored unknown evidence field '{}'.".format(key))
    return clean, warnings


def _signal(sid, label, source, observed, weight, detail):
    return {
        "id": sid,
        "label": label,
        "source": source,
        "observed": observed,
        "weight": weight,
        "detail": detail,
    }


def _weight_of(sid):
    if sid in STRONG:
        return "strong"
    if sid in MODERATE:
        return "moderate"
    if sid in WEAK:
        return "weak"
    return "info"


def evaluate(handle_raw, evidence=None, description=None, now=None):
    """Run the check and return the response dict.

    Raises ValidationError for missing or malformed input.
    """
    handle = normalize_handle(handle_raw)
    clean, warnings = _parse_evidence(evidence)
    if description is not None and not isinstance(description, str):
        raise ValidationError("invalid_description", "'description' must be a string.")
    description = (description or "").strip()[:4000]

    now = now or datetime.now(timezone.utc)
    signals = []

    api = xapi.integration_status()
    signals.append(_signal(
        "x_api_unavailable", "Automatic X API check", "system", None, "info", api["detail"],
    ))
    if xapi.lookup_user(handle) is None:
        signals.append(_signal(
            "handle_existence_unverified", "Account existence", "system", None, "info",
            "The tool cannot confirm that @{} exists or read its metrics without the X API. "
            "Open x.com/{} logged out to confirm.".format(handle, handle),
        ))

    # Text from notices or screenshot descriptions fills only empty fields.
    text_sources = []
    if clean.get("official_notice_text"):
        text_sources.append(("official_notice_text", clean["official_notice_text"]))
    if description:
        text_sources.append(("description", description))
    derived = {}
    for origin, text in text_sources:
        for field, pattern in TEXT_PATTERNS:
            if field in derived:
                continue
            match = pattern.search(text)
            if not match:
                continue
            if field in clean:
                if clean[field] is False:
                    warnings.append(
                        "Your {} mentions \"{}\", but '{}' was set to false. "
                        "The form value was used; check which one is right.".format(
                            "notice text" if origin == "official_notice_text" else "description",
                            match.group(0), field))
                continue
            derived[field] = (origin, match.group(0))

    observed = {}  # signal id -> (observed bool, source, detail)

    for field in BOOL_FIELDS:
        if field in clean:
            prefix = "Observed: " if clean[field] else "Checked, not observed: "
            observed[field] = (clean[field], "user_reported", prefix + BOOL_FIELDS[field])
        elif field in derived:
            origin, phrase = derived[field]
            observed[field] = (
                True, "user_text",
                '{} (matched "{}" in {})'.format(BOOL_FIELDS[field], phrase, origin),
            )

    # Search visibility is phrased positively; turn it into a problem signal.
    if "search_visible_logged_out" in observed:
        visible, source, _ = observed.pop("search_visible_logged_out")
        observed["search_not_visible_logged_out"] = (
            not visible, source,
            "Account {} in search from a logged-out / non-following view".format(
                "appears" if visible else "does not appear"),
        )

    # Impressions near zero, guarded against common misdiagnoses.
    imp = clean.get("impressions_last_7d")
    if imp is not None:
        posts = clean.get("posts_last_7d")
        baseline = clean.get("avg_weekly_impressions_prev_4w")
        if posts == 0:
            signals.append(_signal(
                "no_recent_posts", "Posting activity", "user_reported", None, "info",
                "No posts in the last 7 days, so low impressions are expected and are not evidence of a limit.",
            ))
        elif baseline is not None and baseline >= 100:
            near_zero = imp <= baseline * 0.05
            observed["impressions_near_zero"] = (
                near_zero, "user_reported",
                "{} impressions this week vs {} average before ({}% of baseline).".format(
                    imp, baseline, round(100.0 * imp / baseline, 1)),
            )
        elif baseline is None and posts and imp <= 5 * posts:
            observed["impressions_near_zero"] = (
                True, "user_reported",
                "{} impressions for {} posts. No baseline given, so this is weak on its own.".format(imp, posts),
            )
        else:
            signals.append(_signal(
                "impressions_inconclusive", "Impressions", "user_reported", None, "info",
                "Impressions alone are not conclusive. Add posts_last_7d and avg_weekly_impressions_prev_4w (>=100).",
            ))

    for sid, (obs, source, detail) in observed.items():
        signals.append(_signal(sid, sid.replace("_", " ").capitalize(), source, obs, _weight_of(sid), detail))

    positives = [sid for sid, (obs, _, _) in observed.items() if obs]
    strong = [s for s in positives if s in STRONG]
    moderate = [s for s in positives if s in MODERATE]
    weak = [s for s in positives if s in WEAK]
    negatives = [sid for sid, (obs, _, _) in observed.items() if obs is False]
    core_done = (
        "followers_only_visibility" in observed and "search_not_visible_logged_out" in observed
    )

    if strong:
        status = "limited"
        confidence = MAX_CONFIDENCE_USER_REPORTED
        summary = "A restriction notice from X was reported. Treat the account as limited until the notice clears."
    elif len(moderate) >= 2:
        status = "suspected"
        confidence = 0.5
        summary = "Several visibility signals point to reduced reach. Not confirmed by X."
    elif len(moderate) == 1:
        status = "suspected"
        confidence = 0.35
        summary = "One visibility signal was reported. It may be a normal fluctuation; recheck to confirm."
    elif weak:
        status = "unknown"
        confidence = 0.2
        summary = "Only weak signals were reported (often app or network issues). Not enough to call it."
    elif core_done and len(negatives) >= 3:
        status = "normal"
        confidence = 0.5 if len(negatives) >= 4 else 0.4
        summary = "The checks you reported show no visibility restriction."
    else:
        status = "unknown"
        confidence = CONFIDENCE_UNKNOWN if not observed else 0.2
        summary = (
            "Cannot determine. No verifiable data is available without the X API; "
            "run the manual checks below and submit the results."
            if not observed else
            "Cannot determine yet. Complete at least the logged-out visibility and search checks plus one more."
        )

    likely_causes = [CAUSES[s] for s in strong + moderate + weak if s in CAUSES]
    evidence_source = "none"
    if observed:
        sources = {src for (_, src, _) in observed.values()}
        if len(sources) == 1:
            evidence_source = sources.pop()
        else:
            evidence_source = "user_reported_and_text"

    return {
        "status": status,
        "signals": signals,
        "checked_at": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "confidence": round(confidence, 2),
        "handle": handle,
        "summary": summary,
        "evidence_source": evidence_source,
        "likely_causes": likely_causes,
        "action_48h": ACTIONS[status],
        "recheck_interval_hours": RECHECK_HOURS[status],
        "manual_checks": [c.replace("<handle>", handle) for c in MANUAL_CHECKS],
        "x_api": api,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }


def evidence_schema():
    """Describe accepted evidence fields (used by GET /api/limit-check/schema)."""
    fields = {}
    for k, v in BOOL_FIELDS.items():
        fields[k] = {"type": "boolean|null", "description": v}
    for k, v in INT_FIELDS.items():
        fields[k] = {"type": "integer|null", "description": v}
    for k, v in TEXT_FIELDS.items():
        fields[k] = {"type": "string", "description": v}
    return {"evidence_fields": fields, "statuses": list(STATUSES)}

