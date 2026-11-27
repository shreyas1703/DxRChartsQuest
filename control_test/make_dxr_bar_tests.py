#!/usr/bin/env python3
"""Adds the test-only 3D bar chart N (test score by class and round) to your DxR Unity app. Self-contained: needs only Python 3.

    python3 ~/Downloads/make_dxr_bar_tests.py --dry-run     # shows your bar spec and what it will write; writes nothing
    python3 ~/Downloads/make_dxr_bar_tests.py               # writes the 4 charts

It copies your working DxR bar spec (bar_diamonds_clarity.json, or the first spec whose mark is bar/cube), keeps its
look, and swaps in: the data file, title, x = category (front), z = series (depth), y = value (bar height, 0 .. round
maximum with round ticks), colour = series with a legend. Data files go to Charts~/DxRData, specs to Charts~/DxRSpecs,
and each chart is added to charts.json (backup: charts.json.bak). Run it again any time: it overwrites its own chart.

These values are TEST ONLY. They are never used for training (training is synthetic; these names are banned there).
Truth table: ground_truth/control/bar3d_control_N.csv; its sha256 is in ground_truth/control/MANIFEST_bar.json (seed 20261115).
"""
import argparse, copy, csv, glob, json, math, os, shutil

DEFAULT_PKG = "~/Projects2/DxRChartsApp/Packages/com.vlm.dxrcharts"

CHARTS = {
    "bar3d_control_N": dict(title="Test score by class and round", measure="Score", cat="Class", ser="Round", top=10,
        cols=("class", "round", "value"),
        rows=[("Class Red", "Round 1", 8.3), ("Class Red", "Round 2", 5.1), ("Class Red", "Round 3", 7.0),
              ("Class Red", "Round 4", 4.3), ("Class Blue", "Round 1", 9.4), ("Class Blue", "Round 2", 5.9),
              ("Class Blue", "Round 3", 3.3), ("Class Blue", "Round 4", 1.7)]),
}


def nice_ticks(top_value):
    raw = top_value / 5
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    n = math.ceil(top_value / step - 1e-9)
    return [int(i * step) if float(i * step).is_integer() else round(i * step, 6) for i in range(n + 1)]


def mark_of(spec):
    m = spec.get("mark")
    return (m.get("type") if isinstance(m, dict) else m) or ""


def find_bar_spec(specs_dir, given):
    if given:
        p = given if os.path.isabs(os.path.expanduser(given)) else os.path.join(specs_dir, given)
        return os.path.expanduser(p), json.load(open(os.path.expanduser(p), encoding="utf-8"))
    paths = sorted(glob.glob(os.path.join(specs_dir, "*.json")))
    paths.sort(key=lambda p: os.path.basename(p) != "bar_diamonds_clarity.json")
    for p in paths:
        b = os.path.basename(p)
        if b.startswith("charts") or "control" in b:
            continue
        try:
            s = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if mark_of(s) in ("bar", "cube") or b == "bar_diamonds_clarity.json":
            return p, s
    raise SystemExit(f"No bar spec found in {specs_dir}. Run again with --template <your bar spec .json>")


def axis(e, title, values=None):
    ax = e.get("axis") if isinstance(e.get("axis"), dict) else {}
    ax["title"] = title
    if values is not None:
        ax["values"] = values
    else:
        ax.pop("values", None)
    e["axis"] = ax
    return e


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", default=DEFAULT_PKG, help="the DxR package folder that contains Charts~")
    ap.add_argument("--template", help="your working bar spec (file name in DxRSpecs or a full path)")
    ap.add_argument("--charts", nargs="+", default=list(CHARTS))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    pkg = os.path.expanduser(a.package)
    S, D = os.path.join(pkg, "Charts~", "DxRSpecs"), os.path.join(pkg, "Charts~", "DxRData")
    for d in (S, D):
        if not os.path.isdir(d):
            raise SystemExit(f"Not found: {d}\nGive --package the folder that contains Charts~")
    tpath, base = find_bar_spec(S, a.template)
    tname = os.path.splitext(os.path.basename(tpath))[0]
    turl = (base.get("data") or {}).get("url", "")
    print(f"TEMPLATE {os.path.basename(tpath)}  mark={mark_of(base)}  data={turl}")
    print(json.dumps(base, indent=1)[:2500])
    enc0 = base.get("encoding", {})

    list_path = os.path.join(S, "charts.json")
    listing = json.load(open(list_path, encoding="utf-8")) if os.path.exists(list_path) else None
    items = (listing.get("charts", listing) if isinstance(listing, dict) else listing) if listing is not None else None

    print("\nNumbers on bars: every text/label/tooltip channel is removed, so the bars show NO values "
          "(the axes keep their tick numbers and names).")
    for name in a.charts:
        c = CHARTS[name]
        fc, fs, fv = c["cols"]
        cats = list(dict.fromkeys(r[0] for r in c["rows"]))
        sers = list(dict.fromkeys(r[1] for r in c["rows"]))
        ticks = nice_ticks(c["top"])
        spec = copy.deepcopy(base)
        spec["title"] = c["title"]
        spec["data"] = {**(base.get("data") if isinstance(base.get("data"), dict) else {}), "url": f"{name}.csv"}
        spec["data"].pop("values", None)
        e = spec.setdefault("encoding", {})
        # template channels that read a template column: the one with the bar's value (e.g. height) now reads our
        # value column, the category one our category column; anything else (opacity, tooltip ...) is dropped
        tf = {ch: d.get("field") for ch, d in enc0.items() if isinstance(d, dict) and d.get("field")}
        tx, ty = tf.get("x"), tf.get("y")
        for ch in list(e):
            if ch in ("x", "y", "z", "color") or not (isinstance(e[ch], dict) and e[ch].get("field")):
                continue
            if e[ch]["field"] == ty:
                e[ch]["field"] = fv
                if isinstance(e[ch].get("scale"), dict):
                    e[ch]["scale"]["domain"] = [0, ticks[-1]]
                print(f"  template channel '{ch}' (reads {ty}) now reads {fv}")
            elif e[ch]["field"] == tx:
                e[ch]["field"] = fc
            else:
                e.pop(ch)
        # NO NUMBERS ON THE BARS: remove every value-label / text / tooltip channel and mark option
        for ch in list(e):
            if any(w in ch.lower() for w in ("text", "label", "tooltip")):
                e.pop(ch)
        if isinstance(spec.get("mark"), dict):
            for k in list(spec["mark"]):
                if any(w in k.lower() for w in ("text", "label", "tooltip", "value")):
                    spec["mark"].pop(k)
        for k in list(spec):
            if k.lower() in ("labels", "showvalues", "valuelabels", "text", "tooltip"):
                spec.pop(k)
        def chan(ch):
            d = copy.deepcopy(e.get(ch)) if isinstance(e.get(ch), dict) else {}
            d.pop("aggregate", None); d.pop("bin", None); d.pop("value", None)
            return d
        x = chan("x"); x.update(field=fc, type="nominal")
        x.pop("scale", None)          # let DxR pick its own band scale (an explicit domain/range breaks DxR ordinal scales)
        e["x"] = axis(x, c["cat"])
        y = chan("y"); y.update(field=fv, type="quantitative")
        y["scale"] = {k: v for k, v in (y.get("scale") or {}).items() if k not in ("domain", "type")}
        y["scale"]["domain"] = [0, ticks[-1]]
        e["y"] = axis(y, c["measure"], ticks)
        z = copy.deepcopy(x) if not isinstance(e.get("z"), dict) or e["z"].get("value") is not None else chan("z")
        z.update(field=fs, type="nominal")
        z.pop("scale", None)
        e["z"] = axis(z, c["ser"])
        legend = ((enc0.get("color") or {}).get("legend") if isinstance((enc0.get("color") or {}).get("legend"), dict) else {}) or {}
        col = {"field": fs, "type": "nominal", "legend": {**legend, "title": c["ser"]}}
        tsc = (enc0.get("color") or {}).get("scale")
        if isinstance(tsc, dict):     # keep the template's own colour scheme (it builds), minus its categories
            tsc = {k: v for k, v in tsc.items() if k != "domain" and not isinstance(v, list)}
            if tsc:
                col["scale"] = tsc
        e["color"] = col
        # series need real depth, or all parks/phases/rounds sit in the same plane and hide each other
        spec["depth"] = max(int(spec.get("depth") or 0), 450 if len(sers) > 1 else 150)
        print(f"\n{name}: {c['title']}  {len(cats)} x {len(sers)} = {len(c['rows'])} bars, y axis 0..{ticks[-1]} ticks {ticks}")
        if name == a.charts[0]:
            print(json.dumps(spec, indent=1))
        if not a.dry_run:
            with open(os.path.join(D, f"{name}.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh); w.writerow([fc, fs, fv]); w.writerows(c["rows"])
            json.dump(spec, open(os.path.join(S, f"{name}.json"), "w", encoding="utf-8"), indent=2)
        if items is not None and not any(name in (i if isinstance(i, str) else json.dumps(i)) for i in items):
            tmpl = next((i for i in items if tname in (i if isinstance(i, str) else json.dumps(i))), items[-1])
            new = (tmpl.replace(tname, name) if isinstance(tmpl, str)
                   else json.loads(json.dumps(tmpl).replace(tname, name).replace(turl, f"{name}.csv") if turl else
                                   json.dumps(tmpl).replace(tname, name)))
            items.append(new)
            print("  charts.json entry:", json.dumps(new))
    if a.dry_run:
        print("\n(dry run: nothing written)")
        return
    if listing is not None:
        shutil.copy(list_path, list_path + ".bak")
        json.dump(listing, open(list_path, "w", encoding="utf-8"), indent=2)
        print(f"\ncharts.json updated (backup charts.json.bak): {len(items)} charts")
    else:
        print("\nNo charts.json found: add bar3d_control_N.json to the chart list your app reads.")
    print("Wrote", ", ".join(f"{n}.json" for n in a.charts), "and their .csv files.")
    print("Next in Unity: DxR Charts > Copy charts to StreamingAssets, press Play to check, then DxR Charts > 4. Build and Run on Quest.")


if __name__ == "__main__":
    main()
