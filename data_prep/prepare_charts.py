#!/usr/bin/env python3
"""Turn the raw Kaggle CSVs into the five DxR charts + their ground-truth tables.

    python3 prepare_charts.py                    # default: pie slices named, no numbers printed on marks
    python3 prepare_charts.py --labels values    # pie "Action 19.9%", value on every bar and heatmap cell
    python3 prepare_charts.py --labels none      # pie without slice labels (legend only)

Writes
  ../UnityPackage/com.vlm.dxrcharts/Charts~/DxRSpecs/*.json   DxR JSON specs  (+ charts.json = display order)
  ../UnityPackage/com.vlm.dxrcharts/Charts~/DxRData/*.csv     the exact rows each chart draws
  ../ground_truth/*.csv                                        the table a VLM should recover from the video
  ../ground_truth/manifest.json                                provenance (Kaggle source, sha256, filters)
Then in Unity run  DxR Charts ▸ Copy charts to StreamingAssets  (menu 3 and the build menus also do it).

Charts
  1 pie     Kaggle gregorut/videogamesales — global sales (millions of units) by genre: top 7 genres + Other
  2 bar     Kaggle shivam2503/diamonds — one row of 3D bars: mean price (USD) of the 53,940 diamonds per clarity grade
  3 scatter Kaggle Palmer penguins — 45 penguins (15 per species, fixed random seed):
            bill length (x), flipper length (y), body mass (z), species (colour)
  4 line    Kaggle Gapminder World 1952-2007 — life expectancy of 4 countries, 12 survey years each
  5 heatmap Kaggle rakannimer/air-passengers — monthly airline passengers (thousands), 12 months × 1955-1960
Standard library only.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(HERE, "raw")
PKG = os.path.join(ROOT, "UnityPackage", "com.vlm.dxrcharts", "Charts~")
SPECS = os.path.join(PKG, "DxRSpecs")
DATA = os.path.join(PKG, "DxRData")
GT = os.path.join(ROOT, "ground_truth")

# Mark colours chosen to stand out against the blue grid room (no dark blues) and the dark/light backdrops.
SPECIES_COLORS = ["#ff9f1c", "#ff4fa3", "#7ee36b"]                     # orange, pink, green
PIE_COLORS = ["#f58518", "#e45756", "#72b7b2", "#54a24b", "#eeca3b", "#b279a2", "#ff9da6", "#d9d9d9"]
TABLEAU10 = ["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b", "#eeca3b", "#b279a2", "#ff9da6", "#9d755d", "#bab0ac"]


def read_csv(name):
    with open(os.path.join(RAW, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def sha(name):
    return hashlib.sha256(open(os.path.join(RAW, name), "rb").read()).hexdigest()


def safe(s):
    """DxR's CSV reader splits on commas and strips quotes: keep labels comma/quote free."""
    return s.replace(",", " ").replace('"', "").strip()


def nice_ticks(lo, hi, step):
    lo = math.floor(lo / step) * step
    hi = math.ceil(hi / step) * step
    n = int(round((hi - lo) / step))
    return [round(lo + i * step, 10) for i in range(n + 1)]


def num(v):
    return int(v) if float(v).is_integer() else v


# ---------------------------------------------------------------- 1. pie
def make_pie(labels, top_n):
    rows = read_csv("vgsales.csv")
    by = defaultdict(float)
    for r in rows:
        by[r["Genre"]] += float(r["Global_Sales"])
    total = sum(by.values())
    ranked = sorted(by.items(), key=lambda kv: -kv[1])
    top = ranked[:top_n]
    other = sum(v for _, v in ranked[top_n:])
    slices = [(g, v) for g, v in top] + [("Other", other)]
    out, gt, angle = [], [], 0.0
    for g, v in slices:
        share = 100.0 * v / total
        a0, a1 = angle, angle + 360.0 * v / total
        angle = a1
        label = {"names": g, "values": f"{g} {share:.1f}%", "none": ""}[labels]
        out.append([safe(g), f"{v:.2f}", f"{share:.2f}", f"{a0:.3f}", f"{a1:.3f}", safe(label) or "-"])
        gt.append([g, f"{v:.2f}", f"{share:.1f}"])
    write_csv(os.path.join(DATA, "pie_vgsales_genre.csv"), ["Genre", "Sales", "Percent", "start_angle", "end_angle", "label"], out)
    write_csv(os.path.join(GT, "pie_vgsales_genre.csv"), ["Genre", "Global_Sales_millions", "Share_percent"], gt)
    enc = OrderedDict()
    enc["x"] = {"value": "300"}
    enc["y"] = {"value": "300"}
    enc["z"] = {"value": "0"}
    enc["startangle"] = {"field": "start_angle", "type": "quantitative", "scale": {"type": "none"}}
    enc["endangle"] = {"field": "end_angle", "type": "quantitative", "scale": {"type": "none"}}
    enc["radius"] = {"value": "250"}
    enc["thickness"] = {"value": "60"}
    enc["color"] = {"field": "Genre", "type": "nominal",
                    "scale": {"domain": [safe(g) for g, _ in slices], "range": "category", "scheme": PIE_COLORS[:len(slices)]},
                    "legend": {"title": "Genre", "x": 740, "y": 600}}
    if labels != "none":
        enc["label"] = {"field": "label", "type": "nominal", "scale": {"type": "none"}}
    spec = OrderedDict([("title", "Video game sales by genre (global, millions of units)"),
                        ("width", 600), ("height", 600), ("depth", 60),
                        ("data", {"url": "pie_vgsales_genre.csv"}), ("mark", "arc"), ("encoding", enc)])
    write_json(os.path.join(SPECS, "pie_vgsales_genre.json"), spec)
    return {"id": "pie", "spec": "pie_vgsales_genre.json", "ground_truth": "pie_vgsales_genre.csv",
            "source": "kaggle.com/datasets/gregorut/videogamesales (vgsales.csv)", "raw_sha256": sha("vgsales.csv"),
            "transform": f"sum Global_Sales by Genre over all 16598 games; top {top_n} genres + 'Other'; share = genre / total",
            "total_sales_millions": round(total, 2)}


# ---------------------------------------------------------------- 2. bar (one row of 3D bars)
CLARITY = ["I1", "SI2", "SI1", "VS2", "VS1", "VVS2", "VVS1", "IF"]       # GIA order: worst -> best
BAR_COLOR = "#f58518"


def make_bar(labels):
    rows = read_csv("diamonds.csv")
    tot, cnt = defaultdict(float), defaultdict(int)
    for r in rows:
        tot[r["clarity"]] += float(r["price"]); cnt[r["clarity"]] += 1
    out, gt = [], []
    for c in CLARITY:
        v = round(tot[c] / cnt[c], 1)
        out.append([c, f"{v:.1f}", f"${v:,.0f}".replace(",", " ")])
        gt.append([c, f"{v:.1f}", cnt[c]])
    write_csv(os.path.join(DATA, "bar_diamonds_clarity.csv"), ["Clarity", "MeanPrice", "label"], out)
    write_csv(os.path.join(GT, "bar_diamonds_clarity.csv"), ["Clarity", "Mean_price_usd", "Diamonds"], gt)
    enc = OrderedDict()   # DxR applies channels in this order: x, z, y (bar top), then height + yoffsetpct (bar grows down to 0)
    enc["x"] = {"field": "Clarity", "type": "nominal", "scale": {"domain": CLARITY},
                "axis": {"title": "Clarity grade (worst to best)"}}
    enc["z"] = {"value": "60"}
    enc["y"] = {"field": "MeanPrice", "type": "quantitative", "scale": {"domain": [0, 6000]},
                "axis": {"title": "Mean price (USD)", "values": list(range(0, 6001, 1000)), "grid": True}}
    enc["height"] = {"field": "MeanPrice", "type": "quantitative", "scale": {"domain": [0, 6000]}}
    enc["yoffsetpct"] = {"value": "-0.5"}
    enc["width"] = {"value": "70"}
    enc["depth"] = {"value": "80"}
    enc["color"] = {"value": BAR_COLOR}
    if labels == "values":
        enc["label"] = {"field": "label", "type": "nominal", "scale": {"type": "none"}}
    spec = OrderedDict([("title", "Diamonds: mean price by clarity grade (n = 53,940)"),
                        ("width", 900), ("height", 500), ("depth", 120),
                        ("data", {"url": "bar_diamonds_clarity.csv"}), ("mark", "cube"), ("encoding", enc),
                        ("view", {"yaw": 20})])
    write_json(os.path.join(SPECS, "bar_diamonds_clarity.json"), spec)
    return {"id": "bar", "spec": "bar_diamonds_clarity.json", "ground_truth": "bar_diamonds_clarity.csv",
            "source": "kaggle.com/datasets/shivam2503/diamonds (diamonds.csv)", "raw_sha256": sha("diamonds.csv"),
            "transform": f"mean price per clarity grade over all {len(rows)} diamonds, rounded to 0.1 USD; bars in GIA order I1 (worst) to IF (best)"}


# ---------------------------------------------------------------- 3. scatter
def make_scatter(seed, per_species):
    rows = read_csv("penguins.csv")
    bill = "bill_length_mm" if "bill_length_mm" in rows[0] else "culmen_length_mm"   # mirror vs Kaggle column names
    keep = [r for r in rows if all(r.get(k, "NA") not in ("NA", "", ".") for k in ("species", bill, "flipper_length_mm", "body_mass_g"))]
    rnd = random.Random(seed)
    chosen = []
    for sp in sorted({r["species"] for r in keep}):
        group = [r for r in keep if r["species"] == sp]
        chosen += rnd.sample(group, min(per_species, len(group)))
    chosen.sort(key=lambda r: (r["species"], float(r[bill])))
    out, gt = [], []
    for i, r in enumerate(chosen, 1):
        b, fl, m = float(r[bill]), float(r["flipper_length_mm"]), float(r["body_mass_g"])
        out.append([f"P{i:02d}", r["species"], num(b), num(fl), num(m)])
        gt.append([r["species"], num(b), num(fl), num(m)])
    write_csv(os.path.join(DATA, "scatter_penguins.csv"), ["id", "Species", "BillLength", "FlipperLength", "BodyMass"], out)
    write_csv(os.path.join(GT, "scatter_penguins.csv"), ["Species", "Bill_length_mm", "Flipper_length_mm", "Body_mass_g"], gt)
    xs = [float(r[2]) for r in out]; ys = [float(r[3]) for r in out]; zs = [float(r[4]) for r in out]
    xt, yt, zt = nice_ticks(min(xs), max(xs), 5), nice_ticks(min(ys), max(ys), 10), nice_ticks(min(zs), max(zs), 1000)
    enc = OrderedDict()
    enc["x"] = {"field": "BillLength", "type": "quantitative", "scale": {"domain": [xt[0], xt[-1]]},
                "axis": {"title": "Bill length (mm)", "values": xt, "grid": True}}
    enc["y"] = {"field": "FlipperLength", "type": "quantitative", "scale": {"domain": [yt[0], yt[-1]]},
                "axis": {"title": "Flipper length (mm)", "values": yt, "grid": True}}
    enc["z"] = {"field": "BodyMass", "type": "quantitative", "scale": {"domain": [zt[0], zt[-1]]},
                "axis": {"title": "Body mass (g)", "values": zt, "grid": True, "face": "right", "orient": "bottom"}}
    species = sorted({r[1] for r in out})
    enc["color"] = {"field": "Species", "type": "nominal",
                    "scale": {"domain": species, "range": "category", "scheme": SPECIES_COLORS[:len(species)]},
                    "legend": {"title": "Species"}}
    enc["size"] = {"value": "24"}
    spec = OrderedDict([("title", "Palmer penguins (n=45): bill length, flipper length, body mass"),
                        ("width", 500), ("height", 500), ("depth", 500),
                        ("data", {"url": "scatter_penguins.csv"}), ("mark", "sphere"), ("encoding", enc),
                        ("view", {"yaw": 30})])
    write_json(os.path.join(SPECS, "scatter_penguins.json"), spec)
    return {"id": "scatter", "spec": "scatter_penguins.json", "ground_truth": "scatter_penguins.csv",
            "source": "kaggle.com/datasets/parulpandey/palmer-archipelago-antarctica-penguin-data (Palmer penguins)",
            "raw_sha256": sha("penguins.csv"),
            "transform": f"drop rows with missing values; random.Random({seed}).sample {per_species} per species; sorted by species, bill length"}


# ---------------------------------------------------------------- 4. line
LINE_COUNTRIES = ["Japan", "China", "South Africa", "India"]
LINE_COLORS = ["#ff9f1c", "#ff4fa3", "#7ee36b", "#ffe14d"]          # orange, pink, green, yellow


def make_line():
    rows = read_csv("gapminder.csv")
    kc = next(k for k in rows[0] if k.strip().lower() == "country")
    ky = next(k for k in rows[0] if k.strip().lower() == "year")
    kl = next(k for k in rows[0] if k.replace("_", "").strip().lower() in ("lifeexp", "lifeexpectancy"))
    out, gt = [], []
    for c in LINE_COUNTRIES:
        pts = sorted((int(r[ky]), float(r[kl])) for r in rows if r[kc].strip() == c)
        for y, v in pts:
            out.append([safe(c), y, f"{v:.3f}"])
            gt.append([c, y, f"{v:.3f}"])
    years = sorted({r[1] for r in out})
    write_csv(os.path.join(DATA, "line_gapminder_lifeexp.csv"), ["Country", "Year", "LifeExp"], out)
    write_csv(os.path.join(GT, "line_gapminder_lifeexp.csv"), ["Country", "Year", "Life_expectancy"], gt)
    enc = OrderedDict()
    enc["x"] = {"field": "Year", "type": "quantitative", "scale": {"domain": [1950, 2010]},
                "axis": {"title": "Year", "values": list(range(1950, 2011, 10)), "grid": True}}
    enc["y"] = {"field": "LifeExp", "type": "quantitative", "scale": {"domain": [30, 90]},
                "axis": {"title": "Life expectancy (years)", "values": list(range(30, 91, 10)), "grid": True}}
    enc["z"] = {"value": "30"}
    enc["color"] = {"field": "Country", "type": "nominal",
                    "scale": {"domain": LINE_COUNTRIES, "range": "category", "scheme": LINE_COLORS},
                    "legend": {"title": "Country", "x": 830, "y": 500}}
    enc["size"] = {"value": "18"}
    spec = OrderedDict([("title", "Life expectancy 1952-2007 (Gapminder)"),
                        ("width", 800), ("height", 500), ("depth", 60),
                        ("data", {"url": "line_gapminder_lifeexp.csv"}), ("mark", "line"), ("encoding", enc),
                        ("strokeWidth", 7), ("view", {"yaw": 12})])
    write_json(os.path.join(SPECS, "line_gapminder_lifeexp.json"), spec)
    return {"id": "line", "spec": "line_gapminder_lifeexp.json", "ground_truth": "line_gapminder_lifeexp.csv",
            "source": "kaggle.com/datasets/tklimonova/gapminder-datacamp-2007 (Gapminder World 1952-2007)",
            "raw_sha256": sha("gapminder.csv"),
            "transform": f"life expectancy (lifeExp) of {', '.join(LINE_COUNTRIES)} in every survey year {years[0]}-{years[-1]} ({len(years)} points per country)"}


# ---------------------------------------------------------------- 5. heatmap
HEAT_YEARS = [1955, 1956, 1957, 1958, 1959, 1960]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
HEAT_STOPS = [200, 300, 400, 500, 600, 700]
HEAT_COLORS = ["#ffffb2", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"]   # ColorBrewer YlOrRd


def air_passengers():
    """{(year, month 1-12): passengers} from either the Kaggle file (Month '1949-01', #Passengers) or the mirror."""
    rows = read_csv("air_passengers.csv")
    if "Month" in rows[0]:
        kp = next(k for k in rows[0] if "assengers" in k)
        return {(int(r["Month"][:4]), int(r["Month"][5:7])): int(r[kp]) for r in rows}
    abbr = [m[:3] for m in MONTHS]
    return {(int(r["year"]), abbr.index(r["month"].strip()[:3].title()) + 1): int(r["passengers"]) for r in rows}


def make_heatmap(labels):
    data = air_passengers()
    out, gt = [], []
    for y in HEAT_YEARS:
        for m in range(1, 13):
            v = data[(y, m)]
            out.append([y, MONTHS[m - 1][:3], v, v])
            gt.append([y, MONTHS[m - 1][:3], v])
    write_csv(os.path.join(DATA, "heatmap_air_passengers.csv"), ["Year", "Month", "Passengers", "label"], out)
    write_csv(os.path.join(GT, "heatmap_air_passengers.csv"), ["Year", "Month", "Passengers_thousands"], gt)
    W, H = 720, 720
    months_bottom_up = [m[:3] for m in reversed(MONTHS)]      # DxR's y grows upwards: January ends up on top
    enc = OrderedDict()
    enc["x"] = {"field": "Year", "type": "nominal", "scale": {"domain": [str(y) for y in HEAT_YEARS], "padding": 0},
                "axis": {"title": "Year"}}
    enc["y"] = {"field": "Month", "type": "nominal", "scale": {"domain": months_bottom_up, "padding": 0},
                "axis": {"title": "Month"}}
    enc["z"] = {"value": "15"}
    enc["width"] = {"value": f"{W / len(HEAT_YEARS) * 0.94:.1f}"}
    enc["height"] = {"value": f"{H / 12 * 0.9:.1f}"}
    enc["depth"] = {"value": "20"}
    enc["color"] = {"field": "Passengers", "type": "quantitative",
                    "scale": {"type": "sequential", "domain": HEAT_STOPS, "range": HEAT_COLORS},
                    "legend": {"title": "Passengers (thousands)", "type": "gradient", "x": 750, "y": 700}}
    if labels == "values":
        enc["label"] = {"field": "label", "type": "nominal", "scale": {"type": "none"}}
    spec = OrderedDict([("title", "Airline passengers per month, 1955-1960 (thousands)"),
                        ("width", W), ("height", H), ("depth", 30),
                        ("data", {"url": "heatmap_air_passengers.csv"}), ("mark", "rect"), ("encoding", enc)])
    write_json(os.path.join(SPECS, "heatmap_air_passengers.json"), spec)
    return {"id": "heatmap", "spec": "heatmap_air_passengers.json", "ground_truth": "heatmap_air_passengers.csv",
            "source": "kaggle.com/datasets/rakannimer/air-passengers (AirPassengers.csv; Box & Jenkins airline data)",
            "raw_sha256": sha("air_passengers.csv"),
            "transform": f"monthly totals (thousands of passengers) for {HEAT_YEARS[0]}-{HEAT_YEARS[-1]}; colour = sequential YlOrRd scale with stops {HEAT_STOPS}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", choices=["names", "values", "none"], default="names",
                    help="names: pie slices show the genre; values: also print the value on bars, pie slices and heatmap cells; none: no data labels")
    ap.add_argument("--seed", type=int, default=7, help="random seed for the penguin sample")
    ap.add_argument("--per-species", type=int, default=15)
    ap.add_argument("--pie-top", type=int, default=7, help="genres shown as their own slice (rest = Other)")
    a = ap.parse_args()
    charts = [make_pie(a.labels, a.pie_top), make_bar(a.labels), make_scatter(a.seed, a.per_species),
              make_line(), make_heatmap(a.labels)]
    write_json(os.path.join(SPECS, "charts.json"), {"charts": [{"id": c["id"], "spec": c["spec"]} for c in charts]})
    write_json(os.path.join(GT, "manifest.json"), {"labels_mode": a.labels, "charts": charts})
    for c in charts:
        print(f"{c['id']:8} {c['spec']:32} ground truth: ground_truth/{c['ground_truth']}")
    print("Next: in Unity run  DxR Charts > Copy charts to StreamingAssets  (or menu 3 / the build menu).")


if __name__ == "__main__":
    main()
