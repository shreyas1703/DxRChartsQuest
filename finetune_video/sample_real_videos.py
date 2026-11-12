#!/usr/bin/env python3
"""Turn your real Quest recordings into 8-frame test clips (TEST ONLY - never used for training).

    python3 finetune_video/sample_real_videos.py ~/Desktop/quest_videos
    python3 finetune_video/sample_real_videos.py ~/Desktop/quest_videos --frames 8 --skip 1.0 --width 640
    python3 finetune_video/sample_real_videos.py ~/Desktop/quest_videos_new --charts line   # only line videos (added to the list)

Name each video after its chart: pie.mp4, bar.mp4, line.mp4, heatmap.mp4, scatter.mp4 - extra takes as
pie_2.mp4, bar_take3.mov, ... . Frames are spread evenly over the whole video (first/last --skip seconds dropped),
so the model sees the full walk-around, including the angled views. Output: real_clips/<video>/f0.jpg ... and
real_clips/real.jsonl with {"frames": [...], "chart": "pie", "video": "pie_2"}. Needs ffmpeg + ffprobe.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHARTS = ["heatmap", "scatter", "linexy", "line", "pie", "bar"]          # longest first, so "bar" never matches inside another name


def duration(video):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", video]).strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--skip", type=float, default=1.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--out", default=os.path.join(ROOT, "real_clips"))
    ap.add_argument("--charts", nargs="+", choices=CHARTS, help="only videos of these charts, e.g. --charts line")
    a = ap.parse_args()
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"{t} not found - macOS: brew install ffmpeg")
    vids = sorted(f for ext in ("mp4", "mov", "MP4", "MOV", "m4v") for f in glob.glob(os.path.join(os.path.expanduser(a.videos), "*." + ext)))
    if not vids:
        sys.exit(f"No videos in {a.videos}")
    os.makedirs(a.out, exist_ok=True)
    recs = []
    for v in vids:
        stem = os.path.splitext(os.path.basename(v))[0]
        chart = next((c for c in CHARTS if stem.lower().startswith(c)), None)
        if not chart:
            print(f"skipped {stem}: name must start with pie / bar / line / linexy / heatmap / scatter")
            continue
        if a.charts and chart not in a.charts:
            continue
        dur = duration(v)
        lo, hi = min(a.skip, dur / 4), max(dur - a.skip, dur * 3 / 4)
        d = os.path.join(a.out, stem)
        os.makedirs(d, exist_ok=True)
        frames = []
        for i in range(a.frames):
            t = lo + (hi - lo) * i / max(1, a.frames - 1)
            f = os.path.join(d, f"f{i}.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", v, "-frames:v", "1", "-vf", f"scale={a.width}:-2", "-q:v", "2", f], check=True)
            frames.append(os.path.relpath(f, a.out))
        recs.append({"frames": frames, "chart": chart, "video": stem})
        print(f"{stem}: {a.frames} frames ({chart})")
    path = os.path.join(a.out, "real.jsonl")               # keep clips of other videos made earlier
    old = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
    done = {r["video"] for r in recs}
    recs = [r for r in old if r["video"] not in done] + recs
    with open(path, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    print(f"{len(recs)} test clips in total -> {path}")
    for r in recs:
        print(f"   {r['chart']:8} {r['video']}")


if __name__ == "__main__":
    main()
