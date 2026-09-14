#!/usr/bin/env python3
"""Score the flare core's radial sharpness against the reference.

    python3 tools/core_report.py <label> <render.png> [<label> <render.png> ...]

The review's question was whether the flare centre is too blurry. A blur is a
statement about a gradient, so this measures gradients rather than appearance.

Two things make the measurement awkward and both are handled explicitly:

  * the 30 px ridge clearance that `tools/ray_report.py` needs erases the core
    completely -- the right curve ridge is only 14.5 px east of it, so no circle
    of radius under about 17 px has a single clear sample. So the core is read
    along the two paths that do survive: a vertical cut down the core column,
    which stays 14.6 px clear of every ridge over dy = -25..+25, and an
    azimuthal mean over the west sector alone (theta 140..220), where the
    nearest ridge is the left one 65.5 px away.

  * "sharper" is not one number. A core can be too flat near its peak and too
    steep further out at the same time, which is exactly what the reconstruction
    does, so the falloff is reported in three radial bands and the answer is
    read off the pattern across them, not from a single figure.

Both readings are of total luminance, not of an isolated layer: the question is
about the rendered image, and the isolation algebra is not needed for it.
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

#: Radial bands for the west-sector falloff, and the matching |dy| bands for the
#: vertical cut.  The inner band is where a blurred core shows up as too flat.
WEST_BANDS = ((1, 8), (8, 16), (16, 28))
VERT_BANDS = ((0, 6), (6, 14), (14, 24))
WEST_SECTOR = (140.0, 220.0)
CORE_CLEAR = 8.0


def west_profile(img, dmin, radii):
    th = np.radians(np.arange(WEST_SECTOR[0], WEST_SECTOR[1] + 0.01, 0.5))
    out = []
    for r in radii:
        xs = CORE[0] + r * np.cos(th)
        ys = CORE[1] - r * np.sin(th)
        v = _bilinear(img, xs, ys)
        ok = _bilinear(dmin, xs, ys) > CORE_CLEAR
        out.append(float(v[ok].mean()) if ok.sum() > 10 else float("nan"))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference).mean(2)
    dmin = ridge_distance(ref.shape)
    runs = [("reference", ref)]
    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        runs.append((label, load(path).mean(2)))

    dys = np.arange(-25, 25.1, 1.0)
    print("vertical cut through the core column x = %.1f (luminance)" % CORE[0])
    print("  dy     " + "".join("%7.0f" % v for v in dys[::4]))
    vprof = {}
    for label, img in runs:
        v = _bilinear(img, np.full(dys.shape, CORE[0]), CORE[1] + dys)
        vprof[label] = v
        print("  %-7s" % label + "".join("%7.1f" % x for x in v[::4]))

    radii = np.arange(1.0, 46.01, 1.0)
    print("\nwest-sector azimuthal mean, theta %.0f..%.0f, ridges masked at %.0f px"
          % (WEST_SECTOR[0], WEST_SECTOR[1], CORE_CLEAR))
    print("  r      " + "".join("%7.0f" % r for r in radii[::4]))
    wprof = {}
    for label, img in runs:
        wprof[label] = west_profile(img, dmin, radii)
        print("  %-7s" % label + "".join("%7.1f" % v for v in wprof[label][::4]))

    print("\nwest falloff |dL/dr|, cv/px per band  (too flat inside + too steep")
    print("outside is a core whose light sits in a ring rather than a point)")
    print("  %-11s" % "band" + "".join("%10s" % ("r %d-%d" % b) for b in WEST_BANDS))
    for label in wprof:
        v = wprof[label]
        print("  %-11s" % label + "".join(
            "%10.2f" % ((v[a - 1] - v[b - 1]) / (b - a)) for a, b in WEST_BANDS))

    print("\nvertical falloff |dL/d(dy)|, cv/px, the two sides averaged")
    print("  %-11s" % "band" + "".join("%10s" % ("dy %d-%d" % b) for b in VERT_BANDS))
    mid = len(dys) // 2
    for label in vprof:
        v = vprof[label]
        cells = []
        for a, b in VERT_BANDS:
            up = (v[mid - a] - v[mid - b]) / (b - a)
            dn = (v[mid + a] - v[mid + b]) / (b - a)
            cells.append(0.5 * (up + dn))
        print("  %-11s" % label + "".join("%10.2f" % c for c in cells))

    print("\nsigned error against the reference, cv (+ = render too bright)")
    print("  %-11s" % "west r" + "".join("%7.0f" % r for r in radii[::4]))
    for label in wprof:
        if label == "reference":
            continue
        d = wprof[label] - wprof["reference"]
        print("  %-11s" % label + "".join("%7.1f" % x for x in d[::4]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
