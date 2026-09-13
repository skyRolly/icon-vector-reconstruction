#!/usr/bin/env python3
"""Score the colour of the band flanking each curve, where the paleness is.

    python3 tools/chroma_report.py <label> <render.png> [<label> <render.png> ...]

The review's secondary objective was overall colour saturation. Measured over
the whole canvas that finding does not hold: the render's mean chroma is 1.2%
ABOVE the reference's, so a global saturation boost would move most of the
image the wrong way. The paleness is real but local -- it is a band roughly 16
px wide flanking each curve ridge, and that is what this measures.

For each ring of ridge distance the report gives the mean R, G and B, the
chroma (max - min channel), and the hue angle in the RG/B plane. Hue is the
diagnostic quantity: the reconstruction can carry the right luminance and the
right chroma there and still be the wrong colour, which is what "pale" turns
out to mean here -- too much white and blue, not enough cyan.

Only pixels inside the frame are counted, and the flare is excluded (within 150
px of its core), so the numbers are about the curve glow alone.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from ray_report import CORE, load, ridge_distance  # noqa: E402

#: Ridge-distance rings, in px.  The band the paleness sits in is the first few.
RINGS = ((0, 4), (4, 8), (8, 12), (12, 16), (16, 24), (24, 40), (40, 70))
FLARE_EXCLUDE = 150.0
FRAME_INSET = 110.0


def hue_deg(r, g, b):
    """Hue angle, degrees, 0 = red, 120 = green, 240 = blue."""
    return math.degrees(math.atan2(math.sqrt(3.0) * (g - b), 2.0 * r - g - b)) % 360.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference)
    h, w = ref.shape[:2]
    dmin = ridge_distance(ref.shape)
    yy, xx = np.mgrid[0:h, 0:w]
    keep = (np.hypot(xx - CORE[0], yy - CORE[1]) > FLARE_EXCLUDE)
    keep &= (xx > FRAME_INSET) & (xx < w - FRAME_INSET)
    keep &= (yy > FRAME_INSET) & (yy < h - FRAME_INSET)

    runs = [("reference", ref)]
    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        runs.append((label, load(path)))

    masks = [(lo, hi, keep & (dmin >= lo) & (dmin < hi)) for lo, hi in RINGS]
    print("mean channels by ridge distance (frame and flare excluded)")
    for lo, hi, m in masks:
        print("\n  ridge %2d-%2d px   n = %d" % (lo, hi, int(m.sum())))
        print("    %-11s %7s %7s %7s %8s %8s" % ("", "R", "G", "B", "chroma", "hue"))
        base = None
        for label, img in runs:
            r, g, b = (img[..., k][m].mean() for k in range(3))
            ch = max(r, g, b) - min(r, g, b)
            hu = hue_deg(r, g, b)
            if base is None:
                base = (r, g, b, ch, hu)
                print("    %-11s %7.2f %7.2f %7.2f %8.2f %8.1f" % (label, r, g, b, ch, hu))
            else:
                print("    %-11s %7.2f %7.2f %7.2f %8.2f %8.1f   "
                      "dR %+6.2f dG %+6.2f dB %+6.2f dchroma %+6.2f dhue %+5.1f"
                      % (label, r, g, b, ch, hu,
                         r - base[0], g - base[1], b - base[2], ch - base[3],
                         (hu - base[4] + 180.0) % 360.0 - 180.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
