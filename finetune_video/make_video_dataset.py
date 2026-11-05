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
    n = rng.randint(4, 9)
    names = rng.sample(pool(GENRES), n)
    w = np.array([rng.random() ** 1.6 + 0.04 for _ in range(n)])
    share = np.round(w / w.sum() * 100, 1)
    share[np.argmax(share)] += round(100 - share.sum(), 1)
    return "Genre,Share_percent", [(names[i], round(float(share[i]), 1)) for i in np.argsort(-share)]


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


def render_pie(rng, rows):
    fig = plt.figure(figsize=(8, 6), facecolor=BG)
    ax = fig.add_axes([0.08, 0.08, 0.6, 0.78])
    cols = rng.sample(PALETTE, len(rows))
    wedges, _ = ax.pie([r[1] for r in rows], colors=cols, startangle=rng.uniform(0, 360), counterclock=rng.random() < 0.5)
    for w, (name, _) in zip(wedges, rows):
        a = math.radians((w.theta1 + w.theta2) / 2)
        ax.text(1.25 * math.cos(a), 1.2 * math.sin(a), name, ha="center", va="center", fontsize=rng.choice([8, 9, 10]),
                color="white", bbox=label_box())
    ax.set_aspect("equal")
    legend(fig, rng, rng.choice(["Genre", "Category", "Type"]), [r[0] for r in rows], cols)
    fig.text(0.38, 0.93, rng.choice(["Sales by genre", "Share by category", "Market share"]), ha="center", color="white",
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
    one = {("pie", 1), ("line", 2), ("bar", 1)}
    return header + "\n" + "\n".join(",".join(f"{v:.1f}" if (kind, i) in one else str(v) for i, v in enumerate(r)) for r in rows) + "\n"


DATA = {"pie": data_pie, "bar": data_bar, "line": data_line, "heatmap": data_heatmap, "scatter": data_scatter}
MIX = {"pie": 0.16, "bar": 0.30, "line": 0.14, "heatmap": 0.28, "scatter": 0.12}


def make_clip(kind, rng, n, size):
    header, rows = DATA[kind](rng)
    p = look_params(rng)
    sweep = rng.uniform(40, 80) * rng.choice([-1, 1])            # degrees the viewer walks around the chart
    ts = [i / max(1, n - 1) for i in range(n)]
    frames = []
    if kind in ("bar", "scatter") or (kind == "heatmap" and rng.random() < 0.5):
        fig, ax, az0, elev = {"bar": scene_bar, "scatter": scene_scatter}.get(kind, scene_heatmap3d)(rng, rows)
        for t in ts:
            ax.view_init(elev=elev + rng.uniform(-2, 2), azim=az0 + sweep * (t - 0.5))
            frames.append(headset_look(fig_to_img(fig, close=False), p, rng, size))
        plt.close(fig)
    else:
        img = {"pie": render_pie, "line": render_line, "heatmap": render_heatmap}[kind](rng, rows)
        pitch = rng.uniform(-15, 15)
        yaw0 = rng.uniform(-15, 15)
        for t in ts:
            yaw = max(-70, min(70, yaw0 + sweep * (t - 0.5)))
            frames.append(headset_look(view_flat(img, yaw, pitch + rng.uniform(-2, 2)), p, rng, size))
    return frames, to_csv(header, rows, kind)


def job(args):
    split, i, kind, seed, n, size, out, strict, banned = args
    CFG["strict"], CFG["banned"] = strict, banned
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
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.lower().split("x"))
    banned = real_names() if a.strict else set()
    CFG["strict"], CFG["banned"] = a.strict, banned
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
    for split, n in (("train", a.train), ("val", a.val)):
        jobs = [(split, i, rng.choices(kinds, weights=[MIX[k] for k in kinds])[0], rng.random(), a.frames, size, a.out, a.strict, banned)
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
