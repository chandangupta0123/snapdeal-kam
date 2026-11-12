"""Rule-based diagnosis: finds what changed, ranks issues, picks follow-up questions and recommendations."""
import re
from .data_loader import MET

n = lambda x: int(round(x))
p1 = lambda x: f"{round(x, 1):g}"


def grp(v):  # Indian digit grouping: 2,00,000
    s = str(abs(n(v)))
    if len(s) > 3:
        s = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) + "," + s[-3:]
    return ("-" if v < 0 else "") + s


def fmt(k, v):
    u = MET[k][1]
    return "₹" + grp(v) if u == "₹" else p1(v) + "%" if u == "%" else grp(v)


def describe(ds):
    """Rows for the UI: formatted values + change chip."""
    rows = []
    for k, (label, unit, good, _) in MET.items():
        if k not in ds["m"]:
            continue
        p, c = ds["m"][k]
        d = (c - p) if unit == "%" else ((c - p) / p * 100 if p else 0)
        cls = "flat" if abs(d) < 0.5 or (good == 0 and abs(d) < 5) else "up" if good * d > 0 else "down"
        rows.append({"key": k, "label": label, "prev": fmt(k, p), "cur": fmt(k, c), "assumed": k in ds["assumed"],
                     "chg": f"{'+' if d >= 0 else ''}{p1(d)}{' pts' if unit == '%' else '%'}", "cls": cls})
    return rows


def _g(ds, k):
    a = ds["m"].get(k)
    if not a:
        return None
    return {"p": a[0], "c": a[1], "abs": a[1] - a[0], "pct": (a[1] - a[0]) / a[0] * 100 if a[0] else 0}


REC = {
    "stock": {"title": "Restock your top sellers first", "say": "Restock the products that drove most of last month's orders. Set a low stock alert, and mark items you cannot restock as inactive so they stop taking orders you cannot fulfil"},
    "cancel": {"title": "Bring cancellations back under control", "say": "Sync inventory every day, dispatch within the promised time, and check cancellation reasons in your seller panel every week"},
    "visibility": {"title": "Win back visibility and conversion", "say": "Compare your price with top competitors on your ten best sellers, refresh titles and photos, and put a small ad budget or a Snapdeal promotion behind the restocked products"},
    "margin": {"title": "Protect your margin", "say": "Review discounts and shipping cost on low margin products, and avoid price cuts on items that already sell well"},
    "returns": {"title": "Reduce returns", "say": "Fix product descriptions and photos so they match what you ship, and check packaging for damaged returns"},
}


def analyze(ds):
    S, O, C, A, X, M, V, R, L = (_g(ds, k) for k in ("sales", "orders", "cancel", "asp", "oos", "margin", "views", "returns", "listings"))
    I, head = [], O or S
    flat_price = A and abs(A["pct"]) < 5
    if head and head["pct"] <= -5:
        fell = f"orders fell {p1(abs(O['pct']))} percent, from {n(O['p'])} to {n(O['c'])}" if O else f"sales fell {p1(abs(S['pct']))} percent"
        I.append({"key": "volume", "sev": min(90, -head["pct"] * 1.5), "title": f"{'Orders' if O else 'Sales'} down {p1(abs(head['pct']))}%",
                  "say": fell + (", while your average selling price stayed the same, so this is a volume problem and not a pricing one" if flat_price else "")})
    if X and X["c"] > X["p"]:
        share = n(X["c"] / L["c"] * 100) if L and L["c"] else None
        I.append({"key": "stock", "sev": min(100, 40 + (X["c"] - X["p"]) * 3), "title": f"Out-of-stock products rose from {n(X['p'])} to {n(X['c'])}",
                  "say": f"out of stock products jumped from {n(X['p'])} to {n(X['c'])}" + (f", roughly {share} percent of your listings" if share else ""),
                  "q": "Are your best-selling products among the ones that are out of stock?"})
    if C and C["abs"] >= 2:
        I.append({"key": "cancel", "sev": min(100, 30 + C["abs"] * 8), "title": f"Cancellations rose from {p1(C['p'])}% to {p1(C['c'])}%",
                  "say": f"cancellations rose from {p1(C['p'])} to {p1(C['c'])} percent",
                  "q": "What reasons are you seeing for the cancellations: stock not available, late dispatch, or customers changing their mind?"})
    if A and abs(A["pct"]) >= 5:
        I.append({"key": "price", "sev": 60, "title": f"Average price {'up' if A['pct'] > 0 else 'down'} {p1(abs(A['pct']))}%",
                  "say": f"your average selling price moved {p1(abs(A['pct']))} percent", "q": "Are competitors now selling similar items cheaper than you?"})
    if V and V["pct"] <= -10:
        I.append({"key": "views", "sev": min(70, -V["pct"] * 2), "title": f"Product views down {p1(abs(V['pct']))}%", "say": f"product views dropped {p1(abs(V['pct']))} percent"})
    if V and O and O["pct"] < V["pct"] - 10:
        I.append({"key": "conversion", "sev": 68, "title": "Visitors are not converting",
                  "say": "orders are falling much faster than views, so shoppers are seeing your products but not buying. That usually means unavailable stock or an uncompetitive price"})
    if M and M["abs"] <= -2:
        I.append({"key": "margin", "sev": 45, "title": f"Margin down from {n(M['p'])}% to {n(M['c'])}%", "say": f"your margin slipped from {n(M['p'])} to {n(M['c'])} percent"})
    if R and R["abs"] >= 2:
        I.append({"key": "returns", "sev": 40, "title": f"Return rate up to {p1(R['c'])}%", "say": f"return rate rose to {p1(R['c'])} percent",
                  "q": "Customers are returning more items. What are the main reasons?"})
    I.sort(key=lambda i: -i["sev"])
    qs = [{"key": i["key"], "q": i["q"]} for i in I if "q" in i][:2]
    qs.append({"key": "changes", "q": "In the last month, did you change prices, listing photos or titles, or pause any ads or promotions?"})
    an = {"I": I, "qs": qs, "O": O, "C": C, "X": X}
    an["recs"] = recommend(an)
    return an


def recommend(an):
    mp, out = {"stock": "stock", "cancel": "cancel", "price": "visibility", "views": "visibility", "conversion": "visibility", "margin": "margin", "returns": "returns"}, []
    for i in an["I"]:
        r = mp.get(i["key"])
        if r and r not in out:
            out.append(r)
    for r in ("visibility", "cancel", "stock"):
        if len(out) < 3 and r not in out:
            out.append(r)
    return [REC[k] for k in out[:3]]


def local_summary(an):
    issues = [i["title"] for i in an["I"] if i["key"] != "views"][:3] or ["No major decline found in the data"]
    nxt = []
    if an["X"] and an["X"]["c"] > an["X"]["p"]:
        nxt.append("Restock best sellers within 48 hours")
    if an["C"] and an["C"]["abs"] >= 2:
        nxt.append("Review cancellation reasons in Seller Panel this week")
    tgt = f"target about {n(an['O']['p'] * 0.9)} orders" if an["O"] else "target last month's sales"
    nxt.append(f"Re-check your numbers in 7 days: {tgt}" + (f" and cancellations under {p1(an['C']['p'])}%" if an["C"] else ""))
    return {"issues": issues, "actions": [r["title"] for r in an["recs"]], "next_steps": nxt[:3]}


def spoken_summary(s, lang="en-IN"):
    if lang == "hi-IN":
        return f"सारांश: {'; '.join(s['issues'])}। सुझाव: {'; '.join(s['actions'])}। अगले कदम: {'; '.join(s['next_steps'])}। धन्यवाद।"
    return (f"To summarise. The main issues are: {'; '.join(s['issues'])}. I recommend: {'; '.join(s['actions'])}. "
            f"Next steps: {'; '.join(s['next_steps'])}. Thank you for calling Snapdeal, and all the best for your sales.")


def data_brief(ds, an):
    lines = []
    for k, (p, c) in ds["m"].items():
        d = (c - p) / p * 100 if p else 0
        lines.append(f"- {MET[k][0]}: {fmt(k, p)} -> {fmt(k, c)} ({'+' if d >= 0 else ''}{d:.1f}%)")
    return (f"Periods: {ds['periods'][0]} vs {ds['periods'][1]}\n" + "\n".join(lines) +
            f"\nAuto-diagnosis (ranked): {' | '.join(i['title'] for i in an['I']) or 'none'}\nAssumed/mock fields: {', '.join(ds['assumed']) or 'none'}")
