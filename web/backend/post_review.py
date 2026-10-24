"""Rule-based pre-posting review.

This is a keyword and format heuristic, not a moderation model. It flags
likely problems so a human can decide; it can miss context (sarcasm,
quotes, news reporting) and can flag harmless text. The categories and
verdicts follow docs/content-policy.md.

Verdicts: "allowed", "revise", "do_not_post". Risk: "low", "medium", "high".
"""

import re

MAX_POST_CHARS = 280  # standard limit for non-Premium accounts

# (category id, label, level, pattern, reason, suggestion)
# level: "prohibited" -> do_not_post/high, "sensitive" -> revise/medium,
#        "grey" -> revise/low-medium, "commercial" -> allowed + disclosure check
RULES = [
    # --- Prohibited or high risk -------------------------------------------
    ("violence", "Violent threats", "prohibited",
     r"\b(i('| wi)ll|gonna|going to) (kill|shoot|stab|hurt|beat up)\b|\b(kill|shoot) (you|him|her|them)\b"
     r"|\bbomb (the|your|their)\b|\bdeserves? to die\b",
     "Threats or wishes of violence violate X's Violent Speech policy.",
     "Remove the threat. If you are describing news, quote the source and make the reporting context explicit."),
    ("hate", "Hateful conduct", "prohibited",
     r"\b(subhuman|vermin|go back to (your|their) country|should be (exterminated|wiped out))\b",
     "Dehumanising language about a group violates X's Hateful Conduct policy.",
     "Criticise ideas or actions, never a protected group."),
    ("minors", "Minors in a sexual or exploitative context", "prohibited",
     r"\b(minor|underage|teen|child|kid|loli|schoolgirl)s?\b.{0,40}\b(sexy|nude|nsfw|hot|lewd)\b"
     r"|\b(sexy|nude|nsfw|hot|lewd)\b.{0,40}\b(minor|underage|teen|child|kid|loli|schoolgirl)s?\b",
     "Any sexualised content involving minors is prohibited and reportable.",
     "Do not post. This cannot be fixed by rewording."),
    ("adult", "Adult content", "prohibited",
     r"\b(nsfw|nudes?|porn|onlyfans|explicit content|18\+ only)\b",
     "Adult content must be marked sensitive, cannot be in profile/header images, and is not promoted. Not suitable for growth posts.",
     "Keep growth posts safe-for-work. Move adult material off the promoted account."),
    ("scam", "Scam or fraud pattern", "prohibited",
     r"\b(guaranteed (returns?|profit|income)|double your (money|btc|eth|crypto)|send (me )?\d*\s*(btc|eth|usdt|sol)"
     r"|seed phrase|private key|recovery phrase|claim your (airdrop|reward) now|wallet (drainer|connect to claim))\b",
     "Guaranteed-return promises or requests for wallet secrets match common scam patterns.",
     "Remove profit guarantees and never ask for keys or seed phrases."),
    ("impersonation", "Impersonation", "prohibited",
     r"\b(official (x|twitter) support|x support team|verify your account (here|now)|your account will be suspended)\b",
     "Pretending to be X or another brand violates the Misleading and Deceptive Identities policy.",
     "Speak as yourself. Link to help.x.com instead of imitating support."),
    ("private_info", "Private information", "prohibited",
     r"\b(home address|lives at|doxx?|his phone number|her phone number|their phone number)\b"
     r"|(?<![\w+])(\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
     r"|(?<![\w+])\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)",
     "Sharing someone's phone number, address or other private details violates the Private Information policy.",
     "Remove personal contact details. Use a business contact page if needed."),
    ("spam", "Platform manipulation / spam", "prohibited",
     r"\b(follow for follow|f4f|follow back (guaranteed|100%)|buy (followers|likes|retweets|views)|engagement pod"
     r"|like for like|l4l)\b",
     "Follow-trains and bought engagement violate the Platform Manipulation and Spam policy.",
     "Grow with original posts and real replies instead. See docs/growth-playbook.md."),
    ("copyright", "Copyright infringement", "prohibited",
     r"\b(full movie|free download|leaked (album|episode|course)|cracked|torrent|watch .{0,30} free online)\b",
     "Distributing copyrighted material without permission can lead to DMCA takedowns and strikes.",
     "Link to the official source or share a short commentary instead."),

    # --- Sensitive: revise ----------------------------------------------------
    ("finance_hype", "Financial hype", "sensitive",
     r"\b(\d{2,}x (gains?|returns?)|get rich|passive income|financial freedom in|risk[- ]free|to the moon|can't lose)\b",
     "Exaggerated financial claims attract reports and can breach financial-promotion rules.",
     "State results with numbers and a time frame, add 'not financial advice', remove guarantees."),
    ("medical", "Medical claims", "sensitive",
     r"\b(cures?|treats?|heals?|reverses?) (cancer|diabetes|covid|anxiety|depression|autism)\b"
     r"|\bno side effects\b|\blose \d+ ?(kg|lbs?|pounds) in \d+ ?(days?|weeks?)\b|\bdoctors hate\b",
     "Health claims without evidence fall under misleading health content.",
     "Cite a credible source, avoid cure/guarantee language, suggest consulting a professional."),
    ("crypto", "Crypto / NFT", "sensitive",
     r"\b(nft|presale|pre-sale|token launch|mint (now|live)|airdrop|memecoin|100x gem|ico)\b",
     "Crypto and NFT promotions carry high scam association and are restricted for ads.",
     "Explain what the project does, disclose your involvement, remove price predictions."),
    ("politics", "Political content", "sensitive",
     r"\b(election|vote for|candidate|ballot|political party|rigged)\b",
     "Political posts are allowed but draw reports and civic-integrity scrutiny.",
     "Stick to verifiable facts, link sources, avoid claims about voting procedures you cannot verify."),

    # --- Grey zone: revise by default --------------------------------------
    ("competitor", "Competitor comparison", "grey",
     r"\b(better than|unlike|worse than|vs\.?|versus|switch from)\s+@?\w+",
     "Comparisons with named competitors invite disputes and possible defamation claims.",
     "Compare on verifiable facts and avoid insults; consider not naming the competitor."),
    ("giveaway", "Giveaway", "grey",
     r"\b(giveaway|rt to win|retweet to win|repost to win|tag \d+ friends|follow \+ (rt|repost))\b",
     "Giveaways that require follows/reposts can look like spam if rules and eligibility are missing.",
     "Add clear rules, end date, eligibility and how winners are picked; avoid 'follow + repost' as the only entry."),
    ("ai_content", "AI-generated media", "grey",
     r"\b(ai[- ]generated|midjourney|stable diffusion|dall-?e|made with ai|generated with)\b",
     "AI media of real people or events can be labelled as manipulated media.",
     "Say clearly that it is AI-generated and never depict real people doing things they did not do."),
    ("hot_trend", "Trend-jacking", "grey",
     r"\b(trending|breaking:?|viral)\b",
     "Attaching unrelated content to a trend or 'breaking' claim looks like spam.",
     "Only join a trend if the post adds something relevant; do not label it 'breaking' unless it is."),

    ("superlative", "Unproven superlative", "grey",
     r"\b(best (\w+ )?(on the market|in the world|ever)|number one|the only (tool|app|product)|\d{2,}x (your|more|faster|productivity))\b|(?<!\w)#1\b",
     "Superlatives and multiplier claims need proof, or they read as misleading advertising.",
     "Replace with a measured result: number, sample size, time frame."),

    # --- Commercial ------------------------------------------------------------
    ("commercial", "Commercial / promotional", "commercial",
     r"\b(buy now|shop now|discount|use code|promo code|\d+% off|limited offer|sign up today|link in bio|sponsored|affiliate)\b",
     "Commercial posts are allowed. Paid partnerships must be disclosed.",
     "If you were paid or received a product, add #ad or 'Paid partnership'."),
]

COMPILED = [(cid, label, level, re.compile(pat, re.I), reason, fix)
            for cid, label, level, pat, reason, fix in RULES]

DISCLOSURE_RE = re.compile(
    r"(#ad(?![\w-])|#sponsored(?![\w-])|paid partnership|(?<!\w)ad:|\bpartnered with\b|#collab(?![\w-]))", re.I)
HASHTAG_RE = re.compile(r"(?<!\w)#\w+")
MENTION_RE = re.compile(r"(?<!\w)@\w{1,15}")
URL_RE = re.compile(r"https?://\S+|\b\w+\.(com|io|net|org|xyz|ly)/\S*", re.I)


def _risk_rank(r):
    return {"low": 0, "medium": 1, "high": 2}[r]


def review(text):
    """Review a draft post. Returns a dict; raises ValueError on bad input."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' is required and must be a non-empty string.")
    text = text.strip()
    if len(text) > 25000:
        raise ValueError("'text' is too long (max 25000 characters).")

    matched = []
    reasons = []
    suggestions = []
    verdict = "allowed"
    risk = "low"
    paid_partnership_disclosed = bool(DISCLOSURE_RE.search(text))

    def bump(v, r):
        nonlocal verdict, risk
        order = {"allowed": 0, "revise": 1, "do_not_post": 2}
        if order[v] > order[verdict]:
            verdict = v
        if _risk_rank(r) > _risk_rank(risk):
            risk = r

    for cid, label, level, pattern, reason, fix in COMPILED:
        m = pattern.search(text)
        if not m:
            continue
        matched.append({"category": cid, "label": label, "level": level, "match": m.group(0)})
        if level == "prohibited":
            bump("do_not_post", "high")
            reasons.append(reason)
            suggestions.append(fix)
        elif level == "sensitive":
            bump("revise", "medium")
            reasons.append(reason)
            suggestions.append(fix)
        elif level == "grey":
            bump("revise", "low" if cid in ("hot_trend", "ai_content") else "medium")
            reasons.append(reason)
            suggestions.append(fix)
        elif level == "commercial":
            if not paid_partnership_disclosed:
                reasons.append(reason + " No disclosure tag found; add one if this is paid or gifted.")
                suggestions.append(fix)
            else:
                reasons.append("Commercial post with a disclosure tag.")

    # Format heuristics (affect reach and spam signals, not legality).
    hashtags = HASHTAG_RE.findall(text)
    mentions = MENTION_RE.findall(text)
    urls = [m for m in URL_RE.finditer(text)]
    letters = [c for c in text if c.isalpha()]
    caps_ratio = (sum(c.isupper() for c in letters) / len(letters)) if letters else 0

    if len(hashtags) > 3:
        bump("revise", "low")
        reasons.append("{} hashtags. More than 2-3 looks spammy and lowers engagement.".format(len(hashtags)))
        suggestions.append("Keep at most 1-2 relevant hashtags.")
    if len(mentions) > 5:
        bump("revise", "medium")
        reasons.append("{} mentions. Mass-mentioning accounts is a spam signal.".format(len(mentions)))
        suggestions.append("Mention only people directly involved.")
    if urls and urls[0].start() < 40:
        reasons.append("The post starts with a link. Link-first posts usually get less reach.")
        suggestions.append("Lead with the hook and value; put the link at the end or in a reply.")
    if len(letters) >= 20 and caps_ratio > 0.7:
        bump("revise", "low")
        reasons.append("Mostly uppercase text reads as shouting and spam.")
        suggestions.append("Use normal sentence case; emphasise one or two words at most.")
    if len(text) > MAX_POST_CHARS:
        reasons.append("{} characters. Over {} needs X Premium or a thread.".format(len(text), MAX_POST_CHARS))
        suggestions.append("Split into a thread: hook in post 1, proof in 2-4, call to action last.")

    if not reasons:
        reasons.append("No policy or format issues detected by the rule check.")

    labels = {
        "allowed": "Allowed",
        "revise": "Revise before posting",
        "do_not_post": "Do not post",
    }
    return {
        "verdict": verdict,
        "verdict_label": labels[verdict],
        "risk": risk,
        "reasons": _dedupe(reasons),
        "suggestions": _dedupe(suggestions),
        "matched": matched,
        "stats": {
            "characters": len(text),
            "hashtags": len(hashtags),
            "mentions": len(mentions),
            "links": len(urls),
            "paid_partnership_disclosed": paid_partnership_disclosed,
        },
        "disclaimer": (
            "Keyword-based check. It can miss context or flag harmless text. "
            "X's rules (help.x.com/rules-and-policies) are the authority."
        ),
    }


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out

