"""Turns an uploaded file (CSV/TSV/XLSX/JSON/PDF) or the sample into a dataset:
{source, periods:[prev, cur], m:{metric:[prev, cur]}, assumed:[...]}"""
import csv, io, json, re

# key: (label, unit, good_direction, regex)   good: 1 higher=better, -1 lower=better, 0 neutral
MET = {
    "sales": ("Sales", "₹", 1, r"sales|revenue|gmv"),
    "orders": ("Orders", "#", 1, r"orders?"),
    "cancel": ("Cancellation rate", "%", -1, r"cancel"),
    "asp": ("Average selling price", "₹", 0, r"avg|average|asp|selling price|price per"),
    "oos": ("Out-of-stock products", "#", -1, r"out.?of.?stock|oos|stock.?out|unavailable"),
    "profit": ("Profit", "₹", 1, r"profit"),
    "margin": ("Margin", "%", 1, r"margin"),
    "returns": ("Return rate", "%", -1, r"return|rto"),
    "views": ("Product views", "#", 1, r"views?|impression|visibility|traffic|visits"),
    "listings": ("Active listings", "#", 0, r"listing|active (sku|product)|catalog"),
}
ORDER = ["cancel", "returns", "oos", "margin", "profit", "listings", "views", "asp", "orders", "sales"]


def match_key(s):
    s = str(s or "").strip()
    return next((k for k in ORDER if s and re.search(MET[k][3], s, re.I)), None)


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(\.\d+)?", re.sub(r"[₹$,%\s]", "", str(v or "")))
    return float(m.group()) if m else None


def finalize(m, periods, source, assumed=None):
    for k in ("cancel", "margin", "returns"):          # 0.08 -> 8 %
        if k in m and m[k][0] <= 1 and m[k][1] <= 1:
            m[k] = [m[k][0] * 100, m[k][1] * 100]
    if "margin" not in m and "profit" in m and "sales" in m and all(m["sales"]):
        m["margin"] = [m["profit"][i] / m["sales"][i] * 100 for i in (0, 1)]
    if "asp" not in m and "sales" in m and "orders" in m and all(m["orders"]):
        m["asp"] = [m["sales"][i] / m["orders"][i] for i in (0, 1)]
    if "sales" not in m and "orders" not in m:
        raise ValueError("I couldn't find sales or orders in this file. Use the CSV template: Metric, Last Month, This Month.")
    return {"source": source, "periods": list(periods), "m": m, "assumed": assumed or []}


def from_table(rows, source):
    rows = [[("" if c is None else str(c).strip()) for c in r] for r in rows]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        raise ValueError("The file looks empty.")
    head, m = rows[0], {}
    mr = sum(1 for r in rows[1:] if match_key(r[0]))
    mc = sum(1 for h in head if match_key(h))
    if mr >= 2 and mr >= mc and len(head) >= 3:          # one metric per row
        for r in rows[1:]:
            k = match_key(r[0])
            if not k or k in m or len(r) < 3:
                continue
            a, b = num(r[-2]), num(r[-1])
            if a is not None and b is not None:
                m[k] = [a, b]
        return finalize(m, head[-2:], source)
    if mc >= 2 and len(rows) >= 3:                       # one period per row
        p, c = rows[-2], rows[-1]
        li = next((i for i, h in enumerate(head) if not match_key(h)), None)
        for i, h in enumerate(head):
            k = match_key(h)
            if not k or k in m or i >= len(p) or i >= len(c):
                continue
            a, b = num(p[i]), num(c[i])
            if a is not None and b is not None:
                m[k] = [a, b]
        return finalize(m, [p[li], c[li]] if li is not None else ["Previous", "Current"], source)
    raise ValueError("Couldn't recognise the layout. Use: Metric, Last Month, This Month (one metric per row).")


def from_json(obj, source):
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = list(obj[0])
        return from_table([keys] + [[o.get(k) for k in keys] for o in obj], source)
    if isinstance(obj, dict):
        o, rows = obj.get("metrics", obj), [["Metric", "Previous", "Current"]]
        for k, v in o.items():
            vs = v if isinstance(v, list) else list(v.values()) if isinstance(v, dict) else []
            if len(vs) >= 2:
                rows.append([k, vs[-2], vs[-1]])
        return from_table(rows, source)
    raise ValueError("Unrecognised JSON structure.")


def from_text(text, source):                             # PDF text: "Sales  ₹2,00,000  ₹1,35,000"
    m = {}
    for line in text.splitlines():
        label = re.sub(r"[₹\d,.%\s-]+$", "", line).strip()
        k = match_key((re.split(r"\s{2,}|:", label)[0]) or label)
        nums = [n for n in map(num, re.findall(r"-?\d[\d,]*\.?\d*", line)) if n is not None]
        if k and k not in m and len(nums) >= 2:
            m[k] = [nums[-2], nums[-1]]
    return finalize(m, ["Previous", "Current"], source)


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)


def parse_file(name: str, data: bytes):
    ext = name.rsplit(".", 1)[-1].lower()
    if ext in ("csv", "tsv"):
        text = data.decode("utf-8-sig", errors="replace")
        return from_table(list(csv.reader(io.StringIO(text), delimiter="\t" if ext == "tsv" else ",")), name)
    if ext == "json":
        return from_json(json.loads(data.decode("utf-8-sig")), name)
    if ext in ("xlsx", "xls"):
        from openpyxl import load_workbook
        ws = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
        return from_table(list(ws.iter_rows(values_only=True)), name)
    if ext == "pdf":
        return from_text(pdf_text(data), name)
    raise ValueError("Unsupported file type. Use CSV, Excel, JSON or PDF.")


def sample_data():
    """Assignment data + clearly flagged assumptions (profit, margin, views, listings)."""
    return finalize({
        "sales": [200000, 135000], "orders": [400, 270], "cancel": [8, 14], "asp": [500, 500], "oos": [5, 18],
        "profit": [36000, 16200], "margin": [18, 12], "views": [52000, 47000], "listings": [40, 40],
    }, ["Last month", "This month"], "Sample dataset (mock seller)", ["profit", "margin", "views", "listings"])
