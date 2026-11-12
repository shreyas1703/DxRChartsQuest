import csv, difflib, io, math, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
GT = os.path.join(os.path.dirname(HERE), "ground_truth")
FILES = {"pie": "pie_vgsales_genre.csv", "bar": "bar_diamonds_clarity.csv", "scatter": "scatter_penguins.csv",
         "line": "line_gapminder_lifeexp.csv", "heatmap": "heatmap_air_passengers.csv"}
LABEL = {"pie": ["Genre"], "bar": ["Clarity"], "line": ["Country", "Year"], "heatmap": ["Year", "Month"]}
SKIP = {}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
RELAXED = 0.05
def read(path):
    text = open(path, encoding="utf-8").read()
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]
def num(v):
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None
def norm(s):
    n = re.sub(r"[^a-z0-9]", "", s.lower())
    for m in MONTHS:
        if len(n) >= 3 and m.startswith(n) or n == m:
            return m[:3]
    return n
def score_labeled(kind, gt, pred):
    keys = LABEL[kind]
    cols = [c for c in gt[0] if c not in keys and c != "Rank" and c not in SKIP.get(kind, []) and c in (pred[0] if pred else {})]
    used, matches = set(), []
    for g in gt:
        best, best_r = None, 0.0
        for i, p in enumerate(pred):
            if i in used or any(k not in p for k in keys):
                continue
            r = 1.0
            for k in keys:
                gn, pn = num(g[k]), num(p[k])
                if gn is not None:
                    r = min(r, 1.0 if pn == gn else 0.0)
                else:
                    r = min(r, difflib.SequenceMatcher(None, norm(g[k]), norm(p[k])).ratio())
            if r > best_r:
                best, best_r = i, r
        if best is not None and best_r >= 0.8:
            used.add(best); matches.append((g, pred[best]))
    res = {"rows_true": len(gt), "rows_pred": len(pred), "rows_matched": len(matches),
           "row_recall": round(len(matches) / len(gt), 3), "row_precision": round(len(matches) / len(pred), 3) if pred else 0.0, "columns": {}}
    for c in cols:
        errs, rel, ok = [], [], 0
        for g, p in matches:
            gv, pv = num(g[c]), num(p.get(c))
            if gv is None or pv is None:
                continue
            errs.append(abs(pv - gv)); r = abs(pv - gv) / abs(gv) if gv else (0.0 if pv == 0 else 1.0); rel.append(r); ok += r <= RELAXED
        n = len(errs)
        res["columns"][c] = {"n": n, "mae": round(sum(errs) / n, 4) if n else None, "mean_rel_error": round(sum(rel) / n, 4) if n else None,
                             "relaxed_accuracy": round(ok / len(gt), 3)}
    return res
def score_scatter(gt, pred):
    axes = ["Bill_length_mm", "Flipper_length_mm", "Body_mass_g"]
    ranges = {a: (max(num(r[a]) for r in gt) - min(num(r[a]) for r in gt)) or 1.0 for a in axes}
    res = {"points_true": len(gt), "points_pred": len(pred), "by_species": {}, "axes": {}}
    pairs = []
    for sp in sorted({r["Species"] for r in gt}):
        g = [r for r in gt if r["Species"] == sp]
        p = [r for r in pred if norm(r.get("Species", "")) == norm(sp) and all(num(r.get(a)) is not None for a in axes)]
        cand = sorted((math.sqrt(sum(((num(a[x]) - num(b[x])) / ranges[x]) ** 2 for x in axes)), i, j) for i, a in enumerate(g) for j, b in enumerate(p))
        ug, up = set(), set()
        for d, i, j in cand:
            if i in ug or j in up:
                continue
            ug.add(i); up.add(j); pairs.append((g[i], p[j]))
    res["point_recall"] = round(len(pairs) / len(gt), 3)
    res["all_axes_within_5pct"] = round(sum(all(abs(num(p[a]) - num(g[a])) <= RELAXED * ranges[a] for a in axes) for g, p in pairs) / len(gt), 3)
    return res
def score_line(gt, pred, year_tol=2.5):
    series = {}
    for r in gt:
        series.setdefault(norm(r["Country"]), []).append((num(r["Year"]), num(r["Life_expectancy"]), r))
    for k in series:
        series[k].sort(key=lambda t: t[0])
    res = {}; curve = []
    for k, pts in series.items():
        p = [r for r in pred if norm(r.get("Country", "")) == k and num(r.get("Year")) is not None and num(r.get("Life_expectancy")) is not None]
        lo, hi = pts[0][0], pts[-1][0]
        for b in p:
            x = num(b["Year"])
            if x < lo - year_tol or x > hi + year_tol:
                continue
            x = min(max(x, lo), hi)
            for (x0, y0, _), (x1, y1, _) in zip(pts, pts[1:]):
                if x0 <= x <= x1:
                    curve.append((y0 + (y1 - y0) * ((x - x0) / (x1 - x0) if x1 > x0 else 0), num(b["Life_expectancy"]))); break
    res["series_found"] = sum(1 for k in series if any(norm(r.get("Country", "")) == k for r in pred))
    res["series_true"] = len(series)
    if curve:
        res["curve_mean_rel_error"] = round(sum(abs(p - t) / t for t, p in curve) / len(curve), 4)
        res["curve_within_5pct"] = round(sum(abs(p - t) <= RELAXED * t for t, p in curve) / len(curve), 3)
    return res


def score_linexy(gt, pred):
    """Any line chart (header Series,X,Y): every true point vs the model's value at the same x. A point the model left
    out counts as wrong; only if the model wrote different x values altogether is its curve interpolated."""
    cols_g, cols_p = list(gt[0].keys()), (list(pred[0].keys()) if pred else [])
    s_g, x_g, y_g = cols_g[:3]
    s_p, x_p, y_p = (cols_p + ["", "", ""])[:3]
    series = {}
    for r in gt:
        series.setdefault(norm(r[s_g]), []).append((num(r[x_g]), num(r[y_g])))
    ok = n = found = 0
    rel = []
    for k, pts in series.items():
        p = sorted((num(r.get(x_p)), num(r.get(y_p))) for r in pred if norm(r.get(s_p, "")) == k
                   and num(r.get(x_p)) is not None and num(r.get(y_p)) is not None)
        found += bool(p)
        aligned = sum(any(abs(a - x) < 1e-6 + 0.01 * abs(x) for a, _ in p) for x, _ in pts) >= len(pts) / 2
        for x, t in pts:
            n += 1
            v = next((b for a, b in p if abs(a - x) < 1e-6 + 0.01 * abs(x)), None)
            if v is None and not aligned:
                for (a0, b0), (a1, b1) in zip(p, p[1:]):
                    if a0 <= x <= a1 and a1 > a0:
                        v = b0 + (b1 - b0) * (x - a0) / (a1 - a0)
            if v is None or not t:
                continue
            e = abs(v - t) / abs(t)
            rel.append(e); ok += e <= RELAXED
    res = {"series_found": found, "series_true": len(series), "points_true": n, "points_read": len(rel)}
    res["curve_within_5pct"] = round(ok / n, 3) if n else 0.0
    res["curve_mean_rel_error"] = round(sum(rel) / len(rel), 4) if rel else None
    return res
