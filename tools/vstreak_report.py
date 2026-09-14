#!/usr/bin/env python3
"""Score the vertical diffraction streak through the flare's brightest point.

    python3 tools/vstreak_report.py <label> <render.png> [<label> <render.png> ...]

The reference carries a narrow vertical line through the core that no radial or
horizontal statistic can see, and that a luminance statistic cannot see either:
within about 12 px of the core, G and B are CLIPPED (421 and 453 px at or above
253 in a 90x90 box, against 4 for R), so mean(RGB) there measures the clip and
not the light.  R is the primary channel here for that reason.

THE STATISTIC.  For a column x and a band of rows,

    A_k(x) = mean over rows of [ V(x,y) - 0.5*(V(x-k,y) + V(x+k,y)) ]

a mean over rows, never a peak -- the reference's JPEG grain makes a per-row
maximum a biased estimator, which is the specific error that produced several
retracted claims in an earlier pass.  Two derived quantities:

    N = (4*A_2 - A_4) / 3

which is identically zero for any background quadratic in x over +-4 px, so it
cancels the bloom's own transverse curvature rather than assuming it away; and
the far-band offset, the same A_k at the same column over |dy| 150..430, where
the streak is known to be absent.  Every amplitude below has that offset
subtracted, so a constant error in the baseline cannot masquerade as a line.

WHAT IS NOT MEASURABLE, and is therefore not scored:
  * inside |dy| ~ 16 the bloom's transverse curvature produces most of the
    signal (reference A_4 = 9.46 against the render's 7.52 with no vertical
    element at all), so no amplitude there can be separated from the bloom;
  * dx +6..+25 is inside the right curve ridge.  The only limit available there
    is 11.6 cv at 95%, looser than the streak's own amplitude, so the honest
    position is silence -- this report says nothing about it either way.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from ray_report import load  # noqa: E402

#: Measured axis of the streak: array x 528.9 +- 0.5 (SVG user x 529.4 +- 0.5).
#: It is NOT at FLARE_CORE's x of 530.45, and that offset is real but has not
#: been separately confirmed with the rays masked, so nothing here moves the
#: core -- this report only measures the column it was told to.
AXIS = 528.9
CORE_Y = 512.83
#: The bands the amplitude was tabulated over.  The profile has a factor-3.1
#: STEP between |dy| 30 and 36.5 that neither a power law (slope -1.84) nor an
#: exponential (scale height 31.7 px) reproduces, so it is tabulated rather
#: than fitted; forcing either law would misplace most of the light.
BANDS = ((16, 26), (26, 36), (36, 50), (50, 70), (70, 90), (90, 110))
#: Where the streak is established to be absent: used as the baseline, and as
#: the null that says the statistic reads zero when there is nothing there.
FAR = (150, 430)
KS = (2, 3, 4, 5, 6)


def _col(img, x, ys, ch):
    """Bilinear sample of one column at sub-pixel x, over integer rows."""
    x0 = int(np.floor(x))
    t = x - x0
    a = img[ys, x0, ch] if ch >= 0 else img[ys, x0].mean(1)
    b = img[ys, x0 + 1, ch] if ch >= 0 else img[ys, x0 + 1].mean(1)
    return a * (1 - t) + b * t


def a_k(img, ys, k, ch, axis=AXIS):
    c = _col(img, axis, ys, ch)
    l = _col(img, axis - k, ys, ch)
    r = _col(img, axis + k, ys, ch)
    return float(np.mean(c - 0.5 * (l + r)))


def rows(lo, hi):
    up = np.arange(int(round(CORE_Y - hi)), int(round(CORE_Y - lo)))
    dn = np.arange(int(round(CORE_Y + lo)), int(round(CORE_Y + hi)))
    return np.concatenate([up, dn])


def band_values(img, ch):
    """A_4 and N per band, each with the far-band baseline removed."""
    far = rows(*FAR)
    base4 = a_k(img, far, 4, ch)
    base2 = a_k(img, far, 2, ch)
    out = []
    for lo, hi in BANDS:
        ys = rows(lo, hi)
        v4 = a_k(img, ys, 4, ch) - base4
        v2 = a_k(img, ys, 2, ch) - base2
        out.append((lo, hi, v4, (4 * v2 - v4) / 3.0))
    return out, base4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--channel", default="R", choices=("R", "G", "B", "L"))
    a = ap.parse_args()
    ch = {"R": 0, "G": 1, "B": 2, "L": -1}[a.channel]
    if ch == -1:
        print("NOTE: luminance is clipped near the core; R is the honest channel.")
    runs = [("reference", load(a.reference))]
    runs += [(n, load(p)) for n, p in zip(a.pairs[0::2], a.pairs[1::2])]

    print("vertical streak at array x %.1f, channel %s, far-band baseline "
          "(|dy| %d..%d) removed" % (AXIS, a.channel, FAR[0], FAR[1]))
    print("A_4 is the two-point high pass; N cancels any background quadratic "
          "in x over +-4 px.\n")
    hdr = "  %-12s" % "|dy| band" + "".join("%9s" % ("%d-%d" % b) for b in BANDS)
    for stat_i, stat_name in ((2, "A_4"), (3, "N")):
        print("%s   [%s]" % (hdr, stat_name))
        base = None
        for label, img in runs:
            vals, off = band_values(img, ch)
            v = [r[stat_i] for r in vals]
            line = "  %-12s" % label + "".join("%9.2f" % x for x in v)
            if base is None:
                base = v
            else:
                line += "   rms err %.2f" % float(np.sqrt(np.mean(
                    (np.array(v) - np.array(base)) ** 2)))
            print(line + "    (far-band offset %+.2f)" % off)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
