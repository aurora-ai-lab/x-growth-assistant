# Verification record

Real runs on **2026-10-24**: Linux, **Python 3.12.3**, no `.env`, X API not configured.
The server was started with `python3 web/backend/server.py` and called over
HTTP. Nothing here is mocked. Re-run the same commands to reproduce;
`checked_at` will differ.

## 1. Live smoke test (`python3 tests/smoke_test.py`)

The three required cases are 1–3:

| # | Case | Request | HTTP | Result |
|---|---|---|---|---|
| 1 | Normal handle, no evidence | `GET /api/limit-check?handle=jack` | 200 | `unknown`, confidence 0.1, manual checks returned |
| 2 | Handle that does not exist | `GET /api/limit-check?handle=zz_nosuchuser99` | 200 | `unknown` + signal `handle_existence_unverified` (existence cannot be checked without the X API) |
| 3 | Missing parameter | `GET /api/limit-check` | 400 | `{"error":{"code":"missing_handle",...}}` |
| 4 | Malformed handle | `GET /api/limit-check?handle=bad-handle!` | 400 | `invalid_handle` |
| 5 | Evidence: official notice | `POST /api/limit-check` | 200 | `limited`, confidence 0.6 (cap) |
| 6 | Evidence: two visibility signals | `POST /api/limit-check` | 200 | `suspected`, confidence 0.5 |
| 7 | Post review, scam text | `POST /api/post-review` | 200 | `do_not_post`, risk high |
| 8 | Health | `GET /api/health` | 200 | `ok: true`, `x_api: not_configured` |

Full output (signals trimmed to id/source/observed/weight by the script):

```text
========================================================================
GET /api/limit-check?handle=jack  ->  HTTP 200  [PASS]
# 1. normal handle, no evidence
{
  "status": "unknown",
  "confidence": 0.1,
  "checked_at": "2026-10-24T14:44:17Z",
  "handle": "jack",
  "summary": "Cannot determine. No verifiable data is available without the X API; run the manual checks below and submit the results.",
  "signals": [
    {
      "id": "x_api_unavailable",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "handle_existence_unverified",
      "source": "system",
      "observed": null,
      "weight": "info"
    }
  ]
}
========================================================================
GET /api/limit-check?handle=zz_nosuchuser99  ->  HTTP 200  [PASS]
# 2. well-formed handle that may not exist
{
  "status": "unknown",
  "confidence": 0.1,
  "checked_at": "2026-10-24T14:44:17Z",
  "handle": "zz_nosuchuser99",
  "summary": "Cannot determine. No verifiable data is available without the X API; run the manual checks below and submit the results.",
  "signals": [
    {
      "id": "x_api_unavailable",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "handle_existence_unverified",
      "source": "system",
      "observed": null,
      "weight": "info"
    }
  ]
}
========================================================================
GET /api/limit-check  ->  HTTP 400  [PASS]
# 3. missing parameter
{
  "error": {
    "code": "missing_handle",
    "message": "Parameter 'handle' is required, e.g. ?handle=jack"
  }
}
========================================================================
GET /api/limit-check?handle=bad-handle!  ->  HTTP 400  [PASS]
# 4. malformed handle
{
  "error": {
    "code": "invalid_handle",
    "message": "A handle is 1-15 characters: letters, digits and underscore only."
  }
}
========================================================================
POST /api/limit-check  ->  HTTP 200  [PASS]
# 5. user evidence: official notice
{
  "status": "limited",
  "confidence": 0.6,
  "checked_at": "2026-10-24T14:44:17Z",
  "handle": "jack",
  "summary": "A restriction notice from X was reported. Treat the account as limited until the notice clears.",
  "signals": [
    {
      "id": "x_api_unavailable",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "handle_existence_unverified",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "action_blocked_notice",
      "source": "user_reported",
      "observed": true,
      "weight": "strong"
    }
  ]
}
========================================================================
POST /api/limit-check  ->  HTTP 200  [PASS]
# 6. user evidence: two visibility signals
{
  "status": "suspected",
  "confidence": 0.5,
  "checked_at": "2026-10-24T14:44:17Z",
  "handle": "jack",
  "summary": "Several visibility signals point to reduced reach. Not confirmed by X.",
  "signals": [
    {
      "id": "x_api_unavailable",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "handle_existence_unverified",
      "source": "system",
      "observed": null,
      "weight": "info"
    },
    {
      "id": "followers_only_visibility",
      "source": "user_reported",
      "observed": true,
      "weight": "moderate"
    },
    {
      "id": "search_not_visible_logged_out",
      "source": "user_reported",
      "observed": true,
      "weight": "moderate"
    }
  ]
}
========================================================================
POST /api/post-review  ->  HTTP 200  [PASS]
# 7. post review: scam pattern
{
  "verdict": "do_not_post",
  "verdict_label": "Do not post",
  "risk": "high",
  "reasons": [
    "Guaranteed-return promises or requests for wallet secrets match common scam patterns."
  ],
  "suggestions": [
    "Remove profit guarantees and never ask for keys or seed phrases."
  ],
  "matched": [
    {
      "category": "scam",
      "label": "Scam or fraud pattern",
      "level": "prohibited",
      "match": "Guaranteed returns"
    }
  ],
  "stats": {
    "characters": 45,
    "hashtags": 0,
    "mentions": 0,
    "links": 0,
    "paid_partnership_disclosed": false
  },
  "disclaimer": "Keyword-based check. It can miss context or flag harmless text. X's rules (help.x.com/rules-and-policies) are the authority."
}
========================================================================
GET /api/health  ->  HTTP 200  [PASS]
# 8. health
{
  "ok": true,
  "version": "1.0.0",
  "x_api": "not_configured"
}
========================================================================
8 passed, 0 failed
```

## 2. Unit tests (`python3 -m unittest discover -s tests -v`)

23 tests, all passing (`Ran 23 tests ... OK`). They start the real server on a
free port and cover JSON shape, all four statuses, validation errors,
user-text parsing, conflicting form/text input, the "no posts" misdiagnosis
guard, the X API stub (no network imports, key present → still `unknown`),
post review, chat intents, static files and path traversal.

```text
test_all_clear_gives_normal (test_api.ApiTest.test_all_clear_gives_normal) ... ok
test_chat (test_api.ApiTest.test_chat) ... ok
test_dates_are_not_phone_numbers (test_api.ApiTest.test_dates_are_not_phone_numbers) ... ok
test_description_text_is_parsed (test_api.ApiTest.test_description_text_is_parsed) ... ok
test_disclosure_and_superlatives (test_api.ApiTest.test_disclosure_and_superlatives) ... ok
test_handle_normalisation (test_api.ApiTest.test_handle_normalisation) ... ok
test_health_and_schema (test_api.ApiTest.test_health_and_schema) ... ok
test_impression_drop_vs_baseline (test_api.ApiTest.test_impression_drop_vs_baseline) ... ok
test_invalid_handle_is_400 (test_api.ApiTest.test_invalid_handle_is_400) ... ok
test_invalid_json_and_types (test_api.ApiTest.test_invalid_json_and_types) ... ok
test_key_present_still_unknown (test_api.ApiTest.test_key_present_still_unknown) ... ok
test_missing_handle_is_400 (test_api.ApiTest.test_missing_handle_is_400) ... ok
test_moderate_signals_give_suspected (test_api.ApiTest.test_moderate_signals_give_suspected) ... ok
test_no_posts_is_not_a_limit (test_api.ApiTest.test_no_posts_is_not_a_limit) ... ok
test_nonexistent_handle_is_unknown_not_error (test_api.ApiTest.test_nonexistent_handle_is_unknown_not_error) ... ok
test_normal_handle_without_evidence_is_unknown (test_api.ApiTest.test_normal_handle_without_evidence_is_unknown) ... ok
test_official_notice_gives_limited_with_capped_confidence (test_api.ApiTest.test_official_notice_gives_limited_with_capped_confidence) ... ok
test_partial_negative_checks_stay_unknown (test_api.ApiTest.test_partial_negative_checks_stay_unknown) ... ok
test_post_review (test_api.ApiTest.test_post_review) ... ok
test_static_and_traversal (test_api.ApiTest.test_static_and_traversal) ... ok
test_text_conflicting_with_form_warns (test_api.ApiTest.test_text_conflicting_with_form_warns) ... ok
test_unknown_field_warns (test_api.ApiTest.test_unknown_field_warns) ... ok
test_xapi_stub_has_no_network_code (test_api.ApiTest.test_xapi_stub_has_no_network_code) ... ok
```

## 3. Frontend check

There is no browser in the build sandbox, so the page was loaded from the
running server in **jsdom 24** (Node 24) with `fetch` pointed at the real API,
then the forms were submitted:

```text
greeting: Hi! I'm your X traffic and content compliance assistant. I c
api pill: API v1.0.0 · X API: not_configured
bool selects: 7
A class: result status-unknown | badge: unknown | manual steps: 7
B class: result status-limited
C class: result status-suspected
D class: result status-normal
E: result Evidence JSON is not valid JSON.
F: result Error: Parameter 'handle' is required, e.g. ?handle=jack
chat reply: Verdict: Revise before posting (risk: medium) / Why: / - Giveaways that require follows/reposts can look like spam if rules and eligibility are missing.
```

The page showed the greeting and loaded 7 evidence fields from
`/api/limit-check/schema`. All four colour classes came from server
responses: unknown = grey, limited = red, suspected = yellow, normal = green.
Invalid JSON and a missing handle showed errors without any status. Colours
were not checked visually.

## 4. `.env` key flow

On a temporary copy of the repo, a `.env` with `PORT=8011` and a dummy
`X_API_BEARER_TOKEN` was added and the server restarted:

```text
X Growth Assistant running at http://127.0.0.1:8011/  (X API: not_implemented)
GET /api/health                 -> {"ok": true, "version": "1.0.0", "x_api": "not_implemented"}
GET /api/limit-check?handle=jack -> status "unknown", x_api.state "not_implemented"
```

No request is sent to X in either state. The copy was deleted afterwards; the
repo contains no `.env`.

## 5. Other checks

- Every `.py` file parses with Python 3.9 grammar (`ast.parse(..., feature_version=(3, 9))`).
  It was **not** executed on a real 3.9 interpreter.
- Secret scan: no key, token or password values in the repo. The only hits are
  environment variable *names* and a `"dummy-for-test"` value in a unit test.
- No empty files.
- Cited official URLs returned HTTP 200 on 2026-10-24: help.x.com rules page,
  help.x.com locked-and-limited accounts page, docs.x.com rate-limits page.

