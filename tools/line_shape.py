#!/usr/bin/env python3
"""Measure the long horizontal line's TRANSVERSE shape and colour, not its height.

    python3 tools/line_shape.py <label> <render.png> [<label> <render.png> ...]

`tools/line_report.py` scores the three horizontal lines' amplitudes at one row
each.  That is the wrong instrument for two of the three complaints against the
main line, because both are about how its light is DISTRIBUTED rather than how
much of it there is:

  skirt fraction   the share of the line's transverse light lying beyond
                   |dy| = 3 px.  The reference puts 0.55-0.78 of it out there
                   over |dx| 150-280 west and 100-210 east; a render that puts
                   0.17-0.49 has the same total light in a harder line.  The
                   narrow core's own FWHM is NOT the difference: 4.04 +- 0.54 px
                   in the reference against 3.88 +- 0.26 in the render, a
                   difference of 0.16 +- 0.60 px, so "too thin" is not
                   supported and "too concentrated" is.

  R/G              the line's colour.  The reference's core runs R/G = 0.075
                   and its skirt is pure cyan (R/G = 0.00 +- 0.09).  A grey
                   layer standing in for that skirt reads 1.00 and makes the
                   line white -- which is what "too white" means in a number.

Both are taken from a model-free transverse excess: at each column the row
value minus the mean of two reference rows well outside the line, so no bloom
model enters, and averaged over columns within a band.  The ridge mask is the
usual one; bands that the curves swallow print a dot rather than a number.

WHERE THIS TOOL IS NOT TRUSTWORTHY, stated because it is easier to misread a
printed number than an absent one.  The outermost bands, |dx| beyond about 210,
carry so little light that both quantities are ratios of small differences: the
REFERENCE itself reads R/G = -0.371 and a skirt fraction of 0.124 there, against
0.00 +- 0.09 and 0.55-0.78 from a more careful pass over the same region.  Those
columns are measuring their own baseline.  Read the |dx| 50..210 bands, where
the reference's own values agree with an independent method, and treat the ends
as a consistency check on the estimator rather than as data.
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
from ray_report import load  # noqa: E402

#: |dx| bands, signed: negative is west.  Chosen to match where the difference
#: was established (west 150-280, east 100-210) plus the near field either side.
BANDS = ((-280, -210), (-210, -150), (-150, -100), (-100, -50),
         (50, 100), (100, 150), (150, 210), (210, 280))
#: Rows sampled across the line, and the far rows the baseline comes from.
DY = tuple(range(-13, 14))
BASE_DY = (-26, -22, 22, 26)
CLEAR = 24.0
SKIRT = 3


def excess(img, shape, x0, x1, ch):
    """Transverse profile of the line's own light, baseline removed."""
    keep = ridge_distance(shape) > CLEAR
    y0 = int(round(CORE[1]))
    xa, xb = int(round(CORE[0] + x0)), int(round(CORE[0] + x1))
    chan = img[:, :, ch] if ch >= 0 else img.mean(2)
    base = np.zeros(xb - xa)
    nb = np.zeros(xb - xa)
    for d in BASE_DY:
        ok = keep[y0 + d, xa:xb]
        base += np.where(ok, chan[y0 + d, xa:xb], 0.0)
        nb += ok
    if (nb < 2).all():
        return None
    good = nb >= 2
    base = np.where(good, base / np.maximum(nb, 1), 0.0)
    out = []
    for d in DY:
        ok = keep[y0 + d, xa:xb] & good
        if ok.sum() < 12:
            return None
        out.append(float((chan[y0 + d, xa:xb][ok] - base[ok]).mean()))
    return np.array(out)


def stats(e):
    """Skirt fraction and peak of a transverse profile."""
    tot = e.sum()
    if tot <= 0:
        return float("nan"), float("nan")
    core = e[[i for i, d in enumerate(DY) if abs(d) <= SKIRT]].sum()
    return float((tot - core) / tot), float(e.max())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference)
    runs = [("reference", ref)] + [(n, load(p)) for n, p in
                                   zip(a.pairs[0::2], a.pairs[1::2])]
    shape = ref.shape
    for title, fn in (("skirt fraction beyond |dy| = %d px" % SKIRT,
                       lambda img, b: stats(excess(img, shape, b[0], b[1], -1))[0]),
                      ("R/G of the line's own light", None)):
        print("\n%s" % title)
        print("  %-12s" % "dx band" + "".join("%11s" % ("%d..%d" % b) for b in BANDS))
        for label, img in runs:
            row = "  %-12s" % label
            for b in BANDS:
                if fn is None:
                    er = excess(img, shape, b[0], b[1], 0)
                    eg = excess(img, shape, b[0], b[1], 1)
                    v = (float(er.sum() / eg.sum())
                         if er is not None and eg is not None and eg.sum() > 1e-6
                         else float("nan"))
                else:
                    e = excess(img, shape, b[0], b[1], -1)
                    v = fn(img, b) if e is not None else float("nan")
                row += "      .    " if not np.isfinite(v) else "%11.3f" % v
            print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
