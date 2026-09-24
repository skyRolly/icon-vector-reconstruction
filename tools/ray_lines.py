#!/usr/bin/env python3
"""Every named ray as a 2D profile, reference beside render, on its measured line.

    python3 tools/ray_lines.py out/render_1024.png [--ray lower-right] [--hw 12]

`ray_report.py` reads rays on axes through the core.  Several rays in this
reference do not pass through the core -- the upper-left pair misses it by 17
and 26 px, the lower-left ray by 7 -- and a statistic that samples a wedge about
the core reads those as the field beside them.  This tool follows each ray's
MEASURED line instead and reports, per radial band along it, what the eye
actually uses to judge a ray:

  A_R, A_G, A_B  the amplitude above the local ramp in each channel.  The
                 transverse G profile is fitted by a Gaussian plus a straight
                 line (the curves' glow is a ramp at this scale); R and B are
                 the least-squares amplitudes of the SAME Gaussian, so hue is
                 compared on identical footing.  R is white's only carrier, so
                 A_R is how white the ray is.
  s0             where the ridge sits across the line (+ = counter-clockwise),
                 which is how a mis-placed line shows up.
  sigma          the width.  A ray can carry the right light in the wrong
                 width, and "too blurry" is a width statement.

The lines are the geometry of record: a line through the core for a ray that
passes through it, and the fitted foot and direction for one that does not.
They are measurements of the reference, and the render is read on the same
line so that a render ray placed elsewhere reads as missing, not as present.

The Gaussian fit is bounded (|s0| <= 4, 0.8 <= sigma <= 9) and LOCAL, started on
the line: the amplitude and ramp are solved exactly at each trial (s0, sigma)
and those two are refined by a multi-start pattern search (numpy only; the repository's
documented dependencies are numpy, Pillow and resvg-py).  A band whose fit sits on a bound is not a measurement;
it is printed and should be read as "no clean ray here", which near the curve
ridges is the usual answer.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CORE = (531.0, 513.5)
#: name -> (foot, direction deg (ccw from east, y up), r0, r1).  Canvas
#: coordinates: pixel i spans [i, i+1].  Feet off the core are the TLS lines
#: fitted through the reference's per-band ridge centres (docs/DECISIONS.md D61).
LINES = {
    "upper-left inner": (CORE, 112.0, 40.0, 120.0),
    "upper-left A": ((519.9, 526.9), 140.4, 100.0, 210.0),
    "upper-left B": ((518.0, 535.6), 150.0, 80.0, 170.0),
    "lower-left 229": (CORE, 229.0, 20.0, 76.0),
    "lower-left": ((524.2, 511.7), 255.2, 36.0, 136.0),
    # 2-4 px from the vertical line: at a 12 px half-window the one-Gaussian
    # fit flips between this ray, the line and the dark gap between them from
    # band to band, so this line is read at 8 px (see HALF_WIDTH) and a
    # sigma above ~4 there means "ray and line together".
    "lower-left 268": (CORE, 268.0, 24.0, 108.0),
    "upper-right": ((534.8, 517.0), 47.6, 54.0, 166.0),
    "lower-right": ((531.53, 511.78), 328.1, 32.0, 224.0),
}


#: per-line transverse half-width where the default does not fit the line
HALF_WIDTH = {"lower-left 268": 8.0}


def _bilinear(a, x, y):
    h, w = a.shape[:2]
    x0 = np.clip(np.floor(x).astype(int), 0, w - 1)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    x1, y1 = np.clip(x0 + 1, 0, w - 1), np.clip(y0 + 1, 0, h - 1)
    fx, fy = x - x0, y - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def _sse(s, v, s0, sg):
    """Residual and linear coefficients of v ~ a*G(s0, sg) + c0 + c1*s."""
    X = np.stack([np.exp(-0.5 * ((s - s0) / sg) ** 2), np.ones_like(s), s], 1)
    coef = np.linalg.lstsq(X, v, rcond=None)[0]
    return float(((X @ coef - v) ** 2).sum()), coef


def fit_gauss_line(s, v, s0_max=4.0, sg_lo=0.8, sg_hi=9.0):
    """Bounded Gaussian-plus-line fit, LOCAL, started on the line.

    Deliberately local: the question is what sits ON the line, and a global
    optimum over the window will happily latch onto a neighbouring structure
    or a broad dip at the window's edge.  The amplitude and the ramp are
    solved exactly at every trial (s0, sigma); those two are refined by a
    pattern search whose step halves until it is below 0.005 px, from three
    starting widths, keeping the best solution that is not sitting on a
    bound (a bound-sitting fit is reported only when there is no other).
    """
    lo, hi = np.array([-s0_max, sg_lo]), np.array([s0_max, sg_hi])
    found = []
    for sg0 in (1.5, 3.0, 5.0):
        x, step = np.array([0.0, sg0]), np.array([0.5, 0.5])
        best, coef = _sse(s, v, *x)
        while step.max() > 0.005:
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y = np.clip(x + step * d, lo, hi)
                e, c = _sse(s, v, *y)
                if e < best - 1e-12:
                    x, best, coef = y, e, c
                    break
            else:
                step = step / 2.0
        found.append((best, float(coef[0]), float(x[0]), float(x[1])))
    inner = [f for f in found if abs(f[2]) < s0_max - 0.05 and sg_lo + 0.05 < f[3] < sg_hi - 0.05]
    return min(inner or found)[1:]


def profile(img, foot, direction, r0, r1, step=8.0, hw=12.0):
    """Rows of (r, A_R, A_G, A_B, s0, sigma) along one line."""
    t = math.radians(direction)
    ux, uy, nx, ny = math.cos(t), -math.sin(t), -math.sin(t), -math.cos(t)
    s = np.arange(-hw, hw + 0.01, 0.5)
    rows = []
    for r in np.arange(r0, r1, step):
        rr = np.arange(r, r + step, 0.5)
        xs = foot[0] + rr[:, None] * ux + s[None, :] * nx - 0.5
        ys = foot[1] + rr[:, None] * uy + s[None, :] * ny - 0.5
        v = [_bilinear(img[..., k], xs, ys).mean(0) for k in range(3)]
        _a, s0, sg = fit_gauss_line(s, v[1])
        shape = np.exp(-0.5 * ((s - s0) / sg) ** 2)
        X = np.stack([shape, np.ones_like(s), s], 1)
        amps = [float(np.linalg.lstsq(X, v[k], rcond=None)[0][0]) for k in range(3)]
        rows.append((r + step / 2, amps[0], amps[1], amps[2], float(s0), float(sg)))
    return np.array(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("render")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--ray", default=None, help="one name from LINES; default all")
    ap.add_argument("--hw", type=float, default=None,
                    help="transverse half-width (px); default 12, or the line's own in HALF_WIDTH")
    a = ap.parse_args()
    load = lambda p: np.asarray(Image.open(p).convert("RGB")).astype(np.float64)  # noqa: E731
    ref, rec = load(a.reference), load(a.render)
    for name, (foot, d, r0, r1) in LINES.items():
        if a.ray and a.ray != name:
            continue
        hw = a.hw if a.hw is not None else HALF_WIDTH.get(name, 12.0)
        P, Q = profile(ref, foot, d, r0, r1, hw=hw), profile(rec, foot, d, r0, r1, hw=hw)
        print("%s  line through (%.1f, %.1f) at %.1f deg, half-width %g px" % (name, foot[0], foot[1], d, hw))
        print("   r        " + " ".join("%6.0f" % v for v in P[:, 0]))
        for lab, k in (("G", 2), ("B", 3), ("R", 1), ("sigma", 5), ("s0", 4)):
            print("   %-5s ref " % lab + " ".join("%6.1f" % v for v in P[:, k]))
            print("   %-5s rec " % lab + " ".join("%6.1f" % v for v in Q[:, k]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
