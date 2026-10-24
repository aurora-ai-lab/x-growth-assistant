# Content policy: what to post and what not to post

This table is the reference for the assistant (PROMPT.md section 4–5) and for
the rule-based checker in `web/backend/post_review.py`. It summarises
common risk patterns; the authority is always the
[X Rules and policies](https://help.x.com/en/rules-and-policies).

Two kinds of "no" are kept apart on purpose:

- **Prohibited**: breaks X's rules. Possible removal, lock, or suspension.
- **Not recommended**: allowed, but the ranking system tends to show it less.

## 1. Verdicts and risk levels

| Verdict | Meaning | Typical risk |
|---|---|---|
| `allowed` | Post as is. | low |
| `revise` | Fix the listed issues, then post. Grey-zone default. | low–medium |
| `do_not_post` | Do not publish. Rewording is not enough. | high |

## 2. Prohibited or high risk: `do_not_post`

| Category | Examples of what triggers it | Why | What to do instead |
|---|---|---|---|
| Violence | "I'll hurt him", wishing death, praising attacks | Violent Speech policy | Criticise the action; report real threats |
| Hateful conduct | Dehumanising a group ("vermin", "subhuman") | Hateful Conduct policy | Debate ideas, not identities |
| Minors | Any sexualised reference to minors; identifiable children without guardian consent | Child Sexual Exploitation policy, zero tolerance | Do not post; report if you see it |
| Adult content | Nudity, porn links, "NSFW" promos on a growth account | Must be labelled, never in avatar/header, not promoted | Keep the growth account safe-for-work |
| Scams / fraud | "Guaranteed returns", "send 1 ETH get 2", asking for seed phrases | Financial Scam policy | State real results; never request keys |
| Impersonation | "Official X Support", fake brand accounts | Misleading & Deceptive Identities | Speak as yourself; label parody clearly |
| Private information | Someone's phone number, home address, ID, private photos | Private Information policy | Remove; use public business contact pages |
| Spam / manipulation | "F4F", "follow back 100%", bought likes, duplicate posts | Platform Manipulation & Spam | See `growth-playbook.md` |
| Copyright | "Full movie", leaked courses, cracked software | Copyright policy / DMCA | Link the official source; add commentary |

## 3. Sensitive: `revise`

| Category | Triggers | Required changes |
|---|---|---|
| Financial hype | "100x", "get rich", "risk-free", "passive income in 7 days" | Remove guarantees; give numbers + time frame; add "not financial advice" |
| Medical claims | "Cures anxiety", "no side effects", "lose 10 kg in 7 days" | No cure claims; cite sources; recommend a professional |
| Crypto / NFT | "Presale", "mint now", "airdrop", "memecoin" | Explain utility; disclose holdings or payment; no price targets |
| Politics | Elections, candidates, "rigged" | Facts with sources; nothing unverified about how/when/where to vote |

## 4. Grey zone: `revise` by default, then post

| Situation | Risk | How to make it postable |
|---|---|---|
| Naming a competitor ("better than @X") | Disputes, defamation claims | Verifiable facts only; no insults; consider not naming |
| Hot trend / "BREAKING" | Looks like trend-jacking spam | Only if relevant; no fake "breaking" labels |
| Giveaway | Spam signals if entry = follow + repost + tag | Publish rules, end date, eligibility, selection method |
| AI-generated media | Manipulated-media labels | Say it is AI; never fake real people's actions |
| Superlatives and multipliers ("best on the market", "#1", "10x your…") | Misleading-advertising complaints | Replace with a measured result: number, sample, time frame |

## 5. Commercial slogans

| Status | Examples | Notes |
|---|---|---|
| Allowed | "New planner is out", "Shop now", "Use code SAVE10" | Honest promotion of your own products |
| Careful | "Best tool on the market", "#1 in Vietnam", "Only today" | Superlatives need proof; deadlines must be real |
| Disclose | Paid or gifted promotion | Add `#ad`, `#sponsored` or "Paid partnership". The checker adds a reminder when it sees commercial wording without a tag (it cannot know whether you were paid). |

## 6. Format issues (algorithm, not rules)

These never cause `do_not_post`, but they lower reach or look spammy:

| Issue | Checker threshold | Fix |
|---|---|---|
| Too many hashtags | more than 3 | 1–2 relevant tags |
| Mass mentions | more than 5 `@` | Mention only people involved |
| Link first | URL within the first 40 characters | Hook first, link at the end or in a reply |
| Shouting | more than 70% uppercase letters | Sentence case |
| Too long | over 280 characters | Thread, or X Premium long post |

## 7. Answer template

```
Verdict: allowed | revise | do not post
Risk: low | medium | high
Why:
- ...
How to fix:
- ...
Revised draft:
...
```

## 8. Limits of the automatic checker

`POST /api/post-review` matches keywords and simple patterns. It does not
understand sarcasm, quotation, news reporting, images or languages other
than English (plus a few Vietnamese phrases in the limit check). Treat its
verdict as a first pass and have a person (or the full PROMPT.md assistant)
read anything flagged medium or high.

