"""X (Twitter) API integration stub.

STATUS: intentionally left empty in this release.

This module makes NO network calls. It only reads configuration from
environment variables and reports whether an integration is available.
The limit-check endpoint consults it so the response can say honestly
why it cannot verify anything automatically.

The end user supplies their own X API credentials (see `.env.example`
and README.md). The repository never ships keys.

TODO (next step, once credentials are provided by the end user):
  1. Implement `lookup_user(handle)` with GET /2/users/by/username/:username
     to confirm the account exists and read public_metrics.
  2. Implement `recent_post_metrics(user_id)` with GET /2/users/:id/tweets
     (tweet.fields=public_metrics, non_public_metrics needs user-context
     OAuth 2.0 and only works for the authenticated account itself).
  3. Feed the results into `limit_check.evaluate()` as signals with
     source="x_api" instead of "user_reported".
  4. Respect X API rate limits (HTTP 429, `x-rate-limit-reset` header)
     and cache responses; never retry in a tight loop.
  5. Use OAuth 2.0 (PKCE) for user-context data. Never ask for or store
     the user's X password.
"""

import os

# Environment variable names. Values are read at call time so a restart
# after editing `.env` is enough to pick up a new key.
ENV_BEARER_TOKEN = "X_API_BEARER_TOKEN"
ENV_CLIENT_ID = "X_API_CLIENT_ID"
ENV_CLIENT_SECRET = "X_API_CLIENT_SECRET"


def _configured_keys():
    return [
        name
        for name in (ENV_BEARER_TOKEN, ENV_CLIENT_ID, ENV_CLIENT_SECRET)
        if os.environ.get(name, "").strip()
    ]


def integration_status():
    """Return the state of the X API integration.

    Possible `state` values:
      - "not_configured": no credentials in the environment.
      - "not_implemented": credentials found, but API calls are not
        implemented in this release (see module TODO). Nothing is sent.
    """
    present = _configured_keys()
    if not present:
        return {
            "state": "not_configured",
            "detail": (
                "No X API credentials found. Set X_API_BEARER_TOKEN in .env "
                "to prepare for automatic checks (not implemented yet)."
            ),
        }
    return {
        "state": "not_implemented",
        "detail": (
            "X API credentials detected ({}), but automatic lookups are not "
            "implemented in this release. No request was sent to X.".format(
                ", ".join(present)
            )
        ),
    }


def lookup_user(handle):
    """Placeholder for the future account lookup.

    Always returns None in this release so callers fall back to manual
    checks. It never raises and never touches the network.
    """
    # TODO: call GET https://api.x.com/2/users/by/username/{handle}
    # with the bearer token once the integration is implemented.
    return None

