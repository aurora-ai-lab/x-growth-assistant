# Visibility limits and rate limits: signals and how not to misdiagnose them

## 1. What the tool can and cannot know

**Without an X API key, nothing about an account can be verified
automatically.** The X API integration in this release is an empty stub
(`web/backend/xapi.py`): it makes no network calls. Even with a key, the
public API does not expose X's internal moderation or ranking state, so a
"shadowban" can never be confirmed with certainty by a third-party tool.

Therefore the endpoint follows these rules:

| Situation | Status returned | Confidence |
|---|---|---|
| No evidence submitted | `unknown` + step-by-step manual checks | 0.1 |
| Only weak signals (button errors) | `unknown` | 0.2 |
| Not enough checks to rule anything out | `unknown` | 0.2 |
| One moderate signal | `suspected` | 0.35 |
| Two or more moderate signals | `suspected` | 0.5 |
| User reports an official X restriction notice, captcha or lock | `limited` | 0.6 (cap) |
| Core checks done (logged-out visibility + search) and at least 3 negative results, no positive signal | `normal` | 0.4–0.5 |

Confidence never goes above 0.6 because every input is reported by the user
and cannot be verified by the tool. The status is computed only on the server;
the frontend just displays it.

"Nonexistent handle": the tool cannot tell whether a well-formed handle
exists, so it returns `unknown` with the signal `handle_existence_unverified`
instead of an error. Malformed handles (more than 15 characters, characters
other than letters, digits and `_`) return HTTP 400.

## 2. Signals

| Signal id | Weight | What the user checks | Common innocent explanation |
|---|---|---|---|
| `action_blocked_notice` | strong | Banner such as "Some of your account features are temporarily limited" | None; this is X telling you directly |
| `captcha_or_temporary_lock` | strong | Captcha (Arkose), phone verification, "account locked" | New device/IP, VPN, security check |
| `rate_limit_notice` | moderate | "You are over the daily limit", "try again later" | Normal usage caps (follows, posts, DMs, reading) |
| `followers_only_visibility` | moderate | From a logged-out or non-following account, posts/replies do not show | Protected account setting, deleted post, slow cache |
| `search_not_visible_logged_out` | moderate | Search for `@handle` and a unique phrase from a non-following account | New or renamed account, very recent post |
| `impressions_near_zero` | moderate | 7-day impressions ≤ 5% of the previous 4-week weekly average (baseline ≥ 100) | Fewer posts, topic change, holiday, analytics delay |
| `replies_hidden_behind_show_more` | moderate | Your replies collapsed under "Show more replies" / "probable spam" | Replies are always ranked; new accounts rank low |
| `button_errors` | weak | Like/follow/repost fails or reverts | App version, network, ad blocker |

Free-text descriptions (for example a screenshot described in words, or the
copied notice text) are scanned for known phrases. A phrase only fills a field
the user left as "not checked", and each match is shown as its own signal with
`source: "user_text"` and the exact phrase matched.

## 3. Avoiding misdiagnosis

1. **No posts, no impressions.** If `posts_last_7d` is 0, low impressions are
   not evidence; the tool adds `no_recent_posts` and ignores the drop.
2. **Compare with your own baseline**, not with other accounts. The tool needs
   `avg_weekly_impressions_prev_4w` ≥ 100 to judge a drop.
3. **One bad day is noise.** Use 7-day windows.
4. **Rate limits are not shadowbans.** "Over the daily limit" means an action
   cap was reached; it usually clears within hours.
5. **Check from the right viewpoint.** Your own logged-in view always shows your
   posts. Use a private window or an account that does not follow you.
6. **Protected accounts** are visible only to followers by design.
7. **Analytics delay.** Numbers can lag for hours; recheck before acting.
8. **Never create a new account to escape a limit.** That is ban evasion and
   can turn a temporary limit into a suspension.

## 4. Manual check (about 10 minutes)

1. Private/incognito window → `x.com/<handle>`. Does the profile load with recent posts?
2. Non-following account → search `@handle` and a distinctive phrase from your latest post. Check Top and Latest.
3. Non-following account → open a post you replied to. Is your reply visible or collapsed?
4. Analytics → impressions last 7 days, the 4 weeks before, number of posts (account analytics needs X Premium; otherwise add up per-post view counts).
5. Notifications and Settings → copy any notice text exactly.
6. Try one normal action (like a friend's post). Note errors, rate-limit messages or captchas.
7. Enter the results in the website form (or JSON) and run the check again.

## 5. Recovery (general)

| Status | First 48 hours | Recheck |
|---|---|---|
| `limited` | Stop automation, revoke write-access apps, complete X's verification, pause bulk actions, follow the notice, appeal via help.x.com if mistaken | 48 h |
| `suspected` | Pause bulk actions, 1–2 original posts/day without links or mass mentions, recheck from a non-following account | 24 h |
| `normal` | Focus on content; keep weekly metrics | 7 days |
| `unknown` | Do the manual check; do not change behaviour based on a guess | 24 h |

## 6. Evidence JSON format

```json
{
  "handle": "yourhandle",
  "evidence": {
    "action_blocked_notice": false,
    "captcha_or_temporary_lock": false,
    "rate_limit_notice": false,
    "button_errors": false,
    "followers_only_visibility": true,
    "search_visible_logged_out": false,
    "replies_hidden_behind_show_more": null,
    "impressions_last_7d": 120,
    "avg_weekly_impressions_prev_4w": 4800,
    "posts_last_7d": 9,
    "followers": 1300,
    "official_notice_text": ""
  },
  "description": "Optional: describe what your screenshot shows, in words."
}
```

`true` = observed, `false` = checked and not observed, `null` or missing = not
checked. Unknown fields are ignored with a warning. The live list of fields is
at `GET /api/limit-check/schema`.

## 7. Official sources

- X Rules and policies: https://help.x.com/en/rules-and-policies
- About account locks and limits: https://help.x.com/en/managing-your-account/locked-and-limited-accounts
- X API rate limits (for developers): https://docs.x.com/x-api/fundamentals/rate-limits

When an official X notice and this tool disagree, the notice wins.

