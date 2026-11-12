#!/usr/bin/env python3
"""Run 3 evaluation: Qwen3.5 base vs Qwen3.5 + video LoRA, on your REAL Quest videos (8 frames each).

    python3 finetune_video/eval_video.py --model unsloth/Qwen3.5-9B --name qwen35_base
    python3 finetune_video/eval_video.py --model lora_qwen35_video --name qwen35_lora
    python3 finetune_video/eval_video.py --compare                      # -> compare_video.md

Test sets
  real       real_clips/real.jsonl (made by sample_real_videos.py): every frame of each Quest video goes in as one
             input; the model gets ONLY the frames and the prompt - no values, names or row count. The answer is
             scored against ground_truth/ afterwards (the truth table is never shown to the model).
  synthetic  --val-n clips of finetune_video/data/val.jsonl (unseen generated clips).
--compare also adds the earlier Qwen3-VL best-frame results (base / run 1 / run 2) from results_ft.csv if present.
Results: results_video.csv; answers: predictions/video_<name>/.
"""
import argparse
import csv
import datetime
import importlib.util
import json
import os
import statistics
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "vlm_eval", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


vlm, st = _load("run_local_vlm"), _load("score_tables")
_fb = importlib.util.module_from_spec(importlib.util.spec_from_file_location("vscore", os.path.join(HERE, "vscore.py")))
_fb.__spec__.loader.exec_module(_fb)
for _n in ("GT", "FILES", "read", "num", "norm", "score_labeled", "score_scatter", "score_line", "score_linexy"):
    if not hasattr(st, _n):
        setattr(st, _n, getattr(_fb, _n))          # fill in anything missing from vlm_eval/score_tables.py
COLS = ["time", "set", "model", "input", "chart", "clip", "frames", "seconds", "measure", "structure", "value_acc", "value_mre", "flags", "prediction"]


# ------------------------------------------------------------------ scoring (same rules as vlm_eval/experiment.py)
def flags_of(pred):
    if not pred:
        return "empty"
    out = []
    if len(pred) >= 4 and len({tuple(sorted(r.items())) for r in pred}) <= len(pred) / 2:
        out.append("repeated")
    vals = {}
    for r in pred:
        for k, v in r.items():
            if k != "Year" and st.num(v) is not None:
                vals.setdefault(k, set()).add(st.num(v))
    if len(pred) >= 4 and any(len(s) == 1 for s in vals.values()):
        out.append("constant")
    return "|".join(out)


def scatter_summary(gt, pred):
    axes = ["Bill_length_mm", "Flipper_length_mm", "Body_mass_g"]
    errs, cnt = [], []
    for sp in sorted({r["Species"] for r in gt}):
        g = [r for r in gt if r["Species"] == sp]
        p = [r for r in pred if st.norm(r.get("Species", "")) == st.norm(sp) and all(st.num(r.get(x)) is not None for x in axes)]
        cnt.append(abs(len(p) - len(g)) / len(g))
        for x in axes:
            tm = statistics.mean(st.num(r[x]) for r in g)
            errs.append(abs(statistics.mean(st.num(r[x]) for r in p) - tm) / tm if p else 1.0)
    return round(1 - min(1, statistics.mean(cnt)), 3), round(sum(e <= 0.05 for e in errs) / len(errs), 3), round(statistics.mean(errs), 4)


def score(chart, pred_path, truth_csv=None):
    if truth_csv is None:
        gt = st.read(os.path.join(st.GT, st.FILES[chart]))
    else:
        d = tempfile.mkdtemp(); p = os.path.join(d, "t.csv"); open(p, "w").write(truth_csv); gt = st.read(p)
    try:
        pred = st.read(pred_path)
    except Exception:
        pred = []
    fl = flags_of(pred)
    if not pred:
        return [{"measure": "all", "structure": 0, "value_acc": 0, "value_mre": "", "flags": "empty"}]
    if chart == "scatter":
        r = st.score_scatter(gt, pred)
        s_str, s_acc, s_mre = scatter_summary(gt, pred)
        return [{"measure": "points", "structure": r["point_recall"], "value_acc": r["all_axes_within_5pct"], "value_mre": "", "flags": fl},
                {"measure": "summary", "structure": s_str, "value_acc": s_acc, "value_mre": s_mre, "flags": fl}]
    if chart == "linexy":
        r = st.score_linexy(gt, pred)
        return [{"measure": "Y", "structure": round(r["series_found"] / r["series_true"], 3),
                 "value_acc": r["curve_within_5pct"], "value_mre": r["curve_mean_rel_error"] if r["curve_mean_rel_error"] is not None else "", "flags": fl}]
    if chart == "line":
        r = st.score_line(gt, pred)
        return [{"measure": "Life_expectancy", "structure": round(r["series_found"] / r["series_true"], 3),
                 "value_acc": r.get("curve_within_5pct", 0), "value_mre": r.get("curve_mean_rel_error", ""), "flags": fl}]
    r = st.score_labeled(chart, gt, pred)
    out = [{"measure": c, "structure": r["row_recall"], "value_acc": m["relaxed_accuracy"],
            "value_mre": m["mean_rel_error"] if m["mean_rel_error"] is not None else "", "flags": fl}
           for c, m in r["columns"].items() if not (chart == "pie" and c != "Share_percent")]
    return out or [{"measure": "all", "structure": r["row_recall"], "value_acc": 0, "value_mre": "", "flags": fl}]


def control_truth(video):
    """Truth table of a control recording (ground_truth/control/<video>.csv), or None for the original charts."""
    p = os.path.join(ROOT, "ground_truth", "control", f"{video}.csv")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else None


# ------------------------------------------------------------------ model
def load_image(path, max_side):
    from PIL import Image
    img = Image.open(path).convert("RGB")
    s = max_side / max(img.size)
    return img.resize((round(img.width * s), round(img.height * s))) if s < 1 else img


def evaluate(a):
    from unsloth import FastVisionModel
    import torch
    model, tok = FastVisionModel.from_pretrained(a.model, load_in_4bit=a.load_4bit, max_seq_length=8192)
    FastVisionModel.for_inference(model)
    decode = getattr(tok, "decode", None) or tok.tokenizer.decode

    def ask(chart, frames):
        prompt = vlm.chart_prompt(chart)
        msgs = [{"role": "user", "content": [{"type": "image"} for _ in frames] + [{"type": "text", "text": prompt}]}]
        try:
            text = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False)
        except TypeError:
            text = tok.apply_chat_template(msgs, add_generation_prompt=True)
        inputs = tok(images=frames, text=[text], add_special_tokens=False, return_tensors="pt").to("cuda")
        t0 = datetime.datetime.now()
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=1600 if chart == "scatter" else 2400, do_sample=False, use_cache=True)
        ans = decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return prompt, ans, round((datetime.datetime.now() - t0).total_seconds(), 1)

    outdir = os.path.join(ROOT, "predictions", f"video_{a.name}")
    os.makedirs(outdir, exist_ok=True)
    new = not os.path.exists(a.results)
    fh = open(a.results, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=COLS)
    if new:
        w.writeheader()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")

    def one(set_, inp, chart, clip, paths, truth=None):
        frames = [load_image(p, a.max_side) for p in paths]
        prompt, ans, secs = ask(chart, frames)
        name = f"{set_}_{inp}_{clip}"
        p = os.path.join(outdir, name + ".csv")
        open(p, "w", encoding="utf-8").write(vlm.extract_csv(ans, vlm.expected_header(prompt)))
        json.dump({"model": a.model, "frames": paths, "answer": ans, "seconds": secs}, open(os.path.join(outdir, name + ".json"), "w"), indent=1)
        for m in score(chart, p, truth):
            w.writerow({"time": stamp, "set": set_, "model": a.name, "input": inp, "chart": chart, "clip": clip,
                        "frames": len(paths), "seconds": secs, "prediction": os.path.relpath(p, ROOT), **m})
            fh.flush()
            print(f"  {set_:9} {inp:6} {chart:8} {clip:14} {m['measure']:20} structure {m['structure']}  within5% {m['value_acc']}  {m['flags']}")

    if not a.skip_real:
        base = os.path.dirname(os.path.abspath(a.real))
        for r in (json.loads(l) for l in open(a.real, encoding="utf-8")):
            if a.charts and r["chart"] not in a.charts or a.videos and r["video"] not in a.videos:
                continue
            one("real", "video", r["chart"], r["video"], [os.path.join(base, f) for f in r["frames"]], truth=control_truth(r["video"]))
        if a.best and os.path.exists(a.frames_csv):            # optional: the single best frame, for comparison
            for r in csv.DictReader(open(a.frames_csv, encoding="utf-8")):
                if r.get("best", "").strip() == "1" and (not a.charts or r["chart"] in a.charts):
                    f = r["file"] if os.path.isabs(r["file"]) else os.path.join(ROOT, r["file"])
                    if os.path.exists(f):
                        one("real", "best", r["chart"], r["chart"] + "_best", [f])
    if a.val_n:
        base = os.path.dirname(os.path.abspath(a.val))
        vals = [r for r in (json.loads(l) for l in open(a.val, encoding="utf-8")) if not a.charts or r["chart"] in a.charts]
        for i, r in enumerate(vals[:a.val_n], 1):
            one("synthetic", "video", r["chart"], f"val{i}", [os.path.join(base, f) for f in r["frames"]], truth=r["answer"])
    fh.close()
    print(f"Done -> {a.results}")


# ------------------------------------------------------------------ comparison table
def compare(a):
    rows = list(csv.DictReader(open(a.results, encoding="utf-8"))) if os.path.exists(a.results) else []
    for r in rows:
        r["label"] = f"{r['model']} ({r['input']})"
    if os.path.exists(a.old):                                   # earlier Qwen3-VL runs, best frame only
        names = {"base": "qwen3vl_base", "lora": "qwen3vl_run1", "lora_v2": "qwen3vl_run2"}
        for r in csv.DictReader(open(a.old, encoding="utf-8")):
            if r.get("exp") == "A_best" and r.get("set") == "real":
                rows.append({**r, "label": f"{names.get(r['model'], r['model'])} (best)"})
            elif r.get("set") == "synthetic":
                pass                                            # different synthetic set; not comparable
    labels = []
    for r in rows:
        if r["label"] not in labels:
            labels.append(r["label"])
    order = lambda l: (0 if "qwen3vl" in l else 1, l)
    labels.sort(key=order)
    if a.charts:
        rows = [r for r in rows if r["chart"] in a.charts]
    groups = {}
    for r in rows:
        groups.setdefault((r["set"], r["chart"], r["measure"]), {}).setdefault(r["label"], []).append(float(r["value_acc"] or 0))
    head = "| Set | Chart | Measure | " + " | ".join(labels) + " |"
    lines = [head, "|" + "---|" * (3 + len(labels))]
    for (s, c, m), by in sorted(groups.items()):
        lines.append(f"| {s} | {c} | {m} | " + " | ".join(f"{statistics.mean(by[l]):.2f}" if l in by else "–" for l in labels) + " |")
    out = "Share of true values within 5 % (mean over clips)\n\n" + "\n".join(lines) + "\n"
    open(a.out, "w", encoding="utf-8").write(out)
    print(out)
    print(f"Saved {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--name")
    ap.add_argument("--load-4bit", action="store_true")
    ap.add_argument("--max-side", type=int, default=640)
    ap.add_argument("--real", default=os.path.join(ROOT, "real_clips", "real.jsonl"))
    ap.add_argument("--best", action="store_true", help="also test the single best frame per chart (from frames.csv)")
    ap.add_argument("--frames-csv", default=os.path.join(ROOT, "frames.csv"))
    ap.add_argument("--skip-real", action="store_true")
    ap.add_argument("--val", default=os.path.join(HERE, "data", "val.jsonl"))
    ap.add_argument("--val-n", type=int, default=20)
    ap.add_argument("--results", default=os.path.join(ROOT, "results_video.csv"))
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--charts", nargs="+", help="only these charts, e.g. --charts line")
    ap.add_argument("--videos", nargs="+", help="only these real recordings (names in real.jsonl), e.g. --videos line_clear")
    ap.add_argument("--old", default=os.path.join(ROOT, "results_ft.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "compare_video.md"))
    a = ap.parse_args()
    if a.compare:
        return compare(a)
    if not a.model or not a.name:
        sys.exit("give --model and --name (or --compare)")
    evaluate(a)


if __name__ == "__main__":
    main()
