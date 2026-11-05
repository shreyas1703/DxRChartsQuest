#!/usr/bin/env python3
"""Render a rough 'what the Quest recording will show' preview from a headless DxR dump.

    python3 render_preview.py DUMP_DIR OUT_DIR [--distance 1.0] [--px 1024] [--fov 90]

DUMP_DIR is written by the headless harness (tests/README.md). The camera sits --distance metres in front
of the chart centre (as ChartViewer places it) with a square --fov field of view rendered at --px pixels,
roughly like a Quest 2 system recording. Prints the text height in video pixels for every label class
so readability can be judged before building to the headset.
"""
import argparse
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

BG = "#14171c"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("out")
    ap.add_argument("--distance", type=float, default=1.0)
    ap.add_argument("--px", type=int, default=1024)
    ap.add_argument("--fov", type=float, default=90.0)
    ap.add_argument("--room", help="room mesh dump (tests/headless RoomDump) to draw the immersive grid room behind the chart")
    ap.add_argument("--yaw", type=float, default=None, help="turn the chart (degrees); default: the spec's \"view\" yaw")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    f = (a.px / 2) / math.tan(math.radians(a.fov / 2))
    report = {}
    for fn in sorted(os.listdir(a.dump)):
        if not fn.endswith(".json") or fn.endswith(".inferred.json"):
            continue
        d = json.load(open(os.path.join(a.dump, fn)))
        size = d["size_m"]
        c = [size[0] / 2, size[1] / 2, size[2] / 2]
        inf = os.path.join(a.dump, fn.replace(".json", ".inferred.json"))
        view = json.load(open(inf)).get("view", {}) if os.path.exists(inf) else {}
        yaw = math.radians(a.yaw if a.yaw is not None else float(view.get("yaw", 0)))
        drop = float(view.get("drop", 0))                     # chart lowered by this much; the viewer looks down at it
        h = 0.05 + drop
        phi = math.atan2(h, a.distance)

        def cam(p):
            x, y, z = p[0] - c[0], p[1] - c[1], p[2] - c[2]
            x, z = x * math.cos(yaw) + z * math.sin(yaw), -x * math.sin(yaw) + z * math.cos(yaw)
            y, z = y - h, z + a.distance
            return x, y * math.cos(phi) + z * math.sin(phi), z * math.cos(phi) - y * math.sin(phi)

        def proj(p):
            x, y, z = cam(p)
            return a.px / 2 + f * x / z, a.px / 2 - f * y / z, z

        dpi = 100
        fig = plt.figure(figsize=(a.px / dpi, a.px / dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, a.px); ax.set_ylim(a.px, 0); ax.axis("off")
        fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
        items = []   # (depth, draw-fn)
        if a.room:
            from matplotlib.collections import PolyCollection
            room = json.load(open(a.room))
            for part in ("Walls", "Grid lines"):
                V, T = room[part]["v"], room[part]["t"]
                polys, cols, depths = [], [], []
                for i in range(0, len(T), 3):
                    tri = [V[T[i]], V[T[i + 1]], V[T[i + 2]]]
                    cams = [(p[0], (p[1] - 1.6) * math.cos(phi) + p[2] * math.sin(phi), p[2] * math.cos(phi) - (p[1] - 1.6) * math.sin(phi)) for p in tri]
                    if min(cz for _, _, cz in cams) < 0.15:
                        continue
                    polys.append([(a.px / 2 + f * x / z, a.px / 2 - f * y / z) for x, y, z in cams])
                    cols.append(tuple(sum(p[k] for p in tri) / 3 for k in (3, 4, 5)))
                    depths.append(sum(z for _, _, z in cams) / 3)
                order = sorted(range(len(polys)), key=lambda i: -depths[i])
                ax.add_collection(PolyCollection([polys[i] for i in order], facecolors=[cols[i] for i in order],
                                                 edgecolors=[cols[i] for i in order] if part == "Walls" else "none", linewidths=0.3, zorder=0 if part == "Walls" else 0.5))

        for ln in d["lines"]:
            p0, p1 = ln["a"], ln["b"]
            u0, v0, z0 = proj(p0); u1, v1, z1 = proj(p1)
            data_line = ln["name"].startswith("DataLine")
            items.append(((z0 + z1) / 2 + (0.0 if data_line else 0.5), lambda u0=u0, v0=v0, u1=u1, v1=v1, col=ln["color"], name=ln["name"], dl=data_line:
                          ax.plot([u0, u1], [v0, v1], color=col, lw=0.6 if name == "Grid" else 4.0 if dl else 1.6, zorder=2.5 if dl else 1,
                                  solid_capstyle="round")))

        for sw in d.get("swatches", []):
            mn, mx = sw["min"], sw["max"]
            if sw.get("sphere"):
                ctr = [(mn[i] + mx[i]) / 2 for i in range(3)]
                u, v, z = proj(ctr)
                rad = (mx[0] - mn[0]) / 2 * f / z
                items.append((-2, lambda u=u, v=v, rad=rad, col=sw["color"]: ax.add_patch(Circle((u, v), rad, fc=col, ec="black", lw=0.4, zorder=4))))
            else:
                quad = [proj((mn[0], mn[1], mn[2]))[:2], proj((mx[0], mn[1], mn[2]))[:2], proj((mx[0], mx[1], mn[2]))[:2], proj((mn[0], mx[1], mn[2]))[:2]]
                items.append((-2, lambda quad=quad, col=sw["color"], g=sw["name"] == "GradientCell": ax.add_patch(
                    Polygon(quad, fc=col, ec=col if g else "black", lw=0.3, zorder=4))))

        for m in d["marks"]:
            if m["kind"] == "arc":
                cx, cy, cz = m["center"]
                r = m["radiusMm"] / 1000
                n = 60
                pts = []
                for i in range(n + 1):
                    ang = math.radians(m["startDeg"] + (m["endDeg"] - m["startDeg"]) * i / n)
                    pts.append((cx + r * math.sin(ang), cy + r * math.cos(ang), cz))
                pts.append((cx, cy, cz))
                poly = [proj(p)[:2] for p in pts]
                z = proj((cx, cy, cz))[2]
                items.append((z, lambda poly=poly, col=m["color"]: ax.add_patch(Polygon(poly, closed=True, fc=col, ec=BG, lw=1.5, zorder=2))))
            elif m["kind"] in ("sphere", "point", "line"):
                mn, mx = m["min"], m["max"]
                ctr = [(mn[i] + mx[i]) / 2 for i in range(3)]
                u, v, z = proj(ctr)
                rad = (mx[0] - mn[0]) / 2 * f / z
                items.append((z, lambda u=u, v=v, rad=rad, col=m["color"]: ax.add_patch(Circle((u, v), rad, fc=col, ec="black", lw=0.4, zorder=3))))
            else:
                mn, mx = m["min"], m["max"]
                front = [proj((mn[0], mn[1], mn[2]))[:2], proj((mx[0], mn[1], mn[2]))[:2], proj((mx[0], mx[1], mn[2]))[:2], proj((mn[0], mx[1], mn[2]))[:2]]
                top = [proj((mn[0], mx[1], mn[2]))[:2], proj((mx[0], mx[1], mn[2]))[:2], proj((mx[0], mx[1], mx[2]))[:2], proj((mn[0], mx[1], mx[2]))[:2]]
                z = proj(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, mn[2]))[2]
                items.append((z, lambda front=front, top=top, col=m["color"]: (ax.add_patch(Polygon(top, fc=col, ec="black", lw=0.3, alpha=0.75, zorder=2)),
                                                                               ax.add_patch(Polygon(front, fc=col, ec="black", lw=0.3, zorder=2)))))

        px_heights = {}
        for t in d["texts"]:
            if not t["text"] or t["text"] == "-":
                continue
            u, v, z = proj(t["pos"])
            hpx = t["h"] * f / z
            cls = ("tick" if t["name"].startswith("TickLabel") else "title" if t["name"] in ("Title", "AxisTitle", "LegendTitle")
                   else "legend" if t["name"].startswith("Legend") else "data label")
            px_heights.setdefault(cls, []).append(hpx)
            ha = {"Left": "left", "Right": "right", "Center": "center"}[t["align"]]
            fs = hpx * 0.78 * 72 / dpi
            items.append((-1, lambda u=u, v=v, txt=t["text"], fs=fs, ha=ha, rot=-t["roll"], col=t["color"]:
                          ax.text(u, v, txt, fontsize=fs, ha=ha, va="center", rotation=rot, rotation_mode="anchor", color=col,
                                  fontweight="bold", zorder=5, bbox=dict(boxstyle="square,pad=0.25", fc="#050508", ec="none", alpha=0.78))))

        for _, fn_draw in sorted(items, key=lambda it: (1, -it[0]) if it[0] < 0 else (0, -it[0])):
            fn_draw()
        out = os.path.join(a.out, fn.replace(".json", ".png"))
        fig.savefig(out, dpi=dpi, facecolor=BG)
        plt.close(fig)
        report[fn] = {k: round(sum(v) / len(v), 1) for k, v in px_heights.items()}
        print(f"{out}: text height (video px) " + ", ".join(f"{k} {v}" for k, v in report[fn].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
