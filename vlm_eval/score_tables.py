#!/usr/bin/env python3
"""Score a VLM-extracted table against the ground truth.

    python3 score_tables.py pie     predictions/pie.csv
    python3 score_tables.py bar     predictions/bar.csv
    python3 score_tables.py scatter predictions/scatter.csv
    python3 score_tables.py line    predictions/line.csv
    python3 score_tables.py heatmap predictions/heatmap.csv   [--json result.json]

pie / bar / line / heatmap
           rows are matched by their label columns (pie: Genre; bar: Clarity; line: Country + Year;
           heatmap: Year + Month — text fuzzy, numbers exact, month names or abbreviations both accepted);
           for every numeric column present in both tables: MAE, mean relative error, and "relaxed accuracy"
           = share of values within 5 % (ChartQA convention), plus row recall/precision.
scatter    points are matched one-to-one within each species by nearest neighbour in axis-normalised
           coordinates; reports count recall, per-axis MAE and share of points within 5 % of the axis range.
Standard library only.
"""
import argparse
import csv
import difflib
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GT = os.path.join(os.path.dirname(HERE), "ground_truth")
FILES = {"pie": "pie_vgsales_genre.csv", "bar": "bar_diamonds_clarity.csv", "scatter": "scatter_penguins.csv",
         "line": "line_gapminder_lifeexp.csv", "heatmap": "heatmap_air_passengers.csv"}
LABEL = {"pie": ["Genre"], "bar": ["Clarity"], "line": ["Country", "Year"], "heatmap": ["Year", "Month"]}   # text keys fuzzy, numeric keys exact
SKIP = {"bar": ["Diamonds"]}   # ground-truth columns the chart does not encode (not scored)
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
RELAXED = 0.05


def read(path):
    text = open(path, encoding="utf-8").read()
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", text, re.S)        # tolerate answers wrapped in ``` fences
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
    for m in MONTHS:                       # "Jan", "January", "jan." -> "jan"
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
            used.add(best)
            matches.append((g, pred[best]))
    res = {"rows_true": len(gt), "rows_pred": len(pred), "rows_matched": len(matches),
           "row_recall": round(len(matches) / len(gt), 3), "row_precision": round(len(matches) / len(pred), 3) if pred else 0.0,
           "columns": {}}
    for c in cols:
        errs, rel, ok = [], [], 0
        for g, p in matches:
            gv, pv = num(g[c]), num(p.get(c))
            if gv is None or pv is None:
                continue
            errs.append(abs(pv - gv))
            r = abs(pv - gv) / abs(gv) if gv else (0.0 if pv == 0 else 1.0)
            rel.append(r)
            ok += r <= RELAXED
        n = len(errs)
        res["columns"][c] = {"n": n, "mae": round(sum(errs) / n, 4) if n else None,
                             "mean_rel_error": round(sum(rel) / n, 4) if n else None,
                             "relaxed_accuracy": round(ok / len(gt), 3)}   # unmatched rows count as wrong
    res["missing"] = [" ".join(g[k] for k in keys) for g in gt if all(g is not m[0] for m in matches)]
    return res


def score_scatter(gt, pred):
    axes = ["Bill_length_mm", "Flipper_length_mm", "Body_mass_g"]
    ranges = {a: (max(num(r[a]) for r in gt) - min(num(r[a]) for r in gt)) or 1.0 for a in axes}
    res = {"points_true": len(gt), "points_pred": len(pred), "by_species": {}, "axes": {}}
    pairs = []
    for sp in sorted({r["Species"] for r in gt}):
        g = [r for r in gt if r["Species"] == sp]
        p = [r for r in pred if norm(r.get("Species", "")) == norm(sp) and all(num(r.get(a)) is not None for a in axes)]
        cand = []
        for i, a in enumerate(g):
            for j, b in enumerate(p):
                d = math.sqrt(sum(((num(a[x]) - num(b[x])) / ranges[x]) ** 2 for x in axes))
                cand.append((d, i, j))
        ug, up = set(), set()
        for d, i, j in sorted(cand):
            if i in ug or j in up:
                continue
            ug.add(i); up.add(j); pairs.append((g[i], p[j]))
        res["by_species"][sp] = {"true": len(g), "pred": len(p), "matched": len(ug)}
    res["point_recall"] = round(len(pairs) / len(gt), 3)
    res["point_precision"] = round(len(pairs) / len(pred), 3) if pred else 0.0
    for a in axes:
        e = [abs(num(p[a]) - num(g[a])) for g, p in pairs]
        res["axes"][a] = {"mae": round(sum(e) / len(e), 3) if e else None,
                          "within_5pct_of_range": round(sum(x <= RELAXED * ranges[a] for x in e) / len(gt), 3)}
    res["all_axes_within_5pct"] = round(sum(all(abs(num(p[a]) - num(g[a])) <= RELAXED * ranges[a] for a in axes) for g, p in pairs) / len(gt), 3)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("chart", choices=sorted(FILES))
    ap.add_argument("prediction")
    ap.add_argument("--truth", help="ground-truth CSV (default: ../ground_truth/<chart file>)")
    ap.add_argument("--json", help="write the result here")
    a = ap.parse_args()
    gt = read(a.truth or os.path.join(GT, FILES[a.chart]))
    pred = read(a.prediction)
    res = score_scatter(gt, pred) if a.chart == "scatter" else score_labeled(a.chart, gt, pred)
    res = {"chart": a.chart, "prediction": a.prediction, **res}
    print(json.dumps(res, indent=2))
    if a.json:
        json.dump(res, open(a.json, "w"), indent=2)


if __name__ == "__main__":
    sys.exit(main())
