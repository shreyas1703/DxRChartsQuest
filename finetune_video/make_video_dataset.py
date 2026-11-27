#!/usr/bin/env python3
"""Synthetic training VIDEOS for run 3: short "walk-around" clips of DxR-style charts with their exact tables.

    python3 finetune_video/make_video_dataset.py --strict                     # 2,000 train + 60 val clips, 8 frames
    python3 finetune_video/make_video_dataset.py --strict --train 3000 --frames 8 --workers 8
    python3 finetune_video/make_video_dataset.py --strict --preview 3         # contact sheets to look at
    python3 finetune_video/make_video_dataset.py --strict --charts line --train 1000 --out finetune_video/data_line

Each clip = 8 frames of ONE chart while the camera sweeps around it (like walking past the chart in the
Quest): flat charts (pie, line, 2D heatmap) are seen from a sweeping yaw, 3D charts (bar, scatter, 3D heatmap)
are re-rendered with a moving camera. The answer is the CSV in exactly the format vlm_eval/prompts.md asks for.

--strict (use it): the training data shares NOTHING with the real test charts except chart type and style -
no genre, clarity-grade, country or species names that occur in ground_truth/*.csv (or the built-in list of
the real ones), no heatmap years 1949-1960, and all values random. The real tables are used only for scoring.

Output: <out>/clips/<split>_<kind>_<n>/f0.jpg ... f7.jpg and <out>/train.jsonl, val.jsonl:
    {"frames": ["clips/train_pie_000001/f0.jpg", ...], "chart": "pie", "answer": "Genre,Share_percent\\n..."}
Needs numpy, matplotlib, Pillow.
"""
import argparse
import csv
import io
import json
import math
import os
import random
from multiprocessing import Pool

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BG = "#eef0f3"
LABEL_BG = "#5d6066"
TITLE_BG = "#6b6e74"
PALETTE = ["#f28c28", "#e8504a", "#45a29e", "#2f8f4e", "#e9b31c", "#a0668e", "#f09aa0", "#c8c8c8", "#6c8ebf", "#8c6d46"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
GENRES = ("Puzzle Arcade Strategy Fighting Adventure Simulation Music Horror Party Trivia Rhythm Sandbox Survival Stealth "
          "Educational Card Board Casual Tactics Fitness Builder Mystery Quiz Racing Sports Shooter Platform Action Misc Other "
          "Role-Playing").split()
GRADES = ["I1", "SI2", "SI1", "VS2", "VS1", "VVS2", "VVS1", "IF", "FL", "I2", "I3", "SI3"]
COUNTRIES = ("Brazil Kenya Norway Mexico Peru Chile Egypt Ghana Nepal Spain Italy France Canada Sweden Poland Turkey Iran Iraq "
             "Vietnam Thailand Nigeria Ethiopia Bolivia Cuba Greece Ireland Portugal Finland Denmark Austria Morocco Algeria "
             "Uganda Zambia Haiti Jamaica Panama Uruguay Mongolia Laos Japan China India").split()
SPECIES_REAL = ["Adelie", "Chinstrap", "Gentoo"]
SPECIES_OTHER = ["Emperor", "King", "Macaroni", "Rockhopper", "Humboldt", "Magellanic", "Galapagos", "Snares", "Fiordland", "Erect-crested"]
REAL_NAMES_BUILTIN = {"Action", "Sports", "Shooter", "Role-Playing", "Platform", "Misc", "Racing", "Other", "I1", "SI2", "SI1",
                      "VS2", "VS1", "VVS2", "VVS1", "IF", "Japan", "China", "South Africa", "India", "Adelie", "Chinstrap", "Gentoo"}
CFG = {"strict": False, "banned": set()}


def real_names():
    """Every label that occurs in the real test tables (ground_truth/*.csv), plus the built-in list."""
    names = set(REAL_NAMES_BUILTIN)
    gt = os.path.join(ROOT, "ground_truth")
    if os.path.isdir(gt):
        for f in os.listdir(gt):
            if f.endswith(".csv"):
                for row in csv.DictReader(open(os.path.join(gt, f), encoding="utf-8")):
                    for k in ("Genre", "Clarity", "Country", "Species"):
                        if row.get(k):
                            names.add(row[k].strip())
        ctrl = os.path.join(gt, "control")                     # control (test-only) charts: their names never train
        if os.path.isdir(ctrl):
            for f in os.listdir(ctrl):
                if f.endswith(".csv"):
                    for row in csv.DictReader(open(os.path.join(ctrl, f), encoding="utf-8")):
                        for k in ("Country", "Series", "Category"):
                            if row.get(k):
                                names.add(row[k].strip())
    return names


def pool(words):
    return [w for w in words if w not in CFG["banned"]] if CFG["strict"] else list(words)


def label_box(color=LABEL_BG):
    return dict(boxstyle="square,pad=0.25", facecolor=color, edgecolor="none", alpha=0.95)


def style_ticks(ax, size, zaxis=False):
    for t in ax.get_xticklabels() + ax.get_yticklabels() + (ax.get_zticklabels() if zaxis else []):
        t.set_bbox(label_box()); t.set_color("white"); t.set_fontsize(size)


# ------------------------------------------------------------------ random tables
def data_pie(rng):
    if rng.random() < 0.65:            # pie r1: DxR-like pies have 5-10 fairly even slices
        n = rng.randint(5, 10)
        w = np.array([rng.uniform(0.45, 1.6) for _ in range(n)])
    else:
        n = rng.randint(4, 9)
        w = np.array([rng.random() ** 1.6 + 0.04 for _ in range(n)])
    names = rng.sample(pool(GENRES), n)
    share = np.round(w / w.sum() * 100, 1)
    share[np.argmax(share)] += round(100 - share.sum(), 1)
    return "Genre,Share_percent", [(names[i], round(float(share[i]), 1)) for i in np.argsort(-share)]


def data_pieany(rng):
    """pie r2: a pie about anything (header Category,Share_percent), 3-11 slices, even or lopsided."""
    if rng.random() < 0.6:
        n = rng.randint(4, 10)
        w = np.array([rng.uniform(0.45, 1.6) for _ in range(n)])
    else:
        n = rng.randint(3, 10)
        w = np.array([rng.random() ** 1.6 + 0.04 for _ in range(n)])
    fams = [f for f in PIE_FAMILIES if len(pool(f[1])) >= n]
    legend_t, src, measures = rng.choice(fams)
    names = rng.sample(pool(src), n)
    share = np.round(w / w.sum() * 100, 1)
    share[np.argmax(share)] += round(100 - share.sum(), 1)
    m = rng.choice(measures)
    title = rng.choice([f"{m} by {legend_t.lower()}", f"{m} by {legend_t.lower()} (%)", f"Share of {m.lower()}", m])
    return ("Category,Share_percent", [(names[i], round(float(share[i]), 1)) for i in np.argsort(-share)],
            {"legend": legend_t, "title": title})




def nice_step(hi):
    raw = hi / 6
    mag = 10 ** math.floor(math.log10(raw))
    return next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)


def bar_values(rng, k, hi):
    """k values between ~8 % and ~97 % of hi, no two closer than ~6 % of hi, rounded like real chart data."""
    gap = hi * rng.uniform(0.06, 0.09) if k <= 12 else hi * 0.05
    dec = 2 if hi <= 1 else 1 if hi <= 20 else 0
    for _ in range(200):
        v = sorted(rng.uniform(0.08, 0.97) * hi for _ in range(k))
        if all(b - a >= gap for a, b in zip(v, v[1:])):
            break
    else:
        v = [hi * (0.08 + 0.89 * i / max(1, k - 1)) for i in range(k)]
    if hi >= 1000 and rng.random() < 0.5:                 # sometimes round to tens/hundreds like real tables
        v = [round(x, -1 if hi < 10000 else -2) for x in v]
    v = [round(x, dec) if dec else int(round(x)) for x in v]
    rng.shuffle(v)
    return v


def data_bar3d(rng):
    nc = rng.choice([2, 3, 3, 4, 4, 4, 5, 5, 6])
    ns = rng.choice([1, 1, 2, 2, 3, 3, 3, 4])
    while nc * ns > 16:
        ns -= 1
    cats = [c for c in BAR_CATS if len(pool(c[1])) >= nc]
    cat_t, cpool = rng.choice(cats)
    if cat_t == "Quarter" or cat_t == "Month":
        p = pool(cpool); i0 = rng.randint(0, len(p) - nc); cnames = p[i0:i0 + nc]
    else:
        cnames = rng.sample(pool(cpool), nc)
    ser_opts = [s_ for s_ in BAR_SERIES if s_[1] is None or len(pool(s_[1])) >= ns]
    ser_t, spool = rng.choice(ser_opts)
    if spool is None:
        y0 = rng.randint(1995, 2026 - ns)
        snames = [str(y) for y in range(y0, y0 + ns) if str(y) not in CFG["banned"]]
        if len(snames) < ns:
            ser_t, spool = "Group", ["Group 1", "Group 2", "Group 3", "Group 4", "Group 5"]
    if spool is not None:
        snames = rng.sample(pool(spool), ns)
    snames = [s_ for s_ in snames if s_ not in cnames][:ns] or ["All"]
    hi = rng.choice(NICE_MAX)
    vals = bar_values(rng, len(cnames) * len(snames), hi * rng.uniform(0.85, 1.0))
    m, unit = rng.choice(BAR_MEASURES)
    rows = [(c, s_, vals[i * len(snames) + j]) for i, c in enumerate(cnames) for j, s_ in enumerate(snames)]
    spec = {"cat": cat_t, "ser": ser_t, "measure": m + unit,
            "title": rng.choice([f"{m} by {cat_t.lower()} and {ser_t.lower()}", f"{m} by {cat_t.lower()}", m])}
    return "Category,Series,Value", rows, spec


def scene_bar3d(rng, rows, spec):
    """bar r1: a grid of 3D bars (categories along x, series back in depth y, value up z), grid on the walls,
    tick labels on the axes, sometimes a legend, never value labels (the model must read heights)."""
    fig = plt.figure(figsize=(8, 6), facecolor=rng.choice([BG, BG, "#ffffff", "#2b2f36"]))
    ax = fig.add_subplot(111, projection="3d", facecolor=fig.get_facecolor())
    cats = list(dict.fromkeys(r[0] for r in rows)); sers = list(dict.fromkeys(r[1] for r in rows))
    nc, ns = len(cats), len(sers)
    pal = rng.choice([DXR_COLS, PALETTE, ["#4472c4", "#c0504d", "#9bbb59", "#8064a2", "#f79646", "#4bacc6"]])
    cols = pal[:ns] if rng.random() < 0.6 else rng.sample(pal, ns)
    one_colour = ns == 1 or rng.random() < 0.15
    if one_colour:
        cols = [rng.choice(pal)] * ns
    w, dx, dy = rng.uniform(0.45, 0.75), rng.uniform(1.2, 1.7), rng.uniform(1.2, 1.9)
    vmax = max(r[2] for r in rows)
    step = nice_step(vmax)
    top = math.ceil(vmax / step) * step
    rng.random(); show_vals = False   # bar r1c: never print values on the bars (the test charts have none)
    dark = fig.get_facecolor()[0] < 0.5
    xs, ys, hs, cs = [], [], [], []
    for (c, s_, v) in rows:                              # one bar3d call, so matplotlib sorts the bars by depth
        xs.append(cats.index(c) * dx); ys.append(sers.index(s_) * dy); hs.append(v); cs.append(cols[sers.index(s_)])
    ax.bar3d(xs, ys, [0] * len(xs), w, w, hs, color=cs, shade=True, edgecolor=rng.choice(["none", "none", "#333333"]), linewidth=0.3)
    for (c, s_, v) in rows:
        i, j = cats.index(c), sers.index(s_)
        if show_vals:
            ax.text(i * dx + w / 2, j * dy + w / 2, v + top * 0.03, f"{v:g}", ha="center", fontsize=rng.choice([6, 7, 8]),
                    color="white", bbox=label_box())
    ax.set_xticks([i * dx + w / 2 for i in range(nc)]); ax.set_xticklabels(cats)
    ax.set_yticks([j * dy + w / 2 for j in range(ns)]); ax.set_yticklabels(sers if ns > 1 or rng.random() < 0.6 else [""])
    ax.set_zticks(np.arange(0, top + step / 2, step))
    ax.set_zticklabels([f"{t:g}" for t in np.arange(0, top + step / 2, step)])
    ax.set_xlim(-0.4, (nc - 1) * dx + w + 0.4); ax.set_ylim(-0.4, (ns - 1) * dy + w + 0.4); ax.set_zlim(0, top)
    pane = rng.choice([(0.93, 0.94, 0.95, 1.0), (1, 1, 1, 0.0), (0.85, 0.87, 0.9, 1.0), (0.2, 0.22, 0.26, 1.0)])
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color(pane)
        a._axinfo["grid"]["color"] = (0.55, 0.55, 0.6, rng.uniform(0.4, 1.0))
    style_ticks(ax, rng.choice([9, 10, 11]), zaxis=True)
    if rng.random() < 0.7:
        ax.set_zlabel(spec["measure"], color="#f3e3a6", fontsize=8)
    if ns > 1 and rng.random() < 0.6:                    # legend as well as (or instead of) the depth-axis labels
        fig.text(0.86, 0.80, spec["ser"], color="#f3e3a6", fontsize=9, bbox=label_box())
        for j, s_ in enumerate(sers):
            fig.text(0.88, 0.75 - j * 0.045, s_, color="white", fontsize=8, bbox=label_box())
            fig.patches.append(plt.Rectangle((0.855, 0.745 - j * 0.045), 0.015, 0.02, color=cols[j], transform=fig.transFigure, figure=fig))
    ax.set_box_aspect(((nc - 1) * dx + w + 0.8, max(1.2, (ns - 1) * dy + w + 0.8), rng.uniform(2.6, 4.2)), zoom=rng.uniform(1.0, 1.22))
    fig.subplots_adjust(left=0, right=0.86 if ns > 1 else 1, bottom=0, top=0.95)
    fig.text(0.5, 0.92, spec["title"], ha="center", color="white", fontsize=11, bbox=label_box(TITLE_BG))
    return fig, ax, rng.uniform(-125, -55), rng.uniform(5, 38)


def data_bar(rng):
    n = rng.randint(4, 9)
    style = rng.random()
    if style < 0.35 and len(pool(GRADES)) >= n:
        names = rng.sample(pool(GRADES), n)
    elif style < 0.7:
        names = list(dict.fromkeys(rng.choice("ABCDEGHJKMNPRTUWXZ") + str(rng.randint(1, 9)) for _ in range(n + 4)))[:n]
        names = [x for x in names if x not in CFG["banned"]] or ["A1", "B2", "C3", "D4"]
    else:
        names = rng.sample(pool(GENRES), n)
    hi = rng.choice([3000, 6000, 8000, 12000, 20000])
    if rng.random() < 0.45:
        base = rng.uniform(0.45, 0.75) * hi
        heights = [round(base * rng.uniform(0.75, 1.3), 1) for _ in names]
    else:
        heights = [round(rng.uniform(0.15, 1.0) * hi, 1) for _ in names]
    dmax = rng.choice([1000, 5000, 15000, 30000])
    return "Clarity,Mean_price_usd,Diamonds", [(a, h, int(rng.uniform(0.05, 1.0) * dmax)) for a, h in zip(names, heights)]


def data_line(rng):
    names = rng.sample(pool(COUNTRIES), rng.randint(2, 6))
    start, step = rng.randint(1948, 1965), rng.choice([5, 5, 5, 10])
    m = min(rng.randint(6, 13), (2012 - start) // step + 1)
    rows = []
    for c in names:
        v, slope = rng.uniform(30, 70), rng.uniform(-0.15, 0.55)
        for i in range(m):
            v = min(88, max(25, v + slope * step + rng.gauss(0, 1.2) + (rng.uniform(-8, 0) if rng.random() < 0.06 else 0)))
            rows.append((c, start + step * i, round(v, 1)))
    return "Country,Year,Life_expectancy", rows


# ---- any line chart (run 5): random x axis, random y measure and scale, random series names; header Series,X,Y
CITIES = ("Oslo Lima Cairo Quito Accra Hanoi Dakar Perth Porto Delhi Tunis Riga Sofia Lyon Graz Kobe Bonn Cork Leeds Turin "
          "Austin Denver Boston Dallas Tampa Omaha Fresno Reno").split()
PRODUCTS = [f"{a} {b}" for a in ("Model", "Product", "Brand", "Series", "Plan", "Type") for b in "ABCDEFGHJK"]
TEAMS = ("Falcons Tigers Wolves Hawks Lions Bears Sharks Eagles Comets Rockets Pumas Vipers").split()
SENSORS = [f"Sensor {i}" for i in range(1, 13)] + [f"Station {c}" for c in "ABCDEFGH"] + [f"Group {c}" for c in "ABCDEFGH"]
YMEASURES = [("Sales (units)", 100), ("Revenue (million $)", 10), ("Temperature (°C)", 10), ("Rainfall (mm)", 100),
             ("Price ($)", 10), ("Score", 10), ("Population (thousands)", 1000), ("Speed (km/h)", 100),
             ("Conversion rate (%)", 10), ("Energy use (kWh)", 1000), ("Visitors", 10000), ("Weight (kg)", 10),
             ("Height (cm)", 100), ("Index", 100), ("Share (%)", 10), ("Cost (thousand $)", 100), ("Growth rate", 1)]
LEGEND_OF = {"city": "City", "product": "Product", "team": "Team", "sensor": "Group", "country": "Country"}
# pie r2 ("pieany"): pies about anything. Category names come from many families; the answer header is always
# Category,Share_percent. Names of the test pies (ground_truth/control/pieany_*.csv) are banned by --strict.
BRANDS = ("Zentro Lumina Nordia Vexa Kairo Solenne Brisk Mirra Quanta Novella Strata Pivot Halcyon Juniper Cobalt Verve "
          "Arcadia Nimbus Corvo Pellar").split()
ENERGY = "Solar Wind Hydro Nuclear Coal Gas Oil Biomass Geothermal Tidal Imports Waste".split()
FOODS = "Rice Wheat Maize Beans Fruit Vegetables Dairy Meat Fish Nuts Eggs Sugar Oils Roots".split()
MODES = "Car Bus Train Bicycle Walking Tram Ferry Scooter Taxi Subway Carpool Motorbike".split()
DEPTS = "Sales Marketing Research Support Finance Legal Operations Design Engineering Admin Logistics Training".split()
REGIONS = "North South East West Central Coastal Highlands Lowlands Islands Metro Rural Suburbs".split()
SPEND = ("Housing Groceries Transport Health Leisure Savings Utilities Education Clothing Travel Insurance Gifts Dining "
         "Childcare").split()
PIE_FAMILIES = [("Country", COUNTRIES, ["Population", "Visitors", "Exports", "Votes"]),
                ("City", CITIES, ["Visitors", "Sales", "Population"]),
                ("Product", PRODUCTS, ["Sales", "Revenue", "Orders"]),
                ("Team", TEAMS, ["Fans", "Wins", "Budget"]),
                ("Brand", BRANDS, ["Market share", "Sales", "Users"]),
                ("Source", ENERGY, ["Electricity mix", "Energy supply", "Power generation"]),
                ("Food", FOODS, ["Diet", "Production", "Imports"]),
                ("Mode", MODES, ["Commute", "Trips", "Passengers"]),
                ("Department", DEPTS, ["Budget", "Staff", "Costs"]),
                ("Region", REGIONS, ["Revenue", "Population", "Sales"]),
                ("Category", SPEND, ["Spending", "Budget", "Expenses"]),
                ("Genre", GENRES, ["Sales", "Players"])]
# bar r1 ("bar3d"): a 3D grid of bars - categories along the front, series going back in depth, one value per bar.
# Answer header Category,Series,Value. Values are spread out (no two bars within ~6 % of the axis maximum).
BAR_CATS = [("Quarter", ["Q1", "Q2", "Q3", "Q4"]), ("Quarter", ["Qtr 1", "Qtr 2", "Qtr 3", "Qtr 4"]),
            ("Month", MONTHS), ("Product", PRODUCTS), ("City", CITIES), ("Team", TEAMS), ("Department", DEPTS),
            ("Region", REGIONS), ("Brand", BRANDS), ("Food", FOODS), ("Mode", MODES), ("Source", ENERGY),
            ("Grade", GRADES), ("Country", COUNTRIES)]
BAR_SERIES = [("Year", None), ("Store", ["Store A", "Store B", "Store C", "Store D", "Store E"]),
              ("Scenario", ["Low", "Medium", "High", "Target", "Actual", "Forecast", "Budget", "Plan"]),
              ("Group", ["Group 1", "Group 2", "Group 3", "Group 4", "Group 5"]), ("Region", REGIONS), ("Team", TEAMS),
              ("Shift", ["Morning", "Evening", "Night", "Weekend"]), ("Channel", ["Online", "Retail", "Phone", "Partner", "Kiosk"])]
BAR_MEASURES = [("Sales", ""), ("Revenue", " (USD)"), ("Units sold", ""), ("Visitors", ""), ("Energy", " (kWh)"), ("Cost", " ($)"),
                ("Score", ""), ("Orders", ""), ("Rainfall", " (mm)"), ("Profit", " (k$)"), ("Output", " (tons)"), ("Users", "")]
NICE_MAX = [1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000, 50000, 100000]


def data_linexy(rng):
    xk = rng.choice(["year", "year", "month", "week", "day", "age", "hour", "round"])
    if xk == "year":
        step = rng.choice([1, 2, 5, 5, 10]); m = rng.randint(5, 13); start = rng.randint(1900, 2024 - step * (m - 1)); xt = "Year"
    elif xk == "month":
        start, step, m, xt = 1, 1, rng.choice([6, 12, 12]), "Month"
    elif xk == "week":
        start, step, m, xt = 1, rng.choice([1, 1, 2]), rng.randint(8, 16), "Week"
    elif xk == "day":
        start, step, m, xt = 1, rng.choice([1, 2, 3, 5]), rng.randint(7, 12), "Day"
    elif xk == "age":
        start, step, m, xt = rng.choice([0, 10, 20]), rng.choice([5, 10]), rng.randint(6, 9), "Age (years)"
    elif xk == "hour":
        start, step, m, xt = 0, rng.choice([2, 3]), rng.randint(8, 12), "Hour"
    else:
        start, step, m, xt = 1, 1, rng.randint(6, 12), rng.choice(["Round", "Trial", "Level", "Session", "Step"])
    xs = [start + step * i for i in range(m)]
    yt, mag = rng.choice(YMEASURES)
    mag *= rng.choice([0.5, 1, 1, 2, 5])
    lo = rng.uniform(0.3, 3) * mag
    span = rng.uniform(0.6, 3) * mag
    dec = 0 if mag >= 100 else (1 if mag >= 5 else 2)
    fam = rng.choice(list(LEGEND_OF))
    src = {"city": CITIES, "product": PRODUCTS, "team": TEAMS, "sensor": SENSORS, "country": COUNTRIES}[fam]
    names = rng.sample(pool(src), rng.randint(2, 6))
    rows = []
    for c in names:
        v = lo + rng.uniform(0, 0.7) * span
        slope = rng.uniform(-0.12, 0.25) * span / m
        for i, x in enumerate(xs):
            if i:
                v += slope + rng.gauss(0, 0.04 * span) + (-rng.uniform(0.1, 0.25) * span if rng.random() < 0.06 else 0)
            v = min(lo + span * 1.2, max(lo * 0.5, v))
            rows.append((c, x, round(v, dec) if dec else int(round(v))))
    return "Series,X,Y", rows, {"x": xt, "y": yt, "legend": LEGEND_OF[fam], "dec": dec}


def data_heatmap(rng):
    ny = rng.randint(3, 8)
    y0 = rng.randint(1961, 1990) if CFG["strict"] else rng.randint(1949, 1985)
    months = MONTHS[:rng.choice([12, 12, 12, 6])]
    base, growth, amp, peak = rng.uniform(100, 400), rng.uniform(0.02, 0.15), rng.uniform(0.05, 0.3), rng.randint(4, 8)
    rows = []
    for yi, y in enumerate(range(y0, y0 + ny)):
        for mi, mo in enumerate(months):
            v = base * (1 + growth) ** yi * (1 + amp * math.cos(2 * math.pi * (mi - peak) / 12)) * rng.uniform(0.95, 1.05)
            rows.append((y, mo, int(round(v))))
    return "Year,Month,Passengers_thousands", rows


def data_scatter(rng):
    species = rng.sample(SPECIES_OTHER, 3) if CFG["strict"] else SPECIES_REAL
    rows = []
    for sp in species:
        cb, cf, cm_ = rng.uniform(35, 50), rng.uniform(180, 225), rng.uniform(3300, 5500)
        for _ in range(rng.randint(5, 15)):
            rows.append((sp, round(rng.gauss(cb, 2.5), 1), int(round(rng.gauss(cf, 6))), int(round(rng.gauss(cm_, 400) / 25) * 25)))
    rows.sort(key=lambda r: (r[0], r[1]))
    return "Species,Bill_length_mm,Flipper_length_mm,Body_mass_g", rows


# ------------------------------------------------------------------ renderers
def fig_to_img(fig, close=True):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, facecolor=BG)
    if close:
        plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def legend(fig, rng, title, names, cols, x=0.72, y=0.85, marker="s"):
    lx = fig.add_axes([x, y - 0.6, 0.25, 0.6]); lx.axis("off"); lx.set_xlim(0, 1); lx.set_ylim(0, 1)
    lx.text(0, 1, title, color="#f3e3a6", fontsize=10, bbox=label_box(), va="top")
    for i, (n, c) in enumerate(zip(names, cols)):
        yy = 0.88 - i * 0.09
        lx.scatter([0.04], [yy], s=50, color=c, marker=marker)
        lx.text(0.12, yy, n, color="white", fontsize=9, va="center", bbox=label_box())


def render_pie(rng, rows, spec=None):
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_axes([0.08, 0.08, 0.6, 0.78])
    rows = list(rows)
    if rng.random() < 0.5:             # pie r1: slice order is not always largest-first
        rng.shuffle(rows)
    dxr = rng.random() < 0.7           # pie r1: DxR colour order and start at 12 o'clock, clockwise
    cols = PALETTE[:len(rows)] if dxr else rng.sample(PALETTE, len(rows))
    kw = dict(startangle=90 if dxr else rng.uniform(0, 360), counterclock=False if dxr else rng.random() < 0.5)
    vals, thick, squash = [r[1] for r in rows], 0, 1.0
    if spec is not None:               # pie r2: slices cut out of a disc - exploded slices and/or a 3D thick disc
        if rng.random() < 0.35:
            out = rng.uniform(0.05, 0.16)
            kw["explode"] = [out if rng.random() < 0.75 else 0.0 for _ in rows]
        if rng.random() < 0.4:
            thick, squash, depth = rng.randint(8, 16), rng.uniform(0.45, 0.75), rng.uniform(0.15, 0.3)
            dark = [tuple(c * rng.uniform(0.55, 0.7) for c in matplotlib.colors.to_rgb(col)) for col in cols]
            for k in range(thick, 0, -1):
                ax.pie(vals, colors=dark, center=(0, -depth * k / thick), **kw)
    wedges, _ = ax.pie(vals, colors=cols, **kw)
    for w, (name, _) in zip(wedges, rows):
        a = math.radians((w.theta1 + w.theta2) / 2)
        ax.text(1.25 * math.cos(a), 1.2 * math.sin(a), name, ha="center", va="center", fontsize=rng.choice([8, 9, 10]),
                color="white", bbox=label_box())
    ax.set_aspect(squash)
    if thick:
        ax.autoscale_view()
    legend(fig, rng, spec["legend"] if spec else rng.choice(["Genre", "Category", "Type"]), [r[0] for r in rows], cols)
    fig.text(0.38, 0.93, spec["title"] if spec else rng.choice(["Sales by genre", "Share by category", "Market share"]), ha="center", color="white",
             fontsize=11, bbox=label_box(TITLE_BG))
    return fig_to_img(fig)


def render_line(rng, rows):
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_axes([0.13, 0.14, 0.62, 0.72], facecolor=BG)
    names = list(dict.fromkeys(r[0] for r in rows))
    cols = rng.sample(PALETTE[:7], len(names))
    for n, c in zip(names, cols):
        pts = [(r[1], r[2]) for r in rows if r[0] == n]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=2.2, marker="o", ms=rng.choice([3, 4, 5]))
    ax.grid(True, color="#c9ccd1", lw=0.8)
    lo, hi = min(r[2] for r in rows), max(r[2] for r in rows)
    ax.set_ylim(max(0, math.floor(lo / 10) * 10 - 10), min(100, math.ceil(hi / 10) * 10 + 5))
    from matplotlib.ticker import MultipleLocator          # run 4: finer y gridlines, so values are read more exactly
    ax.yaxis.set_major_locator(MultipleLocator(rng.choice([5, 10, 10])))
    if rng.random() < 0.5:
        ax.yaxis.set_minor_locator(MultipleLocator(rng.choice([1, 2.5])))
        ax.grid(True, which="minor", axis="y", color="#c9ccd1", lw=0.4, alpha=0.6)
    style_ticks(ax, rng.choice([8, 9]))
    ax.set_xlabel("Year", color="white", bbox=label_box(), fontsize=9)
    ax.set_ylabel("Life expectancy (years)", color="#f3e3a6", bbox=label_box(), fontsize=9)
    legend(fig, rng, "Country", names, cols, x=0.78, y=0.85, marker="o")
    fig.text(0.44, 0.93, rng.choice(["Life expectancy over time", "Life expectancy by country"]), ha="center",
             color="white", fontsize=11, bbox=label_box(TITLE_BG))
    return fig_to_img(fig)


def render_linexy(rng, rows, spec):
    from matplotlib.ticker import AutoMinorLocator, MaxNLocator
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_axes([0.15, 0.14, 0.60, 0.72], facecolor=BG)
    names = list(dict.fromkeys(r[0] for r in rows))
    cols = rng.sample(PALETTE[:7], len(names))
    for n, c in zip(names, cols):
        pts = [(r[1], r[2]) for r in rows if r[0] == n]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=2.2, marker="o", ms=rng.choice([3, 4, 5]))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=rng.choice([5, 6, 8, 10])))
    xs = sorted({r[1] for r in rows})
    if len(xs) <= 13:
        ax.set_xticks(xs)
    ax.grid(True, color="#c9ccd1", lw=0.8)
    if rng.random() < 0.5:
        ax.yaxis.set_minor_locator(AutoMinorLocator(rng.choice([2, 4, 5])))
        ax.grid(True, which="minor", axis="y", color="#c9ccd1", lw=0.4, alpha=0.6)
    style_ticks(ax, rng.choice([8, 9]))
    ax.set_xlabel(spec["x"], color="white", bbox=label_box(), fontsize=9)
    ax.set_ylabel(spec["y"], color="#f3e3a6", bbox=label_box(), fontsize=9)
    legend(fig, rng, spec["legend"], names, cols, x=0.80, y=0.85, marker="o")
    fig.text(0.45, 0.93, f"{spec['y'].split(' (')[0]} by {spec['x'].split(' (')[0].lower()}", ha="center",
             color="white", fontsize=11, bbox=label_box(TITLE_BG))
    return fig_to_img(fig)


def heat_grid(rows):
    years = sorted({r[0] for r in rows}); months = list(dict.fromkeys(r[1] for r in rows))
    vals = {(r[0], r[1]): r[2] for r in rows}
    lo = math.floor(min(vals.values()) / 100) * 100; hi = math.ceil(max(vals.values()) / 100) * 100
    return years, months, vals, lo, max(hi, lo + 200)


def render_heatmap(rng, rows):
    years, months, vals, lo, hi = heat_grid(rows)
    grid = np.array([[vals[(y, m)] for y in years] for m in months])
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_axes([0.14, 0.12, 0.6, 0.76])
    mesh = ax.pcolormesh(grid, cmap="YlOrRd", vmin=lo, vmax=hi, edgecolors="white", linewidth=1.0)
    ax.set_xticks(np.arange(len(years)) + 0.5); ax.set_xticklabels([str(y) for y in years])
    ax.set_yticks(np.arange(len(months)) + 0.5); ax.set_yticklabels(months); ax.invert_yaxis()
    style_ticks(ax, rng.choice([8, 9]))
    cax = fig.add_axes([0.79, 0.3, 0.03, 0.5])
    cb = fig.colorbar(mesh, cax=cax, ticks=np.arange(lo, hi + 1, 100 if hi - lo <= 600 else 200))
    for t in cax.get_yticklabels():
        t.set_bbox(label_box()); t.set_color("white"); t.set_fontsize(8)
    cb.outline.set_visible(False)
    fig.text(0.81, 0.84, "Passengers (thousands)", ha="center", color="#f3e3a6", fontsize=9, bbox=label_box())
    return fig_to_img(fig)


def scene_heatmap3d(rng, rows):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    years, months, vals, lo, hi = heat_grid(rows)
    nx, nz = len(years), len(months)
    cmap = matplotlib.colormaps["YlOrRd"]
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_subplot(111, projection="3d", facecolor=BG); ax.set_axis_off()
    polys = [[(years.index(y), 0, nz - 1 - months.index(m)), (years.index(y) + 1, 0, nz - 1 - months.index(m)),
              (years.index(y) + 1, 0, nz - months.index(m)), (years.index(y), 0, nz - months.index(m))] for (y, m) in vals]
    ax.add_collection3d(Poly3DCollection(polys, facecolors=[cmap((v - lo) / (hi - lo)) for v in vals.values()],
                                         edgecolors="white", linewidths=0.8))
    fs = rng.choice([7, 8, 9]) if nx <= 5 else rng.choice([6, 7])
    for i, y in enumerate(years):
        ax.text(i + 0.5, 0, -0.6, str(y), ha="center", va="center", fontsize=fs, color="white", bbox=label_box())
    for j, m in enumerate(months):
        ax.text(-0.7, 0, nz - 1 - j + 0.5, m, ha="center", va="center", fontsize=fs, color="white", bbox=label_box())
    cx, steps = nx + 0.8, 40
    strip = [[(cx, 0, nz * k / steps), (cx + 0.35, 0, nz * k / steps), (cx + 0.35, 0, nz * (k + 1) / steps), (cx, 0, nz * (k + 1) / steps)] for k in range(steps)]
    ax.add_collection3d(Poly3DCollection(strip, facecolors=[cmap((k + 0.5) / steps) for k in range(steps)], edgecolors="none"))
    for t in range(int(lo), int(hi) + 1, 100 if hi - lo <= 600 else 200):
        ax.text(cx + 0.9, 0, (t - lo) / (hi - lo) * nz, str(t), ha="center", va="center", fontsize=fs, color="white", bbox=label_box())
    ax.text(cx + 0.4, 0, nz + 0.8, "Passengers (thousands)", ha="center", fontsize=fs, color="#f3e3a6", bbox=label_box())
    ax.set_xlim(-1.5, nx + 2.2); ax.set_ylim(-1, 1); ax.set_zlim(-2, nz + 1.5)
    ax.set_box_aspect((nx + 3.7, 2, nz + 3.5))
    return fig, ax, -90.0, rng.uniform(-12, 25)


def scene_bar(rng, rows):
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_subplot(111, projection="3d", facecolor=BG)
    n, dmax = len(rows), max(r[2] for r in rows)
    ds = rng.uniform(1.0, 2.0)
    col = rng.choice(["#f28c28", "#f28c28", "#e8504a", "#45a29e", "#6c8ebf"])
    for i, (_, h, d) in enumerate(rows):
        ax.bar3d(i, 0, 0, 0.6, max(0.02, d / dmax * ds), h, color=col, shade=True, edgecolor="none")
    ax.set_xticks(np.arange(n) + 0.3); ax.set_xticklabels([r[0] for r in rows])
    yt = np.linspace(0, ds, 3); ax.set_yticks(yt); ax.set_yticklabels([str(int(round(v / ds * dmax, -1))) for v in yt])
    hmax = max(r[1] for r in rows)
    step = 1000 if hmax <= 8000 else 2000 if hmax <= 16000 else 5000
    ax.set_zticks(np.arange(0, hmax + step, step))
    ax.set_xlim(-0.3, n); ax.set_ylim(0, ds * 1.05); ax.set_zlim(0, math.ceil(hmax / step) * step)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.93, 0.94, 0.95, 1.0))
    style_ticks(ax, rng.choice([8, 9, 10]), zaxis=True)
    ax.set_zlabel("Mean price (USD)", color="#f3e3a6", fontsize=8)
    ax.set_ylabel("Number of diamonds", color="#f3e3a6", fontsize=8)
    ax.set_box_aspect((n * 0.9, ds * 2.4, 3.5))
    fig.text(0.5, 0.92, rng.choice(["Mean price by grade", "Price and count by grade"]), ha="center", color="white",
             fontsize=11, bbox=label_box(TITLE_BG))
    return fig, ax, rng.uniform(-110, -70), rng.uniform(5, 35)


def scene_scatter(rng, rows):
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_subplot(111, projection="3d", facecolor=BG)
    species = list(dict.fromkeys(r[0] for r in rows))
    cols = dict(zip(species, rng.sample(["#f28c28", "#e8508a", "#2fbf4e", "#6c8ebf", "#e9b31c"], 3)))
    for sp in species:
        pts = [r for r in rows if r[0] == sp]
        ax.scatter([p[1] for p in pts], [p[3] for p in pts], [p[2] for p in pts], color=cols[sp], s=rng.choice([10, 14, 18]), depthshade=False)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.93, 0.94, 0.95, 1.0))
    style_ticks(ax, 7, zaxis=True)
    ax.set_xlabel("Bill length (mm)", color="#f3e3a6", fontsize=8)
    ax.set_ylabel("Body mass (g)", color="#f3e3a6", fontsize=8)
    ax.set_zlabel("Flipper length (mm)", color="#f3e3a6", fontsize=8)
    fig.text(0.85, 0.82, "Species", color="#f3e3a6", fontsize=9, bbox=label_box())
    for i, sp in enumerate(species):
        fig.text(0.87, 0.77 - i * 0.045, sp, color="white", fontsize=8, bbox=label_box())
        fig.patches.append(plt.Circle((0.855, 0.778 - i * 0.045), 0.006, color=cols[sp], transform=fig.transFigure, figure=fig))
    return fig, ax, rng.uniform(-100, -50), rng.uniform(5, 30)


DXR_COLS = ["#ff9f1c", "#ff4fa3", "#7ee36b", "#ffe14d", "#4fc3f7", "#b388ff"]


def scene_line3d(rng, rows, spec):
    """Run 6: a line chart drawn the way DxR draws it in VR - a 3D box with the grid on the back wall, the lines
    floating at some depth in front of it, tick labels on the front edges, seen from below/above and from the side."""
    from matplotlib.ticker import MaxNLocator
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_subplot(111, projection="3d", facecolor=BG)
    names = list(dict.fromkeys(r[0] for r in rows))
    pal = DXR_COLS[:] if rng.random() < 0.6 else PALETTE[:7]
    cols = rng.sample(pal, len(names)) if len(names) <= len(pal) else (pal * 2)[:len(names)]
    depth = rng.uniform(0.15, 0.85)                     # where the lines float between the front and the back wall
    lw, ms = rng.choice([2, 3, 3, 4, 5]), rng.choice([3, 4, 5, 6])
    for n, c in zip(names, cols):
        pts = [(r[1], r[2]) for r in rows if r[0] == n]
        ax.plot([p[0] for p in pts], [depth] * len(pts), [p[1] for p in pts], color=c, lw=lw, marker="o", ms=ms)
    xs = sorted({r[1] for r in rows}); ys = [r[2] for r in rows]
    ax.set_ylim(0, 1); ax.set_yticks([])
    ax.zaxis.set_major_locator(MaxNLocator(nbins=rng.choice([4, 5, 6, 7])))
    pad = (max(ys) - min(ys)) * rng.uniform(0.05, 0.3)
    ax.set_zlim(min(ys) - pad, max(ys) + pad * rng.uniform(0.3, 1.0))
    if len(xs) <= 13:
        ax.set_xticks(xs)
    ax.set_position([-0.04, -0.02, 0.92, 1.0])
    ax.set_box_aspect((rng.uniform(1.5, 1.9), rng.uniform(0.12, 0.35), 1), zoom=rng.uniform(1.05, 1.2))
    ax.zaxis._axinfo["juggled"] = (1, 2, 0)            # value axis on the left, like DxR
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.93, 0.94, 0.95, 1.0))
        a._axinfo["grid"]["color"] = (0.55, 0.57, 0.6, 1.0)
    style_ticks(ax, rng.choice([7, 8]), zaxis=True)
    ax.set_xlabel(spec["x"], color="#f3e3a6", fontsize=8, bbox=label_box())
    ax.set_zlabel(spec["y"], color="#f3e3a6", fontsize=8, bbox=label_box())
    lx = rng.choice([0.82, 0.86])
    fig.text(lx, 0.82, spec["legend"], color="#f3e3a6", fontsize=9, bbox=label_box())
    for i, n in enumerate(names):
        fig.text(lx + 0.02, 0.77 - i * 0.045, n, color="white", fontsize=8, bbox=label_box())
        fig.patches.append(plt.Circle((lx + 0.005, 0.778 - i * 0.045), 0.007, color=cols[names.index(n)], transform=fig.transFigure, figure=fig))
    fig.text(0.45, 0.93, f"{spec['y'].split(' (')[0]} by {spec['x'].split(' (')[0].lower()}", ha="center", color="white",
             fontsize=11, bbox=label_box(TITLE_BG))
    return fig, ax, rng.uniform(-105, -75), rng.uniform(-4, 22)


# ------------------------------------------------------------------ camera and headset look
def homography(src, dst):
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(a, float), np.array([c for p in src for c in p], float)).tolist()


def view_flat(img, yaw_deg, pitch_deg):
    w, h = img.size
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    f, dist = 1.2 * w, 1.6 * w
    pts = []
    for x, y in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        X, Y, Z = x * math.cos(yaw), y, x * math.sin(yaw)
        Y, Z = Y * math.cos(pitch) - Z * math.sin(pitch), Y * math.sin(pitch) + Z * math.cos(pitch)
        s = f / (dist + Z); pts.append((X * s, Y * s))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    sc = min(w / (max(xs) - min(xs)), h / (max(ys) - min(ys)))
    dst = [((x - min(xs)) * sc, (y - min(ys)) * sc) for x, y in pts]
    W, H = int(math.ceil(max(d[0] for d in dst))), int(math.ceil(max(d[1] for d in dst)))
    return img.transform((max(W, 1), max(H, 1)), Image.PERSPECTIVE, homography([(0, 0), (w, 0), (w, h), (0, h)], dst), Image.BICUBIC, fillcolor=BG)


def look_params(rng):
    return {"scale": rng.uniform(0.82, 1.0), "fx": rng.random(), "fy": rng.random(), "blur": rng.uniform(0.2, 1.0) if rng.random() < 0.6 else 0,
            "color": rng.uniform(0.75, 1.25), "contrast": rng.uniform(0.85, 1.1), "gains": [rng.uniform(0.975, 1.025) for _ in range(3)],
            "bright": rng.uniform(0.92, 1.05), "shift": rng.uniform(-6, 6), "q": rng.randint(55, 90)}


def headset_look(img, p, rng, size):
    """Same placement/colour for the whole clip, with a little head jitter per frame."""
    W, H = size
    canvas = Image.new("RGB", (W, H), BG)
    s = p["scale"] * min(W / img.width, H / img.height) * rng.uniform(0.97, 1.03)
    im = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BICUBIC)
    x = int(max(0, W - im.width) * p["fx"]) + rng.randint(-12, 12); y = int(max(0, H - im.height) * p["fy"]) + rng.randint(-10, 10)
    canvas.paste(im, (x, y))
    if p["blur"]:
        canvas = canvas.filter(ImageFilter.GaussianBlur(p["blur"]))
    canvas = ImageEnhance.Contrast(ImageEnhance.Color(canvas).enhance(p["color"])).enhance(p["contrast"])
    arr = np.asarray(canvas).astype(np.float32) * np.array(p["gains"], np.float32) * p["bright"] + p["shift"]
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    buf = io.BytesIO(); canvas.save(buf, "JPEG", quality=p["q"]); buf.seek(0)
    return Image.open(buf).convert("RGB")


def to_csv(header, rows, kind):
    one = {("pie", 1), ("pieany", 1), ("line", 2), ("bar", 1)}
    return header + "\n" + "\n".join(",".join(f"{v:.1f}" if (kind, i) in one else str(v) for i, v in enumerate(r)) for r in rows) + "\n"


DATA = {"pie": data_pie, "bar": data_bar, "line": data_line, "heatmap": data_heatmap, "scatter": data_scatter,
        "linexy": data_linexy, "pieany": data_pieany, "bar3d": data_bar3d}
MIX = {"pie": 0.16, "bar": 0.30, "line": 0.14, "heatmap": 0.28, "scatter": 0.12, "linexy": 0.14, "pieany": 0.16, "bar3d": 0.3}


def make_clip(kind, rng, n, size):
    res = DATA[kind](rng)
    header, rows, spec = res[0], res[1], (res[2] if len(res) > 2 else None)
    p = look_params(rng)
    sweep = rng.uniform(40, 80) * rng.choice([-1, 1])            # degrees the viewer walks around the chart
    ts = [i / max(1, n - 1) for i in range(n)]
    frames = []
    line3d = kind in ("line", "linexy") and rng.random() < CFG.get("line3d", 0.0)
    if kind in ("bar", "scatter", "bar3d") or (kind == "heatmap" and rng.random() < 0.5) or line3d:
        if kind == "bar3d":
            fig, ax, az0, elev = scene_bar3d(rng, rows, spec)
            sweep = rng.uniform(30, 70) * rng.choice([-1, 1])
        elif line3d:
            sp = spec or {"x": "Year", "y": "Life expectancy (years)", "legend": "Country"}
            fig, ax, az0, elev = scene_line3d(rng, rows, sp)
        else:
            fig, ax, az0, elev = {"bar": scene_bar, "scatter": scene_scatter}.get(kind, scene_heatmap3d)(rng, rows)
        for t in ts:
            ax.view_init(elev=elev + rng.uniform(-2, 2), azim=az0 + sweep * (t - 0.5))
            frames.append(headset_look(fig_to_img(fig, close=False), p, rng, size))
        plt.close(fig)
    else:
        if kind == "linexy":
            img = render_linexy(rng, rows, spec)
        elif kind in ("pie", "pieany"):
            img = render_pie(rng, rows, spec)
        else:
            img = {"line": render_line, "heatmap": render_heatmap}[kind](rng, rows)
        pitch = rng.uniform(-15, 15)
        yaw0 = rng.uniform(-15, 15)
        for t in ts:
            lim = 82 if kind in ("pie", "pieany") else 70   # pie r1: the Quest walk-around reaches near edge-on views
            yaw = max(-lim, min(lim, yaw0 + sweep * (t - 0.5)))
            frames.append(headset_look(view_flat(img, yaw, pitch + rng.uniform(-2, 2)), p, rng, size))
    return frames, to_csv(header, rows, kind)


def job(args):
    split, i, kind, seed, n, size, out, strict, banned, line3d = args
    CFG["strict"], CFG["banned"], CFG["line3d"] = strict, banned, line3d
    rng = random.Random(seed)
    frames, answer = make_clip(kind, rng, n, size)
    rel = f"clips/{split}_{kind}_{i:06d}"
    os.makedirs(os.path.join(out, rel), exist_ok=True)
    paths = []
    for k, fr in enumerate(frames):
        fr.save(os.path.join(out, rel, f"f{k}.jpg"), quality=90)
        paths.append(f"{rel}/f{k}.jpg")
    return {"frames": paths, "chart": kind, "answer": answer}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(HERE, "data"))
    ap.add_argument("--train", type=int, default=2000)
    ap.add_argument("--val", type=int, default=60)
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--size", default="640x480")
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--strict", action="store_true", help="no names or years from the real test charts (recommended)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--preview", type=int, help="write one contact sheet per chart type with N clips, nothing else")
    ap.add_argument("--charts", nargs="+", choices=list(DATA), help="only these chart types, e.g. --charts line (default: all)")
    ap.add_argument("--line3d", type=float, default=0.0, help="share of line charts drawn as DxR-like 3D charts (run 6: 0.7)")
    ap.add_argument("--weights", help="mix of the chosen chart types, e.g. linexy=0.7,line=0.3 (default: built-in mix)")
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.lower().split("x"))
    banned = real_names() if a.strict else set()
    CFG["strict"], CFG["banned"], CFG["line3d"] = a.strict, banned, a.line3d
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(a.seed)
    if a.preview:
        for kind in (a.charts or list(DATA)):
            clips = [make_clip(kind, random.Random(rng.random()), a.frames, size)[0] for _ in range(a.preview)]
            tw, th = size[0] // 3, size[1] // 3
            sheet = Image.new("RGB", (tw * a.frames, th * len(clips)), "white")
            for r, fr in enumerate(clips):
                for c, im in enumerate(fr):
                    sheet.paste(im.resize((tw, th)), (c * tw, r * th))
            sheet.save(os.path.join(a.out, f"preview_{kind}.jpg"), quality=85)
            print("wrote", os.path.join(a.out, f"preview_{kind}.jpg"))
        return
    kinds = a.charts or list(MIX)
    if a.weights:
        for kv in a.weights.split(","):
            k, v = kv.split("="); MIX[k.strip()] = float(v)
    for split, n in (("train", a.train), ("val", a.val)):
        jobs = [(split, i, rng.choices(kinds, weights=[MIX[k] for k in kinds])[0], rng.random(), a.frames, size, a.out, a.strict, banned, a.line3d)
                for i in range(n)]
        with Pool(a.workers) as p, open(os.path.join(a.out, f"{split}.jsonl"), "w", encoding="utf-8") as fh:
            for k, rec in enumerate(p.imap(job, jobs, chunksize=4), 1):
                fh.write(json.dumps(rec) + "\n")
                if k % 100 == 0:
                    print(f"{split}: {k}/{n}", flush=True)
        print(f"{split}: {n} clips -> {os.path.join(a.out, split + '.jsonl')}")
    if a.strict:
        json.dump(sorted(banned), open(os.path.join(a.out, "excluded_names.json"), "w"), indent=1)
        print(f"strict: {len(banned)} real names excluded from training (list in excluded_names.json)")


if __name__ == "__main__":
    main()
