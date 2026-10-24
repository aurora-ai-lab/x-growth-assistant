# Example: "Check whether my account is limited"

Three rounds of the same conversation. Round 1 has no data, round 2 adds the
user's observations, and round 3 covers an official notice. The JSON excerpts
are copied from real runs of the local API (2026-10-24). `checked_at`
values will differ on your machine.

## Round 1: no data → `unknown`

**User:** am I shadowbanned? @lan_builds

**Website chat (real output):**

```
Status: unknown (confidence 0.1).
Cannot determine. No verifiable data is available without the X API; run the manual checks below and submit the results.
Manual checks (about 10 minutes):
1. Open a private/incognito browser window (logged out) and visit x.com/lan_builds. Note whether the profile and latest posts load.
2. From a second account that does NOT follow you, search for your exact @handle and for a distinctive phrase from your latest post. Note whether you appear in 'Top' and 'Latest'.
3. From that same account, open a recent reply of yours under someone else's post. Note whether it is shown normally or collapsed under 'Show more replies' / 'Show probable spam'.
4. Write down impressions for the last 7 days, the average week of the 4 weeks before, and how many posts and replies you published. Account analytics needs X Premium; without it, add up the view counts shown under each post.
5. Check Notifications and Settings > Your account for any notice from X. Copy the exact wording; do not paraphrase.
6. Try one normal action (like a post from a friend). Note whether it fails, reverts, or shows a rate-limit or captcha prompt.
7. Paste the results into the form (or as JSON) and run the check again.
```

**Assistant running PROMPT.md would add:**
> I can't tell yet. Without data, any "yes" or "no" would be a guess. Do the
> 7 checks above (about 10 minutes) and send me what you see.

## Round 2: user observations → `suspected`

The user ran the checks and entered them in the form:

```bash
curl -s -X POST http://127.0.0.1:8000/api/limit-check \
  -H 'Content-Type: application/json' \
  -d '{
    "handle": "@lan_builds",
    "evidence": {
      "followers_only_visibility": true,
      "search_visible_logged_out": false,
      "impressions_last_7d": 140,
      "avg_weekly_impressions_prev_4w": 5200,
      "posts_last_7d": 11,
      "followers": 1850,
      "action_blocked_notice": false
    },
    "description": "My replies under big accounts are collapsed under Show probable spam"
  }'
```

Response (`manual_checks` omitted):

```json
{
  "status": "suspected",
  "signals": [
    {"id": "x_api_unavailable", "source": "system", "observed": null, "weight": "info",
     "detail": "No X API credentials found. Set X_API_BEARER_TOKEN in .env to prepare for automatic checks (not implemented yet)."},
    {"id": "handle_existence_unverified", "source": "system", "observed": null, "weight": "info",
     "detail": "The tool cannot confirm that @lan_builds exists or read its metrics without the X API. Open x.com/lan_builds logged out to confirm."},
    {"id": "action_blocked_notice", "source": "user_reported", "observed": false, "weight": "strong",
     "detail": "Checked, not observed: X showed an 'action blocked' / 'temporarily restricted' notice"},
    {"id": "followers_only_visibility", "source": "user_reported", "observed": true, "weight": "moderate",
     "detail": "Observed: Posts or replies are visible to followers only (checked from a logged-out or non-following account)"},
    {"id": "replies_hidden_behind_show_more", "source": "user_text", "observed": true, "weight": "moderate",
     "detail": "Replies are collapsed under 'Show more replies' / 'Show probable spam' (matched \"probable spam\" in description)"},
    {"id": "search_not_visible_logged_out", "source": "user_reported", "observed": true, "weight": "moderate",
     "detail": "Account does not appear in search from a logged-out / non-following view"},
    {"id": "impressions_near_zero", "source": "user_reported", "observed": true, "weight": "moderate",
     "detail": "140 impressions this week vs 5200 average before (2.7% of baseline)."}
  ],
  "checked_at": "2026-10-24T14:41:39Z",
  "confidence": 0.5,
  "handle": "lan_builds",
  "summary": "Several visibility signals point to reduced reach. Not confirmed by X.",
  "evidence_source": "user_reported_and_text",
  "likely_causes": [
    "Possible reply or search de-ranking after reports, repeated identical replies, or many links.",
    "Replies ranked as low quality or probable spam: repeated text, links in replies, many mentions, low account history.",
    "Possible search suggestion/search ranking restriction. New or recently renamed accounts can also be missing from search for a while.",
    "Reach dropped sharply. Check content changes and posting frequency before assuming a penalty."
  ],
  "action_48h": [
    "Pause bulk actions (follow/unfollow, repeated replies, many links) for 48 hours.",
    "Publish 1-2 original posts per day without external links and without mass mentions.",
    "Repeat the logged-out and second-account checks after 24 hours and compare.",
    "Compare impressions with your posting frequency; fewer posts explain lower reach."
  ],
  "recheck_interval_hours": 24,
  "x_api": {"state": "not_configured", "detail": "..."},
  "warnings": [],
  "disclaimer": "This tool cannot see X's internal moderation state. Results are based on the evidence provided and may be wrong. Official notices from X are the authority."
}
```

**Assistant running PROMPT.md explains it:**

> **Status: suspected (confidence 0.5). Not confirmed by X.**
>
> Evidence: four visibility signals you reported (followers-only visibility,
> missing from logged-out search, replies collapsed as "probable spam",
> impressions at 2.7% of your usual week). No restriction notice from X.
>
> Likely causes, most likely first:
> 1. Reply de-ranking. Did you paste similar replies under many posts or add links in replies?
> 2. Search ranking restriction after reports.
>
> 48-hour actions:
> 1. No follow/unfollow bursts, no repeated replies, no links in replies.
> 2. 1–2 original posts per day, no external links.
> 3. Recheck from the non-following account in 24 hours.
>
> This is the algorithm showing you less, not a confirmed rule violation. If X
> shows an official notice, that notice is the authority.

## Round 3: an official notice in a screenshot → `limited`

**User:** After following about 200 accounts this morning X showed a banner:
"Some of your account features are temporarily limited". The follow button
also reverts.

The text goes into the form's description field (the tool cannot read
images; describe the screenshot in words or paste the exact notice):

```json
{
  "status": "limited",
  "confidence": 0.6,
  "evidence_source": "user_text",
  "likely_causes": [
    "Activity pattern that looks automated: bursts of follows, likes, replies or DMs in a short time.",
    "Often a client or network bug; can also accompany a temporary action restriction."
  ]
}
```

Signals (excerpt):

```json
{"id": "action_blocked_notice", "source": "user_text", "observed": true, "weight": "strong", "detail": "X showed an 'action blocked' / 'temporarily restricted' notice (matched \"Some of your account features are\" in description)"}
{"id": "button_errors", "source": "user_text", "observed": true, "weight": "weak", "detail": "Like / repost / follow buttons fail or revert (matched \"follow button also reverts\" in description)"}
```

**Assistant:**

> **Status: limited (from the notice you reported).** Confidence is capped at 0.6
> because the tool can't see the notice itself.
>
> The likely cause is 200 follows in one morning, which reads as automation.
> For the next 48 hours:
> 1. Stop following. Revoke any follow tool under Apps and sessions.
> 2. Complete any verification X asks for.
> 3. Post 1–2 normal original posts per day. No DMs in bulk.
> 4. If you think the notice is a mistake, appeal at help.x.com. Don't open a new account to get around it.
>
> Recheck in 48 hours.

## What the tool will not do

- Return `normal` because nothing was entered. Empty input always gives `unknown`.
- Claim it checked X. `x_api.state` is `not_configured` until the integration is built (see README).
- Ask for your password. Never paste it anywhere in this tool.

