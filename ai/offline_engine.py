"""Scripted fallback KAM (no API key / quota exhausted). Stateless: the turn is derived from history."""
import re

CLOSE = re.compile(r"bye|that'?s all|thank|nothing else|no more|done|\bend\b|\bno\b|nahi")


def _ack(key, t):
    t = t.lower()
    if key == "stock":
        if re.search(r"\b(yes|yeah|yep|haan|ha|bestsell|top|main|popular)", t):
            return "That explains a lot. When top sellers go out of stock, you lose orders and your search ranking too. "
        if re.search(r"\b(no|nope|nahi)\b", t):
            return "Okay, so it is mostly slower products, but it still hurts how complete your catalogue looks. "
    if key == "cancel":
        if re.search(r"stock|inventory", t): return "So stock-outs are directly causing cancellations. Fixing stock will fix both problems. "
        if re.search(r"late|delay|dispatch|ship|courier|pickup", t): return "Late dispatch is a common reason, and it is fixable. "
        if re.search(r"customer|buyer|mind|cod|cash", t): return "Customer-side cancellations, especially cash on delivery, can be reduced by confirming orders. "
    if key == "changes":
        if re.search(r"ad|promotion|campaign|stopp|paus", t): return "Pausing ads or promotions can cut traffic quickly. "
        if re.search(r"price|discount", t): return "Price changes can shift conversion, so we should check that against competitors. "
        if re.search(r"\b(no|nope|nahi|nothing)\b", t): return "Okay, so nothing you changed caused this, and the stock and cancellation issues are the likely drivers. "
    return "Got it. "


def reply(history, an):
    users = [m["text"] for m in history if m["role"] == "user"]
    n, last, qs = len(users), users[-1], an["qs"]
    if n == 1:
        vol = next((i for i in an["I"] if i["key"] == "volume"), None)
        rest = [i for i in an["I"] if i["key"] not in ("volume", "views")][:2]
        found = (f"I can see {vol['say']}. " if vol else "") + (
            f"Two things stand out: {', and '.join(i['say'].split('. ')[0] for i in rest)}. " if rest else ("" if vol else "I could not find a clear decline in your data. "))
        return {"text": f"Thanks for telling me, and I'm sorry, a drop like this is stressful. I checked your account. {found}{qs[0]['q']}"}
    i = n - 2                                           # question the seller just answered
    if i < len(qs):
        ack = _ack(qs[i]["key"], last)
        if i + 1 < len(qs):
            return {"text": ack + qs[i + 1]["q"]}
        w = ["First", "Second", "Third"]
        recs = " ".join(f"{w[j]}, {r['say'][0].lower() + r['say'][1:]}." for j, r in enumerate(an["recs"]))
        return {"text": f"{ack}Here is what I recommend. {recs} Anything else you would like to ask, or shall I summarise?"}
    if CLOSE.search(last.lower()):
        return {"wrap": True}
    return {"text": "Happy to help more. You can ask about stock, cancellations or pricing, or say that is all and I will summarise."}
