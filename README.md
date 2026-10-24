# X Growth Assistant

An open-source assistant for **growing real traffic on X (Twitter)**,
**checking content against X's rules before posting**, and **explaining
visibility-limit ("shadowban") checks honestly**.

The repo has two parts:

| Part | What it is |
|---|---|
| [`PROMPT.md`](PROMPT.md) | A complete system prompt. Load it into any LLM chat to get the full assistant. |
| [`web/`](web/) | A local website + JSON API: rule-based chat, pre-posting review, and a limit-check form. Python standard library only. |

> **Important: the X API integration is intentionally empty in this release.**
> The tool makes no calls to X. Without the API (and even with it), a
> third-party tool **cannot determine a shadowban with certainty**, so the
> limit check returns `status: "unknown"` with step-by-step manual checks
> until you give it evidence. See [Honesty and limits](#honesty-and-limits).

## Contents

```
PROMPT.md               system prompt (8 sections)
docs/
  content-policy.md     what can / cannot be posted, by category
  growth-playbook.md    sample weekly plan and metrics
  rate-limit.md         limit signals and how to avoid misdiagnosis
api/openapi.yaml        API specification (matches the running code)
examples/
  post-review.md        "review my post" conversation
  limit-check.md        "check whether I'm limited" conversation
web/backend/            Python server (server.py, limit_check.py, post_review.py, chat.py, xapi.py stub)
web/frontend/           static HTML/CSS/JS (chat + limit-check form)
tests/                  unit tests (test_api.py) and live smoke test (smoke_test.py)
VERIFICATION.md         recorded results of real API calls
.env.example            variable names for your own keys (no values)
```

## Requirements

- **Python 3.9 or newer** (tested with 3.12.3). No `pip install` needed.
- Node.js is **not** required.
- Any modern browser.

## Quick start

```bash
git clone <your-fork-url> x-growth-assistant
cd x-growth-assistant
python3 web/backend/server.py
```

Open http://127.0.0.1:8000/. On Windows use `py web\backend\server.py`.

Options:

```bash
PORT=9000 python3 web/backend/server.py      # different port
HOST=0.0.0.0 python3 web/backend/server.py   # listen on your LAN (no auth, so be careful)
```

### Using the prompt only

Copy the content of `PROMPT.md` into the system prompt / custom instructions
of the LLM you use. The website does not need to be running for that.

## What still needs to be connected

Local run needs nothing extra: Python 3.9+ only, standard library, no
`pip install`, no keys. The table below is everything that is NOT wired
up yet, and what each item takes to work.

| # | Feature | Works now? | What still needs to be connected | Who provides it |
|---|---|---|---|---|
| 1 | Website + rule chat + post review + manual-evidence limit check | Yes, out of the box | Nothing. Run `python3 web/backend/server.py` and open http://127.0.0.1:8000/ | — |
| 2 | Automatic limit check (verify handle exists, read post metrics) | No — returns `unknown` + manual steps | (a) Implement the calls listed in the TODO at the top of `web/backend/xapi.py` (`lookup_user`, `recent_post_metrics`); (b) the end user fills their own key in `.env` (`X_API_BEARER_TOKEN`, see below). Key alone is NOT enough: today a key only flips `x_api.state` to `not_implemented` and still sends no request to X | Code: repo owner. Key: each end user |
| 3 | Free-form smart chat on the website | No — chat is rule-based (`review:` / `check @handle` / growth tips only) | Load `PROMPT.md` into an LLM and wire an LLM API key + endpoint into a new chat backend. No LLM code exists in this repo yet | Repo owner (code + key) |
| 4 | X account login binding ("site already linked to X") | No | X OAuth 2.0 (PKCE) flow: app registration at developer.x.com, redirect URI, token storage. Never ask for or store the user's X password | Repo owner + each end user authorises their own account |
| 5 | Public website (anyone on the internet can open it) | No — local only, no auth, no rate limiting | A server/VPS, a domain, HTTPS via a reverse proxy, plus auth and rate limiting in front of the server. Until then keep it on `127.0.0.1` | Whoever deploys it |

In short: **to run it locally, connect nothing. To make the limit check
automatic, connect (2). To make the chat smart, connect (3). To put it
online, connect (5).** Items (2)–(5) are deliberately left out of this
release; they are not hidden dependencies.

## The website

- **Chat** (left): opens with a greeting. Rule-based, no LLM. It understands:
  - `how do I grow`: this week's 3 actions
  - `review: <draft>`: verdict `allowed` / `revise` / `do_not_post` with risk level
  - `check @handle` or `am I shadowbanned? @handle`: runs the limit check
  - refuses bought engagement, account takeover, ban evasion and automation spam, and warns if you paste a password
- **Limit check** (right): handle + what you observed (yes / no / not checked),
  optional analytics numbers, exact notice text, a description of your screenshot in
  words, or a pasted evidence JSON. Result colours:
  - green `normal`, yellow `suspected`, red `limited`, grey `unknown`.

The frontend only renders the JSON from the API. It never decides a status.

## API

Full spec: [`api/openapi.yaml`](api/openapi.yaml).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{ok, version, x_api}` |
| GET | `/api/limit-check?handle=<h>` | Check without evidence (always `unknown`) |
| POST | `/api/limit-check` | `{handle, evidence?, description?}` → result |
| GET | `/api/limit-check/schema` | Accepted evidence fields |
| POST | `/api/post-review` | `{text}` → verdict, risk, reasons, suggestions |
| POST | `/api/chat` | `{message}` → `{intent, reply, data?}` |

Limit-check response (always present): `status` (`normal | suspected | limited | unknown`),
`signals[]`, `checked_at` (UTC ISO 8601), `confidence` (0–0.6). Also returned:
`summary`, `likely_causes`, `action_48h`, `recheck_interval_hours`, `manual_checks`,
`evidence_source`, `x_api`, `warnings`, `disclaimer`.

```bash
curl "http://127.0.0.1:8000/api/limit-check?handle=jack"

curl -X POST http://127.0.0.1:8000/api/limit-check \
  -H 'Content-Type: application/json' \
  -d '{"handle":"jack","evidence":{"followers_only_visibility":true,"search_visible_logged_out":false}}'

curl -X POST http://127.0.0.1:8000/api/post-review \
  -H 'Content-Type: application/json' -d '{"text":"Use code SAVE10 for 10% off"}'
```

Errors are JSON too: `{"error": {"code": "missing_handle", "message": "..."}}` with HTTP 400/404/405.

## Honesty and limits

- **No X API key → no automatic verification.** The check is based only on what
  you report. With no evidence the result is `unknown` (confidence 0.1) plus manual steps.
- **No fake statuses.** Nothing defaults to `normal`. `normal` needs the two core
  checks (logged-out visibility and search) plus at least one more, all negative.
- **Confidence is capped at 0.6** because user-reported evidence can't be verified.
- **A nonexistent handle can't be detected** without the API: well-formed handles
  get `unknown` with the signal `handle_existence_unverified`. Malformed handles get HTTP 400.
- **Screenshots are not read.** Describe them in words or paste the exact notice;
  matched phrases are listed as signals with `source: "user_text"`.
- **The post review is a keyword heuristic.** It can miss context (sarcasm,
  quotes, news) and flag harmless text.
- **Official notices from X are the authority.** Details: [`docs/rate-limit.md`](docs/rate-limit.md).

## X API keys (end user supplies their own)

The X API integration is **left empty in this release** and waits for the owner
to wire it up later. `web/backend/xapi.py` is a stub: it reads environment
variables and reports `not_configured` (or `not_implemented` if a key is present)
and **never sends a request**. The TODO list for the real integration is at the top of that file.

When the integration exists, each end user uses **their own** key:

```bash
cp .env.example .env
# edit .env:
#   X_API_BEARER_TOKEN=<your token from developer.x.com>
#   X_API_CLIENT_ID=<optional, for OAuth 2.0>
#   X_API_CLIENT_SECRET=<optional, for OAuth 2.0>
python3 web/backend/server.py   # restart to pick up changes
```

- `.env` is git-ignored. Never commit keys. The repo ships no keys.
- Environment variables set in the shell override `.env`.
- Today, setting a key only changes `x_api.state` to `not_implemented`; the
  limit check still returns `unknown` without manual evidence.
- Never put your X password anywhere. Future account access must use X's official OAuth 2.0.

## Tests

```bash
python3 -m unittest discover -s tests -v   # 23 tests, starts its own server on a free port
python3 web/backend/server.py &            # then, against the running server:
python3 tests/smoke_test.py                # 8 live checks; exit code 1 on failure
```

Recorded results: [`VERIFICATION.md`](VERIFICATION.md).

## Running it elsewhere

This is a repo meant for local use. It is not a hosted service: there are no
user accounts, no deployment config and no domain. If you want it on another
machine, run the same command there (any host with Python 3.9+). The server has
**no authentication and no rate limiting**, so keep it on `127.0.0.1` or put it
behind your own reverse proxy with auth before exposing it to a network.

## Disclaimer

Operational advice only, not legal advice. The check can be wrong in both
directions. Official X notices and the [X Rules](https://help.x.com/en/rules-and-policies)
take precedence. This project does not support ban evasion, fraud, account
takeover or API abuse.

## License

[MIT](LICENSE)

