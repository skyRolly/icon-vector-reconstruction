#!/usr/bin/env python3
"""Score the flare's three horizontal lines the way they were measured.

    python3 tools/line_report.py <label> <render.png> [<label> <render.png> ...]

The reference's central light carries three distinct horizontal features, at
dy = -0.283 +- 0.037, +6.740 +- 0.055 and +19.329 +- 0.065 from the core row
(y increasing downward).  A radial profile averages all three together, and a
whole-image metric cannot see any of them: the faintest is 3-5 code values over
a few hundred columns.

Two things make the measurement trustworthy.  The curve ridges cross the streak
row 65.5 px west and 14.5 px east of the core, so every window is masked to
more than 30 px from either ridge -- an unmasked window at dx +15..+40 sits
entirely inside the right curve's core and reads the curve, not the streak.
And the amplitude is taken as a model-free row difference,
L(y0+dy) - 0.5*[L(y0+dy-k) + L(y0+dy+k)], which isolates a thin line without
assuming anything about the bloom underneath it.

Row differences with the curve ridges masked: L(y0+dy) - 0.5*[L(y0+dy-k) +
L(y0+dy+k)] isolates a thin line at dy without any model of the bloom under it.
"""
import json, os, sys
import numpy as np
ROOT = "/home/user/icon-vector-reconstruction"; SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import diagnose as D
from regions import ARCS

CORE_Y, CORE_X = 513.0, 530.5
LINES = (("A", -0.283, 4), ("B", 6.740, 4), ("C", 19.329, 7))
BINS = ((-300, -240), (-240, -190), (-190, -150), (-150, -120), (-120, -95),
        (-95, -70), (-70, -47), (-36, -17), (17, 36), (47, 70), (70, 95),
        (95, 120), (120, 150), (150, 190), (190, 240), (240, 300))

def ridge_mask(shape):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dmin = np.full((h, w), 1e9)
    for side, (cx, cy, rx, ry) in ARCS.items():
        u, v = (xx - cx) / rx, (yy - cy) / ry
        rr = np.sqrt(u * u + v * v)
        dd = np.abs(rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6)
        dmin = np.minimum(dmin, dd)
    return dmin > 30.0

def line_amp(img, keep, dy, k):
    L = img.mean(2)
    y = int(round(CORE_Y + dy))
    out = []
    for a, b in BINS:
        x0, x1 = int(round(CORE_X + a)), int(round(CORE_X + b))
        cols = keep[y, x0:x1] & keep[y - k, x0:x1] & keep[y + k, x0:x1]
        if cols.sum() < 6:
            out.append(np.nan); continue
        v = L[y, x0:x1][cols] - 0.5 * (L[y - k, x0:x1][cols] + L[y + k, x0:x1][cols])
        out.append(float(v.mean()))
    return np.array(out)

ref = D.load(os.path.join(ROOT, "reference.png"))
keep = ridge_mask(ref.shape)
runs = [("reference", ref)] + [(n, D.load(p)) for n, p in
        [(a, b) for a, b in zip(sys.argv[1::2], sys.argv[2::2])]]
for nm, dy, k in LINES:
    print("\nline %s  (dy %+.3f, model-free row difference, ridges masked)" % (nm, dy))
    print("  %-11s" % "dx bin" + "".join("%7s" % ("%+d" % a) for a, b in BINS))
    base = None
    for label, img in runs:
        v = line_amp(img, keep, dy, k)
        if base is None:
            base = v
            print("  %-11s" % label + "".join("    .  " if np.isnan(x) else "%7.2f" % x for x in v))
        else:
            ok = ~np.isnan(v) & ~np.isnan(base)
            rms = float(np.sqrt(np.mean((v[ok] - base[ok]) ** 2)))
            print("  %-11s" % label + "".join("    .  " if np.isnan(x) else "%7.2f" % x for x in v)
                  + "   rms err %.2f" % rms)
