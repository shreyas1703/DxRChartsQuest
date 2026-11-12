#!/usr/bin/env python3
"""Control test: brand-new line charts with RANDOM values that exist nowhere else (not in Gapminder, not online,
not in training). Build them in DxR exactly like the Gapminder line chart, record them on the Quest, and test the
fine-tuned model on them. If it reads them as well as the Gapminder chart, it reads charts - it does not recall data.

    python3 control_test/make_control_charts.py                 # writes ground_truth/control/ + previews + manifest

Outputs
  ground_truth/control/line_control_A.csv ...   truth tables, header Country,Year,Life_expectancy (scorer + DxR data)
  ground_truth/control/dxr/line_control_A.csv   the same data with Gapminder-style columns country,year,lifeExp
  ground_truth/control/preview_*.png       how each chart should look (to check the DxR build)
  ground_truth/control/MANIFEST.json       seed, design, number of values and sha256 of every truth file

Commit MANIFEST.json to GitHub BEFORE recording: its timestamp and hashes prove the truth tables were fixed before
the model ever saw the videos.
"""
import csv
import datetime
import hashlib
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "ground_truth", "control")
SEED = 20261120

# Three designs: same layout as the Gapminder chart, fewer/longer steps with crossings, and a harder busy chart.
DESIGNS = {
    "line_control_A": {"what": "same layout as the Gapminder chart (4 lines, 1952-2007 every 5 years), new random values",
                       "names": ["Brazil", "Kenya", "Norway", "Peru"], "start": 1952, "step": 5, "points": 12, "lo": 32, "hi": 84},
    "line_control_B": {"what": "3 lines, 1960-2010 every 10 years, sharp rise and fall",
                       "names": ["Egypt", "Canada", "Vietnam"], "start": 1960, "step": 10, "points": 6, "lo": 35, "hi": 82},
    "line_control_C": {"what": "harder: 6 lines, 1950-2010 every 5 years (78 values), dips and crossings",
                       "names": ["Mexico", "Ghana", "Poland", "Nepal", "Chile", "Morocco"], "start": 1950, "step": 5, "points": 13,
                       "lo": 30, "hi": 86},
    # other axes: not life expectancy, not countries, not years (chart type "linexy", header Series,X,Y)
    "linexy_control_D": {"what": "monthly sales of 3 products (x = month 1-12, y = thousand units)",
                         "names": ["Product A", "Product B", "Product C"], "start": 1, "step": 1, "points": 12, "lo": 120, "hi": 480,
                         "dec": 0, "legend": "Product", "x": "Month", "y": "Sales (thousand units)", "dxr": ["product", "month", "sales"]},
    "linexy_control_E": {"what": "energy use of 4 stations through the day (x = hour 0-22, y = kWh)",
                         "names": ["Station A", "Station B", "Station C", "Station D"], "start": 0, "step": 2, "points": 12, "lo": 210,
                         "hi": 890, "dec": 0, "legend": "Station", "x": "Hour", "y": "Energy use (kWh)", "dxr": ["station", "hour", "energy_kwh"]},
    "linexy_control_F": {"what": "price of 3 items over 12 days, small decimal values (x = day, y = dollars)",
                         "names": ["Coffee", "Bread", "Milk"], "start": 1, "step": 1, "points": 12, "lo": 2.4, "hi": 9.8,
                         "dec": 2, "legend": "Item", "x": "Day", "y": "Price ($)", "dxr": ["item", "day", "price_usd"]},
}


def series(rng, d, k):
    """A random but chart-like curve: random start, random trend, noise, sometimes a dip or a turn."""
    n, lo, hi, dec = d["points"], d["lo"], d["hi"], d.get("dec", 1)
    span = hi - lo
    v = rng.uniform(lo, lo + span * 0.6)
    slope = rng.uniform(-0.012, 0.05) * span
    dip_at = rng.randrange(2, n - 1) if rng.random() < 0.5 else None
    turn_at = rng.randrange(n // 2, n) if rng.random() < 0.35 else None
    out = []
    for i in range(n):
        if i:
            if turn_at is not None and i >= turn_at:
                slope = -abs(slope) * 0.8
            v += slope + rng.gauss(0, 0.021 * span)
            if dip_at == i:
                v -= rng.uniform(0.08, 0.17) * span
            if dip_at is not None and i == dip_at + 1:
                v += rng.uniform(0.08, 0.15) * span
        v = min(hi, max(lo, v))
        out.append(round(v, dec) if dec else int(round(v)))
    return out


def preview(name, d, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5), dpi=110)
    for c in d["names"]:
        pts = [(x, v) for cc, x, v in rows if cc == c]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", ms=4, lw=2, label=c)
    ax.set_title(f"{name}: {d['what']}", fontsize=9)
    ax.set_xlabel(d.get("x", "Year")); ax.set_ylabel(d.get("y", "Life_expectancy")); ax.grid(alpha=0.3)
    ax.set_xticks([d["start"] + d["step"] * i for i in range(d["points"])] if d["points"] <= 13 and "x" in d else ax.get_xticks())
    ax.legend(fontsize=8, title=d.get("legend", "Country")); fig.tight_layout(); fig.savefig(os.path.join(OUT, f"preview_{name}.png")); plt.close(fig)


def main():
    os.makedirs(os.path.join(OUT, "dxr"), exist_ok=True)
    manifest = {"created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "seed": SEED,
                "purpose": "control line charts with random values for the generalisation test", "charts": {}}
    for k, (name, d) in enumerate(DESIGNS.items()):
        rng = random.Random(SEED + k)
        rows = []
        for i, c in enumerate(d["names"]):
            for j, v in enumerate(series(rng, d, i)):
                rows.append((c, d["start"] + d["step"] * j, v))
        path = os.path.join(OUT, f"{name}.csv")
        head = ["Series", "X", "Y"] if name.startswith("linexy") else ["Country", "Year", "Life_expectancy"]
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(head); w.writerows(rows)
        with open(os.path.join(OUT, "dxr", f"{name}.csv"), "w", newline="") as fh:
            w = csv.writer(fh); w.writerow(d.get("dxr", ["country", "year", "lifeExp"])); w.writerows(rows)
        preview(name, d, rows)
        manifest["charts"][name] = {"design": d["what"], "series": d["names"], "x_axis": d.get("x", "Year"),
                                    "y_axis": d.get("y", "Life expectancy"), "legend_title": d.get("legend", "Country"), "x_values": f"{d['start']}-{d['start'] + d['step'] * (d['points'] - 1)} every {d['step']}",
                                    "values": len(rows), "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest()}
        print(f"{name}: {len(d['names'])} lines x {d['points']} points = {len(rows)} values -> {os.path.relpath(path, ROOT)}")
    json.dump(manifest, open(os.path.join(OUT, "MANIFEST.json"), "w"), indent=2)
    print("manifest ->", os.path.relpath(os.path.join(OUT, "MANIFEST.json"), ROOT))


if __name__ == "__main__":
    main()
