#!/usr/bin/env python3
"""Score the westward fan's EXTENT, which a radial or angular mean cannot.

    python3 tools/fan_report.py <label> <render.png> [<label> <render.png> ...]

`flare_ray_d` is the largest layer of the flare and it reaches out along the
left curve, so two quite different errors look alike in any regional average:
the fan being too BRIGHT, and the fan being too LONG.  They are separated here
by asking how the excess is distributed along the curve.

  S    = mean(render - reference) over r 110..170, theta 148..216.  A plain
         regional mean; it moves for either error.

  STEP = mean(D, |t| < 16 deg) - mean(D, 16 <= |t| < 26 deg), pooled over signed
         distances d = -100..-48 px on the left curve's concave side, where t is
         the ALONG-CURVE angle measured from the flare's own position on that
         curve.  Every arc layer is nearly flat in |t| at fixed distance
         (arc_glow3 reads 11.67/11.54/11.03 code values across the three |t|
         bands, arc_haze 4.79/4.31/3.68), while flare_ray_d falls from 5.0-8.6
         to 0.0-0.31 across the same bands.  STEP therefore cancels the curve
         glow and keeps only light anchored to the flare.

Both are quoted against nulls built from this image rather than from a noise
model: the block-mean scatter of (render - reference) in the quiet background
falls only from 1.07 to 0.63 code values between 1 px and 32 px blocks, so the
difference field is dominated by long-range model error and a 1/sqrt(N) error
bar is simply wrong here.  The STEP null is the same statistic taken at other
along-curve centres, on both curves, where no flare sits.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from ray_report import CORE, ridge_distance  # noqa: E402
from ray_report import load as _load_rgb  # noqa: E402
from regions import ARCS  # noqa: E402

SECTOR_R = (110.0, 170.0)
SECTOR_TH = (148.0, 216.0)
CLEAR = 26.0
STEP_D = (-100.0, -48.0)
STEP_T = (16.0, 26.0)
#: Along-curve centres used as the STEP null: no flare sits at any of them.
NULL_T = tuple(float(v) for v in range(-70, 71, 10) if abs(v) >= 34)


def load(p):
    return _load_rgb(p).mean(2)


def _curve(shape, side):
    """Signed perpendicular distance and along-curve angle, both in one pass."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    cx, cy, rx, ry = ARCS[side]
    u, v = (xx - cx) / rx, (yy - cy) / ry
    rr = np.sqrt(u * u + v * v)
    d = (rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6)
    t = np.degrees(np.arctan2(v, u))
    return d, t


def sector(res, shape):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    dx, dy = xx - CORE[0], yy - CORE[1]
    r = np.hypot(dx, dy)
    th = np.degrees(np.arctan2(-dy, dx)) % 360.0
    m = ((r >= SECTOR_R[0]) & (r < SECTOR_R[1])
         & (th >= SECTOR_TH[0]) & (th < SECTOR_TH[1])
         & (ridge_distance(shape) > CLEAR))
    return float(res[m].mean()), int(m.sum())


def step(res, shape, side="left", t0=None):
    d, t = _curve(shape, side)
    if t0 is None:
        # the flare's own along-curve position
        cx, cy, rx, ry = ARCS[side]
        t0 = np.degrees(np.arctan2((CORE[1] - cy) / ry, (CORE[0] - cx) / rx))
    dt = np.abs((t - t0 + 180.0) % 360.0 - 180.0)
    band = (d >= STEP_D[0]) & (d < STEP_D[1])
    inn = band & (dt < STEP_T[0])
    out = band & (dt >= STEP_T[0]) & (dt < STEP_T[1])
    if inn.sum() < 200 or out.sum() < 200:
        return float("nan"), 0, 0
    return float(res[inn].mean() - res[out].mean()), int(inn.sum()), int(out.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference)
    shape = ref.shape

    print("westward fan extent.  S is a regional mean; STEP keeps only light")
    print("anchored to the flare's own position along the left curve.")
    print("A fan of the right length reads about zero on BOTH.\n")
    print("  %-14s %9s %7s %9s %9s" % ("render", "S", "px", "STEP", "null sd"))
    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        res = load(path) - ref
        s, n = sector(res, shape)
        st, _, _ = step(res, shape)
        nulls = []
        for side in ("left", "right"):
            for t0 in NULL_T:
                cx, cy, rx, ry = ARCS[side]
                base = np.degrees(np.arctan2((CORE[1] - cy) / ry,
                                             (CORE[0] - cx) / rx))
                v, _, _ = step(res, shape, side, base + t0)
                if np.isfinite(v):
                    nulls.append(v)
        sd = float(np.std(nulls)) if nulls else float("nan")
        print("  %-14s %9.3f %7d %9.3f %9.3f  (%d null placements)"
              % (label, s, n, st, sd, len(nulls)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
