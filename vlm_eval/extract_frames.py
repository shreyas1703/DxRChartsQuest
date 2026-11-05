#!/usr/bin/env python3
"""Pull still frames out of a Quest recording for the VLM.

    python3 extract_frames.py VIDEO.mp4                      # 8 frames spread over the video
    python3 extract_frames.py VIDEO.mp4 --count 4 --skip 2   # 4 frames, ignore first/last 2 s
    python3 extract_frames.py VIDEO.mp4 --every 1.5          # one frame every 1.5 s
    python3 extract_frames.py VIDEO.mp4 --at 3.5 --at 9      # exact times (s)

Recommended protocol: record ONE short video per chart (start recording → look at the chart → stop),
name it after the chart id (pie / bar / scatter), then extract frames. Frames are written to
frames/<video name>/ as PNG plus frames.json (times, size). Needs ffmpeg/ffprobe on PATH.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys


def duration(video):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", video])
    return float(out.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--count", type=int, default=8)
    ap.add_argument("--every", type=float)
    ap.add_argument("--at", type=float, action="append")
    ap.add_argument("--skip", type=float, default=1.0, help="seconds ignored at start and end (head movement while pressing record)")
    ap.add_argument("--out", default="frames")
    a = ap.parse_args()
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit(f"{t} not found — macOS: brew install ffmpeg")
    dur = duration(a.video)
    lo, hi = min(a.skip, dur / 3), max(dur - a.skip, dur * 2 / 3)
    if a.at:
        times = a.at
    elif a.every:
        times, t = [], lo
        while t <= hi:
            times.append(round(t, 2)); t += a.every
    else:
        n = max(1, a.count)
        times = [round(lo + (hi - lo) * (i + 0.5) / n, 2) for i in range(n)]
    stem = os.path.splitext(os.path.basename(a.video))[0]
    out = os.path.join(a.out, stem)
    os.makedirs(out, exist_ok=True)
    files = []
    for i, t in enumerate(times):
        f = os.path.join(out, f"{stem}_f{i:02d}_t{t:07.2f}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", a.video, "-frames:v", "1", f], check=True)
        files.append({"file": os.path.basename(f), "t": t})
    json.dump({"video": os.path.abspath(a.video), "duration": dur, "frames": files}, open(os.path.join(out, "frames.json"), "w"), indent=2)
    print(f"{len(files)} frames → {out}")


if __name__ == "__main__":
    main()
