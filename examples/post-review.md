# Example: "Help me review this post"

Two parts: a conversation with an LLM running `PROMPT.md`, and the same
draft sent to the local rule-based API. The API output below is copied from
a real run (`POST /api/post-review`, 2026-10-24).

## 1. Conversation (assistant running PROMPT.md)

**User:**
> Can I post this? We launch tomorrow.
>
> "https://mytool.io/launch Our AI tool is the best on the market!! 10x your
> productivity, guaranteed profit for your agency. Use code LAUNCH50 for 50%
> off #ai #saas #growth #startup #marketing"

**Assistant:**

**Verdict: do not post (as written)** · **Risk: high**

Why:
- "Guaranteed profit" is a guaranteed-return claim. That matches X's financial-scam patterns. **Prohibited-risk**, not just low reach.
- "Best on the market" and "10x your productivity" are unproven superlatives. Allowed, but they invite misleading-advertising complaints. **Revise.**
- 5 hashtags and a link in the first line. Not against the rules, but **the algorithm usually shows these less**.
- Promo code without a disclosure tag. Fine for your own product; if anyone was paid to post it, add `#ad`.

How to fix:
- Replace the guarantee and the "10x" with one measured result (number, sample, time frame).
- Keep one hashtag. Move the link to the end or into the first reply.

Revised draft:
> Our AI tool cut weekly reporting time from 6h to 2h for 14 agencies in our
> beta (median, Sep 2026). It drafts, you review.
>
> Launch week: 50% off with code LAUNCH50.
> https://mytool.io/launch #reporting

**Re-check of the revised draft: allowed, risk low.**

## 2. Same drafts through the local API

```bash
curl -s -X POST http://127.0.0.1:8000/api/post-review \
  -H 'Content-Type: application/json' \
  -d '{"text":"https://mytool.io/launch Our AI tool is the best on the market!! 10x your productivity, guaranteed profit for your agency. Use code LAUNCH50 for 50% off #ai #saas #growth #startup #marketing"}'
```

Response (selected fields):

```json
{
  "verdict": "do_not_post",
  "verdict_label": "Do not post",
  "risk": "high",
  "reasons": [
    "Guaranteed-return promises or requests for wallet secrets match common scam patterns.",
    "Superlatives and multiplier claims need proof, or they read as misleading advertising.",
    "Commercial posts are allowed. Paid partnerships must be disclosed. No disclosure tag found; add one if this is paid or gifted.",
    "5 hashtags. More than 2-3 looks spammy and lowers engagement.",
    "The post starts with a link. Link-first posts usually get less reach."
  ],
  "suggestions": [
    "Remove profit guarantees and never ask for keys or seed phrases.",
    "Replace with a measured result: number, sample size, time frame.",
    "If you were paid or received a product, add #ad or 'Paid partnership'.",
    "Keep at most 1-2 relevant hashtags.",
    "Lead with the hook and value; put the link at the end or in a reply."
  ]
}
```

Revised draft:

```json
{
  "verdict": "allowed",
  "verdict_label": "Allowed",
  "risk": "low",
  "reasons": [
    "Commercial posts are allowed. Paid partnerships must be disclosed. No disclosure tag found; add one if this is paid or gifted."
  ],
  "suggestions": [
    "If you were paid or received a product, add #ad or 'Paid partnership'."
  ]
}
```

## 3. A grey-zone draft

**User:** `review: BREAKING: giveaway! RT to win our AI-generated poster pack`

**Assistant (website chat, real output):**

```
Verdict: Revise before posting (risk: medium)
Why:
- Giveaways that require follows/reposts can look like spam if rules and eligibility are missing.
- AI media of real people or events can be labelled as manipulated media.
- Attaching unrelated content to a trend or 'breaking' claim looks like spam.
How to fix:
- Add clear rules, end date, eligibility and how winners are picked; avoid 'follow + repost' as the only entry.
- Say clearly that it is AI-generated and never depict real people doing things they did not do.
- Only join a trend if the post adds something relevant; do not label it 'breaking' unless it is.
Keyword-based check. It can miss context or flag harmless text. X's rules (help.x.com/rules-and-policies) are the authority.
```

A postable version: *"Giveaway: 3 AI-generated poster packs (made with our own model, no real people). Reply with the room you'd hang one in. Ends Oct 31, 23:59 UTC; winners picked at random from replies, open worldwide 18+. Rules: link in reply."*

