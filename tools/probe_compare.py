#!/usr/bin/env python3
"""Geometric probes: measure reference and render the same way, then diff.

Global metrics tell you *that* something is off; these probes tell you *what*.
Each probe measures a geometric quantity in both images with identical code, so
a systematic difference is a geometry error rather than a photometry error:

  frame     stroke centre-line position and width on all four edges
  arcs      sub-pixel ridge position of both luminous curves vs y
  streak    the flare's horizontal streak profile and symmetry centre
  radial    mean luminance in rings around the flare centre
  edges     mean luminance profile across the whole canvas per row/column band

    python3 tools/probe_compare.py out/render_1024.png
    python3 tools/probe_compare.py out/render_1024.png --probe arcs
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def stroke_stats(vals, guess, half=11):
    """Coverage-weighted centre and equivalent width of a bright line."""
    lo, hi = int(guess) - half, int(guess) + half + 1
    seg = vals[lo:hi]
    base = min(seg[:3].mean(), seg[-3:].mean())
    w = np.clip(seg - base, 0, None)
    if w.sum() <= 0:
        return np.nan, np.nan, np.nan
    xs = np.arange(lo, hi)
    c = (xs * w).sum() / w.sum()
    return c, w.sum() / w.max(), w.max()


def frame_probe(ref, rec, fr):
    out = []
    for name, axis, fixed, rng in (
        ("left", "row", fr["left"], range(300, 760, 20)),
        ("right", "row", fr["right"], range(300, 760, 20)),
        ("top", "col", fr["top"], range(340, 700, 20)),
        ("bottom", "col", fr["bottom"], range(340, 700, 20)),
    ):
        acc = []
        for k in rng:
            for img, tag in ((ref, "ref"), (rec, "rec")):
                lum = img.mean(2)
                vals = lum[k] if axis == "row" else lum[:, k]
                acc.append((tag,) + stroke_stats(vals, fixed))
        r = np.array([a[1:] for a in acc if a[0] == "ref"])
        c = np.array([a[1:] for a in acc if a[0] == "rec"])
        out.append((name, np.nanmean(r, 0), np.nanmean(c, 0)))
    print("frame stroke:  edge      ref_centre  rec_centre   d      ref_width rec_width  ref_peak rec_peak")
    for name, r, c in out:
        print("               %-8s %9.3f %11.3f %+7.3f %9.2f %9.2f %9.1f %8.1f"
              % (name, r[0], c[0], c[0] - r[0], r[1], c[1], r[2], c[2]))


def ridge(vals, guess, half=24, frac=0.6):
    lo, hi = max(0, int(guess) - half), min(len(vals), int(guess) + half + 1)
    seg = vals[lo:hi]
    i = int(np.argmax(seg))
    pk = seg[i]
    base = np.percentile(seg, 10)
    if pk - base < 8:
        return np.nan, np.nan
    thr = base + frac * (pk - base)
    j = i
    while j > 0 and seg[j] > thr:
        j -= 1
    xl = j + (thr - seg[j]) / (seg[j + 1] - seg[j]) if seg[j + 1] != seg[j] else j
    k = i
    while k < len(seg) - 1 and seg[k] > thr:
        k += 1
    xr = (k - 1) + (seg[k - 1] - thr) / (seg[k - 1] - seg[k]) if seg[k - 1] != seg[k] else k
    return lo + 0.5 * (xl + xr), pk


def arc_probe(ref, rec):
    print("arcs:   y    ref_xL   rec_xL     d     ref_pkL rec_pkL |  ref_xR   rec_xR     d     ref_pkR rec_pkR")
    dl, dr = [], []
    gl, gr = 464.0, 544.0
    for y in range(120, 940, 20):
        rows = {}
        for img, tag in ((ref, "ref"), (rec, "rec")):
            ch = img[..., 0]
            rows[tag + "L"] = ridge(ch[y], gl)
            rows[tag + "R"] = ridge(ch[y], gr)
        gl = rows["refL"][0] if np.isfinite(rows["refL"][0]) else gl
        gr = rows["refR"][0] if np.isfinite(rows["refR"][0]) else gr
        d1 = rows["recL"][0] - rows["refL"][0]
        d2 = rows["recR"][0] - rows["refR"][0]
        if np.isfinite(d1):
            dl.append(d1)
        if np.isfinite(d2):
            dr.append(d2)
        if y % 60 == 0:
            print("      %4d %8.2f %8.2f %+7.2f %8.1f %7.1f | %8.2f %8.2f %+7.2f %8.1f %7.1f"
                  % (y, rows["refL"][0], rows["recL"][0], d1, rows["refL"][1], rows["recL"][1],
                     rows["refR"][0], rows["recR"][0], d2, rows["refR"][1], rows["recR"][1]))
    print("      mean dx  left %+.3f (rms %.3f)   right %+.3f (rms %.3f)"
          % (np.mean(dl), np.sqrt(np.mean(np.square(dl))), np.mean(dr), np.sqrt(np.mean(np.square(dr)))))


def streak_probe(ref, rec):
    print("streak excess (rows 506-520 minus rows 478-492/534-548):")
    print("        x      ref     rec     d")
    for img, tag in ((ref, "ref"), (rec, "rec")):
        lum = img.mean(2)
        s = lum[506:520].mean(0) - 0.5 * (lum[478:492].mean(0) + lum[534:548].mean(0))
        if tag == "ref":
            sr = s
        else:
            sc = s
    for x in range(200, 860, 40):
        print("      %4d %8.2f %8.2f %+7.2f" % (x, sr[x], sc[x], sc[x] - sr[x]))


def radial_probe(ref, rec, cx=513.0, cy=516.0):
    h, w, _ = ref.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - cx, yy - cy)
    print("radial rings about the flare:  r      ref     rec       d")
    for r0, r1 in ((0, 12), (12, 25), (25, 40), (40, 60), (60, 90), (90, 130),
                   (130, 180), (180, 240), (240, 320), (320, 420)):
        m = (r >= r0) & (r < r1)
        a, b = ref.mean(2)[m].mean(), rec.mean(2)[m].mean()
        print("                            %3d-%3d %8.2f %8.2f %+8.2f" % (r0, r1, a, b, b - a))


def band_probe(ref, rec):
    print("row bands (mean lum):    y-range      ref     rec      d   |  x-range      ref     rec      d")
    rl, cl = ref.mean(2), rec.mean(2)
    for i in range(0, 1024, 128):
        a, b = rl[i:i + 128].mean(), cl[i:i + 128].mean()
        c, d = rl[:, i:i + 128].mean(), cl[:, i:i + 128].mean()
        print("                      %4d-%4d %8.3f %8.3f %+7.3f | %4d-%4d %8.3f %8.3f %+7.3f"
              % (i, i + 128, a, b, b - a, i, i + 128, c, d, d - c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--probe", default="all",
                    choices=["all", "frame", "arcs", "streak", "radial", "bands"])
    a = ap.parse_args()
    import json
    params = json.load(open(os.path.join(ROOT, "src", "params.json")))
    ref, rec = load(a.reference), load(a.render)
    if a.probe in ("all", "frame"):
        frame_probe(ref, rec, params["frame"])
    if a.probe in ("all", "arcs"):
        arc_probe(ref, rec)
    if a.probe in ("all", "streak"):
        streak_probe(ref, rec)
    if a.probe in ("all", "radial"):
        radial_probe(ref, rec)
    if a.probe in ("all", "bands"):
        band_probe(ref, rec)


if __name__ == "__main__":
    main()
