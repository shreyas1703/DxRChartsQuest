#!/usr/bin/env python3
"""Check every mark the real DxR code built (headless dump) against the ground-truth tables.

    python3 verify_dumps.py DUMP_DIR          # DUMP_DIR = <out>/dump written by headless/run_headless.sh

Reads each chart's geometry back into data values (inverting the inferred DxR scales) and compares
with ../ground_truth/*.csv. Exit code = number of failing charts. Standard library only.
"""
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GT = os.path.join(ROOT, "ground_truth")


def gt(name):
    return list(csv.DictReader(open(os.path.join(GT, name), encoding="utf-8")))


def load(dump, stem):
    d = json.load(open(os.path.join(dump, stem + ".json")))
    inf = json.load(open(os.path.join(dump, stem + ".inferred.json")))
    return d, inf


def ctr(m):
    return [(m["min"][i] + m["max"][i]) / 2 for i in range(3)]


def lin_inv(pos_m, scale):
    d0, d1 = float(scale["domain"][0]), float(scale["domain"][-1])
    r0, r1 = float(scale["range"][0]) / 1000, float(scale["range"][-1]) / 1000
    return d0 + (pos_m - r0) / (r1 - r0) * (d1 - d0)


def hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def seq_color(v, scale):
    """Same interpolation as DxR ScaleSequential.ApplyScale."""
    dom = [float(x) for x in scale["domain"]]
    rng = scale["range"]
    if v <= dom[0]:
        return hexrgb(rng[0])
    if v >= dom[-1]:
        return hexrgb(rng[len(dom) - 1])
    i = next(k for k in range(len(dom)) if v <= dom[k])
    t = (v - dom[i - 1]) / (dom[i] - dom[i - 1])
    a, b = hexrgb(rng[i - 1]), hexrgb(rng[i])
    return [round(a[k] + (b[k] - a[k]) * t) for k in range(3)]


def report(name, ok, msg):
    print(f"{'PASS' if ok else 'FAIL'}  {name:8} {msg}")
    return 0 if ok else 1


def check_pie(dump):
    d, _ = load(dump, "pie_vgsales_genre")
    t = {r["Genre"]: float(r["Share_percent"]) for r in gt("pie_vgsales_genre.csv")}
    errs = [abs((m["endDeg"] - m["startDeg"]) / 3.6 - t[m["datum"]["Genre"]]) for m in d["marks"]]
    return report("pie", len(errs) == len(t) and max(errs) <= 0.051,
                  f"{len(errs)}/{len(t)} slices, max share error {max(errs):.3f} pt (table rounded to 0.1)")


def check_bar(dump):
    d, inf = load(dump, "bar_diamonds_clarity")
    t = {r["Clarity"]: float(r["Mean_price_usd"]) for r in gt("bar_diamonds_clarity.csv")}
    ys = inf["encoding"]["y"]["scale"]
    errs, base = [], []
    for m in d["marks"]:
        errs.append(abs(lin_inv(m["max"][1], ys) - t[m["datum"]["Clarity"]]))
        base.append(abs(m["min"][1]))
    xs = [ctr(m)[0] for m in d["marks"]]
    ordered = [m["datum"]["Clarity"] for m in sorted(d["marks"], key=lambda m: ctr(m)[0])] == [r["Clarity"] for r in gt("bar_diamonds_clarity.csv")]
    return report("bar", len(errs) == len(t) and max(errs) < 0.05 and max(base) < 1e-5 and ordered,
                  f"{len(errs)}/{len(t)} bars, max height error {max(errs):.4f} USD, bars start at 0, order {'ok' if ordered else 'WRONG'}")


def check_scatter(dump):
    d, inf = load(dump, "scatter_penguins")
    rows = gt("scatter_penguins.csv")
    e = inf["encoding"]
    rec = sorted((m["datum"]["Species"], round(lin_inv(ctr(m)[0], e["x"]["scale"]), 3), round(lin_inv(ctr(m)[1], e["y"]["scale"]), 3),
                  round(lin_inv(ctr(m)[2], e["z"]["scale"]), 3)) for m in d["marks"])
    true = sorted((r["Species"], float(r["Bill_length_mm"]), float(r["Flipper_length_mm"]), float(r["Body_mass_g"])) for r in rows)
    err = max(max(abs(a[i] - b[i]) / (b[i] or 1) for i in (1, 2, 3)) for a, b in zip(rec, true)) if len(rec) == len(true) else 1
    return report("scatter", len(rec) == len(true) and err < 1e-4, f"{len(rec)}/{len(true)} points, max relative position error {err:.2e}")


def check_line(dump):
    d, inf = load(dump, "line_gapminder_lifeexp")
    rows = gt("line_gapminder_lifeexp.csv")
    e = inf["encoding"]
    true = {(r["Country"], int(r["Year"])): float(r["Life_expectancy"]) for r in rows}
    errs = []
    for m in d["marks"]:
        c = ctr(m)
        yr = lin_inv(c[0], e["x"]["scale"])
        key = (m["datum"]["Country"], round(yr))
        errs.append(abs(yr - key[1]) + abs(lin_inv(c[1], e["y"]["scale"]) - true.get(key, float("nan"))))
    segs = [l for l in d["lines"] if l["name"].startswith("DataLine")]
    centres = {tuple(round(v, 5) for v in ctr(m)) for m in d["marks"]}
    joined = all(tuple(round(v, 5) for v in l["a"]) in centres and tuple(round(v, 5) for v in l["b"]) in centres for l in segs)
    series = len({m["datum"]["Country"] for m in d["marks"]})
    want_segs = len(true) - series
    ok = len(errs) == len(true) and max(errs) < 1e-3 and len(segs) == want_segs and joined
    return report("line", ok, f"{len(errs)}/{len(true)} points, max error {max(errs):.1e}; {len(segs)}/{want_segs} segments joining "
                              f"consecutive points of {series} series{'' if joined else ' (ENDPOINTS OFF)'}")


def check_heatmap(dump):
    d, inf = load(dump, "heatmap_air_passengers")
    rows = gt("heatmap_air_passengers.csv")
    e = inf["encoding"]
    true = {(r["Year"], r["Month"]): int(r["Passengers_thousands"]) for r in rows}
    xdom, ydom = e["x"]["scale"]["domain"], e["y"]["scale"]["domain"]
    W, H = inf["width"] / 1000, inf["height"] / 1000
    pos_err, col_err = 0, 0
    for m in d["marks"]:
        c = ctr(m)
        yr, mo = xdom[int(c[0] / (W / len(xdom)))], ydom[int(c[1] / (H / len(ydom)))]
        pos_err += (yr, mo) != (m["datum"]["Year"], m["datum"]["Month"])
        want = seq_color(true[(yr, mo)], e["color"]["scale"])
        col_err = max(col_err, max(abs(a - b) for a, b in zip(hexrgb(m["color"]), want)))
    grad = [s for s in d.get("swatches", []) if s["name"] == "GradientCell"]
    ok = len(d["marks"]) == len(true) and pos_err == 0 and col_err <= 1 and len(grad) > 0
    return report("heatmap", ok, f"{len(d['marks'])}/{len(true)} cells in the right row/column ({pos_err} misplaced), "
                                 f"max colour error {col_err}/255 vs the sequential scale, colour bar of {len(grad)} segments")


def main():
    dump = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "headless", "out", "dump")
    fails = sum(f(dump) for f in (check_pie, check_bar, check_scatter, check_line, check_heatmap))
    return fails


if __name__ == "__main__":
    sys.exit(main())
