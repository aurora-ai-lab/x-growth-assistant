# X Growth Assistant

A small, local toolkit for planning X content, reviewing drafts against platform rules, and checking visibility signals from user-provided evidence.

## Features

- Rule-based chat for growth questions and content review
- Pre-posting review with verdicts, risks, and suggestions
- Manual visibility and reach checks
- Local web interface and JSON API
- No external API calls required for the default local workflow

## Quick start

Requirements: Python 3.9 or newer.

```bash
python3 web/backend/server.py
```

Open <http://127.0.0.1:8000/>.

On Windows:

```text
py web\backend\server.py
```

Run the tests:

```bash
python3 -m unittest discover -s tests -v
```

## Repository layout

- `web/backend/` — Python server and API handlers
- `web/frontend/` — static browser interface
- `api/openapi.yaml` — API specification
- `docs/` — policy and usage notes
- `examples/` — example conversations
- `tests/` — automated and smoke tests
- `PROMPT.md` — optional system prompt

## Configuration and privacy

The default release is local-only and does not require an API key. The repository contains only `.env.example`; never commit a real `.env` file or credentials.

The server has no built-in authentication or rate limiting. Keep it on localhost unless you add your own protected reverse proxy.

## Safety

This project does not support ban evasion, fraud, account takeover, or API abuse. It provides operational guidance only; official platform notices and policies take precedence.

## License

MIT
