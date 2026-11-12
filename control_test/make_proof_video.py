#!/usr/bin/env python3
"""Make a downloadable proof video (and a slide image) for one tested line-chart recording.

    python3 control_test/make_proof_video.py --video videos/line_control_A.mp4 \
        --truth ground_truth/control/line_control_A.csv --pred predictions/video_qwen35_r4_line/real_video_line_control_A.csv \
        --frames real_clips/line_control_A --model "Qwen3.5-9B + LoRA (run 4)" --out proof/line_control_A_proof.mp4

The video has four parts (1920x1080, no sound):
  1. title card: chart, what was tested, sha256 of the truth table (from MANIFEST.json if present)
  2. the raw Quest recording, unedited, start to end
  3. the 8 frames the model was given
  4. the result: true lines vs the model's values, accuracy, and every value outside 5 %
It also writes <out>_result.png (part 4) for the slides. Needs ffmpeg and matplotlib.
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

W, H = 1920, 1080


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def num(v):
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except ValueError:
        return None


def read(path):
    text = open(path, encoding="utf-8").read()
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", text, re.S)
    rows = list(csv.DictReader((m.group(1) if m else text).strip().splitlines()))
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in rows]


def compare(truth, pred):
    """Every true value with the model's value at that year. A year the model left out counts as missing; only when
    the model wrote different years altogether is its curve interpolated at the true years."""
    sc, xc, yc = list(truth[0].keys())[:3]                       # Country,Year,Life_expectancy or Series,X,Y
    pc = (list(pred[0].keys()) + ["", "", ""])[:3] if pred else [sc, xc, yc]
    ps, px, py = (sc, xc, yc) if all(c in pc for c in (sc, xc, yc)) else pc
    series = {}
    for r in truth:
        series.setdefault(r[sc], []).append((num(r[xc]), num(r[yc])))
    out = []
    for c, pts in series.items():
        p = sorted((num(r.get(px)), num(r.get(py))) for r in pred if norm(r.get(ps, "")) == norm(c)
                   and num(r.get(px)) is not None and num(r.get(py)) is not None)
        aligned = sum(any(abs(a - y) < 0.5 for a, _ in p) for y, _ in pts) >= len(pts) / 2   # model used the true years
        for y, t in pts:
            v = None
            exact = [b for a, b in p if abs(a - y) < 0.5]
            if exact:
                v = exact[0]
            elif not aligned:                                  # model wrote other years (e.g. axis ticks): read its curve
                for (a0, b0), (a1, b1) in zip(p, p[1:]):
                    if a0 <= y <= a1 and a1 > a0:
                        v = b0 + (b1 - b0) * (y - a0) / (a1 - a0)
            out.append({"series": c, "year": y if y != int(y) else int(y), "truth": t, "model": v, "err": None if v is None else (v - t) / t * 100})
    return series, out


def stats(rows):
    n = len(rows)
    found = [r for r in rows if r["err"] is not None]
    return {"n": n, "w5": sum(abs(r["err"]) <= 5 for r in found), "w2": sum(abs(r["err"]) <= 2 for r in found),
            "mre": sum(abs(r["err"]) for r in found) / len(found) if found else None, "missing": n - len(found),
            "max": max((abs(r["err"]) for r in found), default=None)}


def card(path, lines, sub=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="#102a43")
    y = 0.72
    for i, t in enumerate(lines):
        fig.text(0.07, y, t, color="#ffffff" if i == 0 else "#d7e0e9", fontsize=44 if i == 0 else 26, weight="bold" if i == 0 else "normal")
        y -= 0.11 if i == 0 else 0.07
    if sub:
        fig.text(0.07, 0.08, sub, color="#9fb3c8", fontsize=16, family="monospace")
    fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)


def frames_sheet(path, frames, title):
    from PIL import Image, ImageDraw
    sheet = Image.new("RGB", (W, H), "#102a43")
    d = ImageDraw.Draw(sheet)
    d.text((60, 30), title, fill="#ffffff")
    cw, ch = 440, 330
    for i, f in enumerate(frames[:8]):
        im = Image.open(f).convert("RGB"); im.thumbnail((cw, ch))
        x, y = 60 + (i % 4) * (cw + 20), 140 + (i // 4) * (ch + 60)
        sheet.paste(im, (x, y)); d.text((x, y + ch + 8), f"frame {i + 1}", fill="#d7e0e9")
    sheet.save(path)


def result_panel(path, series, rows, st, title, model, xlab="Year", ylab="Life_expectancy"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor="#f7f4ee")
    ax = fig.add_axes([0.05, 0.12, 0.56, 0.70])
    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, (c, pts) in enumerate(series.items()):
        col = colors[i % len(colors)]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=2.5, label=f"{c} (truth)")
        mv = [(r["year"], r["model"]) for r in rows if r["series"] == c and r["model"] is not None]
        ax.scatter([p[0] for p in mv], [p[1] for p in mv], color=col, edgecolor="#1f2d3a", s=60, zorder=3, marker="D")
    ax.set_xlabel(xlab, fontsize=14); ax.set_ylabel(ylab, fontsize=14); ax.grid(alpha=0.3)
    ax.legend(fontsize=11, loc="best"); ax.set_title("lines = true values   ◆ = values the model wrote", fontsize=14)
    fig.text(0.05, 0.92, title, fontsize=30, weight="bold", color="#102a43")
    fig.text(0.05, 0.87, model, fontsize=16, color="#5b6b7b")
    x = 0.65
    fig.text(x, 0.76, f"{100 * st['w5'] / st['n']:.1f} %", fontsize=64, weight="bold", color="#c2410c")
    fig.text(x, 0.71, f"within 5 %  ({st['w5']} / {st['n']} values)", fontsize=18, color="#1f2d3a")
    fig.text(x, 0.64, f"within 2 %: {st['w2']} / {st['n']}", fontsize=18, color="#1f2d3a")
    fig.text(x, 0.60, f"mean error: {st['mre']:.2f} %" if st["mre"] is not None else "mean error: -", fontsize=18, color="#1f2d3a")
    fig.text(x, 0.56, f"largest error: {st['max']:.1f} %" if st["max"] is not None else "", fontsize=18, color="#1f2d3a")
    bad = [r for r in rows if r["err"] is None or abs(r["err"]) > 5]
    fig.text(x, 0.48, "Values outside 5 %:" if bad else "Every value is within 5 %.", fontsize=18, weight="bold", color="#102a43")
    y = 0.44
    for r in bad[:12]:
        m = "missing" if r["model"] is None else f"{r['model']:g} ({r['err']:+.1f} %)"
        fig.text(x, y, f"{r['series']} at {r['year']}: truth {r['truth']:g}, model {m}", fontsize=14, color="#b91c1c"); y -= 0.033
    if len(bad) > 12:
        fig.text(x, y, f"... and {len(bad) - 12} more", fontsize=14, color="#b91c1c")
    fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True); ap.add_argument("--truth", required=True); ap.add_argument("--pred", required=True)
    ap.add_argument("--frames", help="folder with the 8 frames the model saw (f0.jpg ... f7.jpg)")
    ap.add_argument("--model", default="Qwen3.5-9B + LoRA (run 4)"); ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default=None)
    a = ap.parse_args()
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            raise SystemExit(f"{t} not found")
    name = os.path.splitext(os.path.basename(a.video))[0]
    series, rows = compare(read(a.truth), read(a.pred))
    st = stats(rows)
    sha = hashlib.sha256(open(a.truth, "rb").read()).hexdigest()
    man = a.manifest or os.path.join(os.path.dirname(os.path.abspath(a.truth)), "MANIFEST.json")
    meta = json.load(open(man)) if os.path.exists(man) else {}
    created = meta.get("created", "")
    info = meta.get("charts", {}).get(name, {})
    xlab, ylab = info.get("x_axis", "Year"), info.get("y_axis", "Life_expectancy")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    tmp = tempfile.mkdtemp()
    card(f"{tmp}/1.png", [f"Line chart test: {name}", f"{len(series)} lines, {st['n']} values ({ylab} by {xlab}), random numbers that exist nowhere else",
                          "Model never trained on this chart or its values", "Next: the raw Quest 2 recording, unedited"],
         f"truth table sha256 {sha}" + (f"   fixed {created}" if created else ""))
    card(f"{tmp}/2.png", ["Raw Quest 2 recording", "unedited, full length"])
    frames = sorted(glob.glob(os.path.join(a.frames, "f*.jpg")), key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0)) if a.frames else []
    if frames:
        frames_sheet(f"{tmp}/3.png", frames, "The 8 frames the model was given (spread over the whole video)")
    result_panel(f"{tmp}/4.png", series, rows, st, f"Result: {name}", a.model, xlab, ylab)
    shutil.copy(f"{tmp}/4.png", os.path.splitext(a.out)[0] + "_result.png")
    still = lambda png, sec, out: subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(sec), "-i", png, "-r", "30",
                                                  "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264", out], check=True)
    parts = []
    still(f"{tmp}/1.png", 5, f"{tmp}/p1.mp4"); parts.append("p1.mp4")
    still(f"{tmp}/2.png", 2, f"{tmp}/p2.mp4"); parts.append("p2.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-an", "-r", "30",
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
                    "-c:v", "libx264", f"{tmp}/p3.mp4"], check=True); parts.append("p3.mp4")
    if frames:
        still(f"{tmp}/3.png", 6, f"{tmp}/p4.mp4"); parts.append("p4.mp4")
    still(f"{tmp}/4.png", 12, f"{tmp}/p5.mp4"); parts.append("p5.mp4")
    open(f"{tmp}/list.txt", "w").write("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-c", "copy", os.path.abspath(a.out)],
                   check=True, cwd=tmp)
    print(f"{name}: {st['w5']}/{st['n']} within 5 %, {st['w2']} within 2 %, mean error "
          f"{st['mre']:.2f} %" if st["mre"] is not None else f"{name}: no values read")
    print("proof video ->", a.out, "| slide image ->", os.path.splitext(a.out)[0] + "_result.png")


if __name__ == "__main__":
    main()
