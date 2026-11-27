#!/usr/bin/env python3
"""Run 4 evaluation: ask the model about the whole video AND about each frame alone, take the median value per
row (country + year, genre, ...), then remove the model's average offset measured on SYNTHETIC clips only.

    python3 finetune_video/eval_median.py --model lora_qwen35_line --name qwen35_lora_line --charts line \
        --val finetune_video/data_line/val.jsonl --val-n 10 --max-side 640

Writes three kinds of rows to results_video.csv (input column): "video" (the whole-video answer, as before),
"median" (median over the whole-video answer + one answer per frame) and "median_cal" (median minus the offset
learnt on the synthetic clips). The real truth tables are read only by the scorer, never to set the offset.
Then: python3 finetune_video/eval_video.py --compare --charts line --out compare_line.md
"""
import argparse
import csv
import importlib.util
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("eval_video", os.path.join(HERE, "eval_video.py"))
ev = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ev)
vlm, st = ev.vlm, ev.st
KEYS = {"line": ["Country", "Year"], "pie": ["Genre"], "bar": ["Clarity"], "heatmap": ["Year", "Month"], "linexy": ["Series", "X"], "pieany": ["Category"], "bar3d": ["Category", "Series"]}


def rows_of(text):
    try:
        return st.read_text(text) if hasattr(st, "read_text") else _read(text)
    except Exception:
        return []


def _read(text):
    import io, re
    m = re.search(r"```(?:csv)?\s*\n(.*?)```", text, re.S)
    text = m.group(1) if m else text
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(text.strip()))]


def keyof(chart, r):
    out = []
    for k in KEYS[chart]:
        v = r.get(k, "")
        n = st.num(v)
        out.append(str(int(round(n))) if n is not None and k == "Year" else (f"{n:g}" if n is not None and k == "X" else st.norm(v)))
    return tuple(out)


def median_table(chart, header, answers):
    """answers[0] = whole-video answer; the rest = one answer per frame. Returns CSV text."""
    cols = header.split(",")
    vals_cols = [c for c in cols if c not in KEYS[chart]]
    tables = [rows_of(a) for a in answers]
    seen, label = {}, {}
    for t in tables:
        for r in t:
            if any(k not in r for k in KEYS[chart]):
                continue
            k = keyof(chart, r)
            label.setdefault(k, r)
            seen.setdefault(k, []).append(r)
    first = [keyof(chart, r) for r in tables[0] if all(k in r for k in KEYS[chart])] if tables else []
    need = max(1, len(tables) // 2)
    keys = list(dict.fromkeys(first + [k for k, v in seen.items() if len(v) > need]))
    lines = [header]
    for k in keys:
        rs = seen.get(k, [])
        cells = []
        for c in cols:
            if c in KEYS[chart]:
                cells.append(label[k][c])
            else:
                xs = [st.num(r.get(c)) for r in rs if st.num(r.get(c)) is not None]
                cells.append(f"{statistics.median(xs):.2f}".rstrip("0").rstrip(".") if xs else "")
        lines.append(",".join(cells))
    return "\n".join(lines) + "\n", vals_cols


def offsets(chart, pairs, vals_cols):
    """pairs = [(pred_csv_text, truth_csv_text)] from synthetic clips -> median signed error per value column."""
    diffs = {c: [] for c in vals_cols}
    for pred, truth in pairs:
        t = {keyof(chart, r): r for r in rows_of(truth) if all(k in r for k in KEYS[chart])}
        for r in rows_of(pred):
            if all(k in r for k in KEYS[chart]) and keyof(chart, r) in t:
                for c in vals_cols:
                    p, g = st.num(r.get(c)), st.num(t[keyof(chart, r)].get(c))
                    if p is not None and g is not None:
                        diffs[c].append(p - g)
    return {c: round(statistics.median(d), 3) if d else 0.0 for c, d in diffs.items()}


def to100(text, col="Share_percent"):
    """pie r2: a pie always adds up to 100 %, so rescale the shares to total 100 (uses no true values)."""
    rs = rows_of(text)
    tot = sum(st.num(r.get(col)) or 0 for r in rs) if rs else 0
    if not rs or tot <= 0 or col not in rs[0]:
        return text
    cols = list(rs[0].keys())
    out = [",".join(cols)]
    for r in rs:
        out.append(",".join(f"{st.num(r[c]) * 100 / tot:.1f}" if c == col and st.num(r.get(c)) is not None else r.get(c, "") for c in cols))
    return "\n".join(out) + "\n"


def shift(text, chart, off):
    rs = rows_of(text)
    if not rs:
        return text
    cols = list(rs[0].keys())
    out = [",".join(cols)]
    for r in rs:
        cells = []
        for c in cols:
            n = st.num(r.get(c))
            cells.append(f"{n - off[c]:.2f}".rstrip("0").rstrip(".") if c in off and n is not None else r.get(c, ""))
        out.append(",".join(cells))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--charts", nargs="+", required=True)
    ap.add_argument("--videos", nargs="+")
    ap.add_argument("--load-4bit", action="store_true")
    ap.add_argument("--max-side", type=int, default=640)
    ap.add_argument("--real", default=os.path.join(ROOT, "real_clips", "real.jsonl"))
    ap.add_argument("--val", required=True, help="synthetic val.jsonl of this chart (used to learn the offset)")
    ap.add_argument("--val-n", type=int, default=10)
    ap.add_argument("--results", default=os.path.join(ROOT, "results_video.csv"))
    a = ap.parse_args()
    if any(c not in KEYS for c in a.charts):
        sys.exit("median/offset works for line, linexy, pie, bar, heatmap (not scatter)")

    from unsloth import FastVisionModel
    import datetime
    import torch
    model, tok = FastVisionModel.from_pretrained(a.model, load_in_4bit=a.load_4bit, max_seq_length=16384)
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
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=2400, do_sample=False, use_cache=True)
        return vlm.extract_csv(decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True), vlm.expected_header(prompt))

    outdir = os.path.join(ROOT, "predictions", f"median_{a.name}")
    os.makedirs(outdir, exist_ok=True)
    new = not os.path.exists(a.results)
    fh = open(a.results, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=ev.COLS)
    if new:
        w.writeheader()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")

    def run_clip(chart, paths):
        frames = [ev.load_image(p, a.max_side) for p in paths]
        t0 = datetime.datetime.now()
        answers = [ask(chart, frames)] + [ask(chart, frames[:i] + frames[i + 1:]) for i in range(len(frames))]   # v2: 7-frame subsets
        med, vals_cols = median_table(chart, vlm.expected_header(vlm.chart_prompt(chart)), answers)
        return answers, med, vals_cols, round((datetime.datetime.now() - t0).total_seconds(), 1)

    def write(set_, inp, chart, clip, n, secs, text, truth=None):
        p = os.path.join(outdir, f"{set_}_{inp}_{clip}.csv")
        open(p, "w", encoding="utf-8").write(text)
        if set_ == "real" and truth is None:
            truth = ev.control_truth(clip)
        for m in ev.score(chart, p, truth):
            w.writerow({"time": stamp, "set": set_, "model": a.name, "input": inp, "chart": chart, "clip": clip, "frames": n,
                        "seconds": secs, "prediction": os.path.relpath(p, ROOT), **m}); fh.flush()
            print(f"  {set_:9} {inp:10} {chart:8} {clip:14} {m['measure']:16} within5% {m['value_acc']}  mean err {m['value_mre']}")

    for chart in a.charts:
        base = os.path.dirname(os.path.abspath(a.val))
        vals = [r for r in (json.loads(l) for l in open(a.val, encoding="utf-8")) if r["chart"] == chart][:a.val_n]
        pairs, pairs_v = [], []
        print(f"{chart}: {len(vals)} synthetic clips (learn the offset) ...")
        for i, r in enumerate(vals, 1):
            answers, med, vals_cols, secs = run_clip(chart, [os.path.join(base, f) for f in r["frames"]])
            pairs.append((med, r["answer"])); pairs_v.append((answers[0], r["answer"]))
            write("synthetic", "video", chart, f"val{i}", len(r["frames"]), secs, answers[0], r["answer"])
            write("synthetic", "median", chart, f"val{i}", len(r["frames"]), secs, med, r["answer"])
            if chart in ("pie", "pieany"):
                write("synthetic", "median_norm", chart, f"val{i}", len(r["frames"]), secs, to100(med), r["answer"])
        off = offsets(chart, pairs, vals_cols); off_v = offsets(chart, pairs_v, vals_cols)
        print(f"{chart}: offset learnt on synthetic clips only = median {off}, video {off_v}")
        json.dump({"chart": chart, "offset": off, "offset_video": off_v, "synthetic_clips": len(pairs)}, open(os.path.join(outdir, f"offset_{chart}.json"), "w"), indent=1)
        rbase = os.path.dirname(os.path.abspath(a.real))
        for r in (json.loads(l) for l in open(a.real, encoding="utf-8")):
            if r["chart"] != chart or a.videos and r["video"] not in a.videos:
                continue
            answers, med, vals_cols, secs = run_clip(chart, [os.path.join(rbase, f) for f in r["frames"]])
            write("real", "video", chart, r["video"], len(r["frames"]), secs, answers[0])
            write("real", "median", chart, r["video"], len(r["frames"]), secs, med)
            write("real", "median_cal", chart, r["video"], len(r["frames"]), secs, shift(med, chart, off))
            write("real", "video_cal", chart, r["video"], len(r["frames"]), secs, shift(answers[0], chart, off_v))
            if chart in ("pie", "pieany"):          # pie r2: pre-registered main result = median rescaled to 100 %
                write("real", "median_norm", chart, r["video"], len(r["frames"]), secs, to100(med))
                write("real", "video_norm", chart, r["video"], len(r["frames"]), secs, to100(answers[0]))
    fh.close()
    print(f"Done -> {a.results}")


if __name__ == "__main__":
    main()
