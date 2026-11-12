#!/usr/bin/env python3
"""Add the test-only control line charts to your DxR app, by copying your working line-chart spec.

    python3 control_test/make_dxr_specs.py --package ~/Projects/DxRChartsApp/Packages/com.vlm.dxrcharts
    python3 control_test/make_dxr_specs.py --package ... --charts linexy_control_D linexy_control_E linexy_control_F   (default)
    python3 control_test/make_dxr_specs.py --package ... --dry-run          # show what would change, write nothing

What it does, for each control chart:
  1. copies ground_truth/control/dxr/<chart>.csv to <package>/Charts~/DxRData/<chart>.csv
  2. copies your line-chart spec (the one whose data file has Country/Year/Life_expectancy-style columns), then
     swaps in the new data file, the new field names, the axis titles, the legend title, the chart title and, if
     the original spec fixes them, the x tick values and the scale domains
  3. adds the chart to <package>/Charts~/DxRSpecs/charts.json, after the existing charts
A backup of charts.json is written as charts.json.bak. Then in Unity: DxR Charts > Copy charts to StreamingAssets,
and DxR Charts > 4. Build and Run on Quest.
"""
import argparse
import copy
import csv
import glob
import json
import math
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CTRL = os.path.join(ROOT, "ground_truth", "control")


def nice_ticks(lo, hi, n=6):
    raw = (hi - lo) / max(1, n - 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    a, b = math.floor(lo / step) * step, math.ceil(hi / step) * step
    ticks, v = [], a
    while v <= b + step / 2:
        ticks.append(round(v, 6)); v += step
    return [int(t) if float(t).is_integer() else t for t in ticks]


def replace_fields(obj, mapping):
    if isinstance(obj, dict):
        return {k: replace_fields(v, mapping) for k, v in obj.items()}
    if isinstance(obj, list):
        return [replace_fields(v, mapping) for v in obj]
    if isinstance(obj, str) and obj in mapping:
        return mapping[obj]
    return obj


def find_line_spec(specs_dir, data_dir):
    for p in sorted(glob.glob(os.path.join(specs_dir, "*.json"))):
        if os.path.basename(p) == "charts.json" or "control" in os.path.basename(p):
            continue
        try:
            spec = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        url = (spec.get("data") or {}).get("url", "")
        enc = spec.get("encoding", {})
        if "x" in enc and "y" in enc and ("line" in os.path.basename(p).lower() or "lifeexp" in url.lower() or "life" in url.lower()):
            return p, spec, url
    raise SystemExit(f"No line-chart spec found in {specs_dir} (looked for a spec with x and y encodings and 'line' in its name)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True, help="the DxR package folder, e.g. .../Packages/com.vlm.dxrcharts")
    ap.add_argument("--charts", nargs="+", default=["linexy_control_D", "linexy_control_E", "linexy_control_F"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pkg = os.path.expanduser(a.package)
    specs_dir, data_dir = os.path.join(pkg, "Charts~", "DxRSpecs"), os.path.join(pkg, "Charts~", "DxRData")
    for d in (specs_dir, data_dir):
        if not os.path.isdir(d):
            raise SystemExit(f"Not found: {d}  (give --package the folder that contains Charts~)")
    man = json.load(open(os.path.join(CTRL, "MANIFEST.json")))["charts"]
    src_path, base, base_url = find_line_spec(specs_dir, data_dir)
    print(f"template: {os.path.relpath(src_path, pkg)}  (data {base_url})")
    old_cols = next(csv.reader(open(os.path.join(data_dir, base_url), encoding="utf-8")))[:3]
    enc = base["encoding"]
    roles = {"x": enc["x"].get("field"), "y": enc["y"].get("field")}
    series_ch = next((c for c in ("color", "detail", "shape", "label") if isinstance(enc.get(c), dict) and enc[c].get("field")), None)
    roles["s"] = enc[series_ch]["field"] if series_ch else next(c for c in old_cols if c not in (roles["x"], roles["y"]))
    print(f"template fields: series={roles['s']} x={roles['x']} y={roles['y']} (series channel: {series_ch})")

    list_path = os.path.join(specs_dir, "charts.json")
    listing = json.load(open(list_path, encoding="utf-8")) if os.path.exists(list_path) else None
    for name in a.charts:
        info = man[name]
        rows = list(csv.reader(open(os.path.join(CTRL, "dxr", f"{name}.csv"), encoding="utf-8")))
        new_s, new_x, new_y = rows[0]
        xs = sorted({float(r[1]) for r in rows[1:]}); ys = [float(r[2]) for r in rows[1:]]
        spec = replace_fields(copy.deepcopy(base), {roles["s"]: new_s, roles["x"]: new_x, roles["y"]: new_y})
        spec["data"]["url"] = f"{name}.csv"
        spec["title"] = f"{info['y_axis'].split(' (')[0]} by {info['x_axis'].lower()}"
        e = spec["encoding"]
        e["x"].setdefault("axis", {})["title"] = info["x_axis"]
        e["y"].setdefault("axis", {})["title"] = info["y_axis"]
        if series_ch:
            e[series_ch].setdefault("legend", {})["title"] = info["legend_title"]
        if "values" in e["x"].get("axis", {}):
            e["x"]["axis"]["values"] = [int(v) if v.is_integer() else v for v in xs]
        if "domain" in e["x"].get("scale", {}):
            bd, bv = base["encoding"]["x"]["scale"]["domain"], base["encoding"]["x"].get("axis", {}).get("values")
            pad = (xs[1] - xs[0]) * 0.5 if bv and len(xs) > 1 and bd[0] < min(bv) else 0
            lo, hi = xs[0] - pad, xs[-1] + pad
            e["x"]["scale"]["domain"] = [int(lo) if float(lo).is_integer() else lo, int(hi) if float(hi).is_integer() else hi]
        yt = nice_ticks(min(ys), max(ys))
        if "domain" in e["y"].get("scale", {}):
            e["y"]["scale"]["domain"] = [yt[0], yt[-1]]
        if "values" in e["y"].get("axis", {}):
            e["y"]["axis"]["values"] = yt
        out_spec = os.path.join(specs_dir, f"{name}.json")
        print(f"\n{name}: {info['y_axis']} by {info['x_axis']}, legend {info['legend_title']}")
        print(json.dumps(spec, indent=1)[:900])
        if not a.dry_run:
            shutil.copy(os.path.join(CTRL, "dxr", f"{name}.csv"), os.path.join(data_dir, f"{name}.csv"))
            json.dump(spec, open(out_spec, "w", encoding="utf-8"), indent=2)
        if listing is not None:
            items = listing.get("charts", listing) if isinstance(listing, dict) else listing
            base_name = os.path.splitext(os.path.basename(src_path))[0]
            names_now = [i if isinstance(i, str) else json.dumps(i) for i in items]
            if not any(name in n for n in names_now):
                tmpl = next((i for i in items if base_name in (i if isinstance(i, str) else json.dumps(i))), items[-1])
                new = (tmpl.replace(base_name, name) if isinstance(tmpl, str)
                       else json.loads(json.dumps(tmpl).replace(base_name, name).replace(base_url, f"{name}.csv")))
                items.append(new)
    if listing is not None and not a.dry_run:
        shutil.copy(list_path, list_path + ".bak")
        json.dump(listing, open(list_path, "w", encoding="utf-8"), indent=2)
        print(f"\ncharts.json now lists {len(listing.get('charts', listing) if isinstance(listing, dict) else listing)} charts (backup: charts.json.bak)")
    elif listing is None:
        print("\nNo charts.json found: add the new spec names to the chart list your app reads.")
    print("\nNext in Unity: DxR Charts > Copy charts to StreamingAssets, then DxR Charts > 4. Build and Run on Quest."
          if not a.dry_run else "\n(dry run: nothing written)")


if __name__ == "__main__":
    main()
