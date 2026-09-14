#!/usr/bin/env python3
"""Score the angular structure west of the flare, where a mean cannot.

    python3 tools/wedge_report.py <label> <render.png> [<label> <render.png> ...]

The light west of the flare is not one thing.  The reference has, at r 34..46:
a bright due-west horizontal arm, a broad upper-left flank over theta 104..136
with a hard outer edge, a broad lower-left flank peaking at theta 226..232, and
two genuine MINIMA between them at theta ~148 and ~199..215.  A reconstruction
can carry the right total light there and fill both minima in, which is what
"a false triangular wedge" means in measurable terms.

So this reports the angular MODULATION, bin by bin, rather than a regional
average.  The headline numbers are the residual RMS over the cleared bins and
the peak-to-peak swing; a render that flattens the minima scores badly on both
while barely moving a mean absolute error.

It also reports the |dx| 22..52 strip split by |dy|, because the same defect has
a second signature there: light that belongs in a thin horizontal arm spread
into an area reads as too bright at 12 <= |dy| < 30 and too dark at |dy| < 8.

Whole-image MAE moves the WRONG WAY when this is fixed -- measured, a trial that
took the bin RMS from 5.95 to 3.85 cv made MAE worse -- so MAE must not be used
to judge this region.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from ray_report import CORE, _bilinear, load, ridge_distance  # noqa: E402

#: Angular bins, 6 degrees wide, over the two west sectors that clear the ridge.
SECTORS = ((106.0, 166.0), (196.0, 250.0))
BIN = 6.0
RADII = (34.0, 40.0, 46.0)
RIDGE_CLEAR = 26.0
#: The horizontal-arm strip: |dx| band, and the |dy| splits.
STRIP_DX = (22.0, 52.0)
STRIP_DY = ((0.0, 8.0), (8.0, 12.0), (12.0, 30.0))


def bins():
    out = []
    for lo, hi in SECTORS:
        t = lo
        while t + BIN <= hi + 1e-9:
            out.append((t, t + BIN))
            t += BIN
    return out


def angular(lum, dmin):
    """Mean luminance in each (bin, radius) cell, NaN where the ridge intrudes."""
    vals = []
    for a, b in bins():
        ths = np.arange(a, b, 0.5)
        cell = []
        for r in RADII:
            rad = np.radians(ths)
            xs, ys = CORE[0] + r * np.cos(rad), CORE[1] - r * np.sin(rad)
            ok = _bilinear(dmin, xs, ys) > RIDGE_CLEAR
            if ok.sum() < ths.size * 0.6:
                cell.append(np.nan); continue
            cell.append(float(np.nanmean(np.where(ok, _bilinear(lum, xs, ys), np.nan))))
        vals.append(cell)
    return np.array(vals)


def strip(lum):
    h, w = lum.shape
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = xx - CORE[0], yy - CORE[1]
    west = (dx < 0) & (np.abs(dx) >= STRIP_DX[0]) & (np.abs(dx) < STRIP_DX[1])
    return [float(lum[west & (np.abs(dy) >= a) & (np.abs(dy) < b)].mean())
            for a, b in STRIP_DY]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference).mean(2)
    dmin = ridge_distance(ref.shape)
    ra = angular(ref, dmin)
    rs = strip(ref)
    bs = bins()

    print("angular mean luminance west of the core, %d-degree bins, r = %s, ridges masked at %.0f px"
          % (int(BIN), "/".join("%g" % r for r in RADII), RIDGE_CLEAR))
    hdr = "  %-11s" % "theta" + "".join("%7.0f" % ((x + y) / 2) for x, y in bs)
    print(hdr)
    print("  %-11s" % "reference" + "".join(
        "     . " if np.isnan(v) else "%7.1f" % v for v in np.nanmean(ra, axis=1)))

    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        img = load(path).mean(2)
        ca = angular(img, dmin)
        d = np.nanmean(ca - ra, axis=1)
        good = np.isfinite(d)
        rms = float(np.sqrt(np.nanmean(d[good] ** 2)))
        ptp = float(np.nanmax(d[good]) - np.nanmin(d[good]))
        print("  %-11s" % (label[:9] + " err") + "".join(
            "     . " if np.isnan(v) else "%+7.1f" % v for v in d))
        print("  %-11s residual RMS %.2f cv over %d cleared bins, peak-to-peak %.2f cv"
              % (label, rms, int(good.sum()), ptp))

    print("\nwest horizontal arm, |dx| %g..%g, split by |dy| (light spread off the core row"
          % STRIP_DX)
    print("reads as too bright far from it and too dark on it)")
    print("  %-13s" % "band" + "".join("%12s" % ("|dy| %g-%g" % b) for b in STRIP_DY))
    print("  %-13s" % "reference" + "".join("%12.2f" % v for v in rs))
    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        cs = strip(load(path).mean(2))
        print("  %-13s" % (label[:11]) + "".join("%12.2f" % (c - r) for c, r in zip(cs, rs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
