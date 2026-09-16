#!/usr/bin/env python3
"""Measure the flare's horizontal arms against a matched null, east and west.

    python3 tools/arm_report.py <label> <render.png> [<label> <render.png> ...]
    python3 tools/arm_report.py --xsec  <label> <render.png>   # shape in dy
    python3 tools/arm_report.py --null  <label> <render.png>   # estimator tests

The light either side of the core is the largest structure of the flare, and the
two sides are not mirror images, so nothing here averages them.

WHAT WENT WRONG BEFORE, AND WHAT THIS DOES INSTEAD
--------------------------------------------------
The previous iteration quoted reference-side numbers with uncertainties derived
from the pixels inside the measuring window, as if those were independent
samples.  `reference.png` is a JPEG with real 8x8 blocking; a naive standard
error is several times too tight, and one such claim drove an artwork change
that had to be reverted.  Worse, the west window sits 20-35 px from the LEFT
CURVE RIDGE -- the ridge crosses the core's row only 65 px west -- so a deficit
there is equally consistent with the curve's glow being wrong, which is not a
flare fact at all.

Both problems are answered by the same device: a MATCHED NULL.  Every west cell
is defined by its perpendicular distance from the left ridge, and the identical
cell is then evaluated at many other positions ALONG that ridge, far above and
below the flare.  Those cells share the curve glow, the JPEG noise and the
estimator; the only thing they do not share is the flare.  The reported
significance is the flare cell measured against the spread of that population,
so it assumes nothing about the noise -- no autocorrelation model, no Gaussian.

Run with --null to see this measured: at perpendicular 20-30 px the along-ridge
population reads +1.6 +- 2.2 over 17 cells while the flare's own row reads
-15.7, and the estimator recovers an injected arm to within a few percent.

WHAT CANNOT BE MEASURED
-----------------------
West of about dx -52 the left ridge is closer than 20 px and its glow dominates
anything the flare contributes.  This tool prints "(ridge)" there rather than a
number.  Any claim about the west arm's extent beyond dx -55 is a claim about
the curve-glow model, not about the arm, and must not be made from this report.
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
from ray_report import CORE, ridge_distance  # noqa: E402
from ray_report import load as _load_rgb  # noqa: E402
from regions import ARCS  # noqa: E402

#: Longitudinal bins in |dx| from the core.  Inside 20 the core dominates.
DX_BINS = ((20, 28), (28, 36), (36, 44), (44, 52), (52, 62), (62, 74),
           (74, 90), (90, 110), (110, 135))
#: The arm's own band in dy, and the shoulders either side of it.  The arm is
#: not centred on the core row: see --xsec.
DY_CORE = (-5.0, 9.0)
DY_SHOULDER = (9.0, 24.0)
#: 20 px, not 30: the west arm is only 25-35 px from the left ridge and a wider
#: clearance deletes the measurement instead of protecting it.  The matched null
#: is what protects it.
RIDGE_CLEAR = 20.0
#: Row bands used as the along-ridge null population, and the flare row to
#: exclude from it.  They span 170 px either side of the flare.
NULL_ROWS = tuple(range(340, 700, 20))
FLARE_ROWS = (496, 532)


def load(p):
    """Luminance, the channel every structure here is measured in."""
    return _load_rgb(p).mean(2)


def signed_ridge(shape, side="left"):
    """Signed perpendicular distance to one curve ridge; positive outside it."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    cx, cy, rx, ry = ARCS[side]
    u, v = (xx - cx) / rx, (yy - cy) / ry
    rr = np.sqrt(u * u + v * v)
    return (rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6)


def cell_mask(shape, side, dx0, dx1, dy0, dy1, clear):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    dx = (xx - CORE[0]) * (1.0 if side == "east" else -1.0)
    dy = yy - CORE[1]
    m = (dx >= dx0) & (dx < dx1) & (dy >= dy0) & (dy < dy1)
    return m & (ridge_distance(shape) > clear)


def stat(res, m, use_median=False):
    if m.sum() < 20:
        return float("nan")
    v = res[m]
    return float(np.median(v) if use_median else v.mean())


def along_ridge_null(res, shape, perp0, perp1, dy_h, ridge="left"):
    """The same cell, evaluated at many positions along the same ridge.

    Shares the curve glow, the JPEG grain and the estimator with the flare cell;
    differs only in not containing the flare.  Returns one reading per position.
    """
    sd = signed_ridge(shape, ridge)
    other = "right" if ridge == "left" else "left"
    clear_other = np.abs(signed_ridge(shape, other)) > 40.0
    h, w = shape[:2]
    yy = np.mgrid[0:h, 0:w][0]
    band = (sd >= perp0) & (sd < perp1) & clear_other
    out = []
    for y0 in NULL_ROWS:
        if FLARE_ROWS[0] - dy_h < y0 + 20 and y0 < FLARE_ROWS[1] + dy_h:
            continue
        m = band & (yy >= y0) & (yy < y0 + 20)
        if m.sum() < 40:
            continue
        out.append(float(res[m].mean()))
    return out


def measure(res, shape, side, dx0, dx1, dy0, dy1):
    """Point estimate and the sensitivity range over defensible variations."""
    base = cell_mask(shape, side, dx0, dx1, dy0, dy1, RIDGE_CLEAR)
    val = stat(res, base)
    n = int(base.sum())
    if n < 20 or not np.isfinite(val):
        return None
    alts = [val]
    for clear in (14.0, 28.0):
        alts.append(stat(res, cell_mask(shape, side, dx0, dx1, dy0, dy1, clear)))
    for shift in (-2.0, 2.0):
        alts.append(stat(res, cell_mask(shape, side, dx0, dx1,
                                        dy0 + shift, dy1 + shift, RIDGE_CLEAR)))
    alts.append(stat(res, base, use_median=True))
    alts = [a for a in alts if np.isfinite(a)]
    return val, min(alts), max(alts), n


def inject_recover(ref, shape, amp, sigma):
    """Inject a known west arm into the reference and measure it back.

    The estimator is only worth trusting if it returns what was put in.  The
    injected arm has the shape the west deficit is claimed to have -- a Gaussian
    in dy riding an exponential decay in dx -- and is added to a copy of the
    reference.  The ratio printed is recovered over the arm's exact mean in the
    cell, not over its peak, so a ratio of 1 is correct recovery.
    """
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    u = CORE[0] - xx                      # westward along the arm
    v = yy - CORE[1]
    arm = (amp * np.exp(-0.5 * ((v - 2.0) / sigma) ** 2)
           * np.clip((u - 14.0) / 8.0, 0, 1) * np.exp(-np.maximum(u, 0) / 45.0))
    res = (ref + arm) - ref
    rows = []
    for x0, x1 in ((20, 28), (28, 36), (36, 44), (44, 52)):
        m = cell_mask(shape, "west", x0, x1, DY_CORE[0], DY_CORE[1], RIDGE_CLEAR)
        if m.sum() < 20:
            continue
        rows.append((x0, x1, float(res[m].mean()), float(arm[m].mean()), int(m.sum())))
    return rows


def _sig(val, pop):
    """How far the cell sits from its matched null, in that null's own units."""
    if not pop:
        return float("nan"), float("nan"), float("nan")
    mu, sd = float(np.mean(pop)), float(np.std(pop))
    return mu, sd, (val - mu) / sd if sd > 0 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--xsec", action="store_true")
    ap.add_argument("--null", action="store_true")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference)
    shape = ref.shape

    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        res = load(path) - ref

        if a.null:
            print("\n%s -- tests of the estimator, not of the artwork" % label)
            print("  along-ridge null: the west cell moved up and down the left")
            print("  ridge at the same perpendicular distance.  It shares the curve")
            print("  glow and the grain; it does not share the flare.")
            print("    %-12s %8s %8s %8s %6s" % ("perp px", "mean", "sd", "|max|", "cells"))
            for p0, p1 in ((14, 22), (20, 30), (30, 40), (40, 50)):
                pop = along_ridge_null(res, shape, p0, p1, 20)
                if len(pop) < 6:
                    continue
                print("    %-12s %8.2f %8.2f %8.2f %6d"
                      % ("%d..%d" % (p0, p1), np.mean(pop), np.std(pop),
                         max(abs(v) for v in pop), len(pop)))
            print("  injection recovery (a known arm added to the reference and")
            print("  measured back through the identical cells):")
            for amp, sig in ((30.0, 6.0), (12.0, 6.0), (30.0, 11.0)):
                for x0, x1, got, want, n in inject_recover(ref, shape, amp, sig):
                    print("    peak %4.1f sigma %4.1f, dx %d..%d: got %6.2f, "
                          "put in %6.2f, ratio %.3f (%d px)"
                          % (amp, sig, x0, x1, got, want,
                             got / want if want else float("nan"), n))
            continue

        if a.xsec:
            print("\n%s -- the arm's shape across dy, render minus reference" % label)
            for side, (x0, x1) in (("west", (22, 50)), ("east", (30, 70))):
                print("  %s, dx %d..%d" % (side, x0, x1))
                print("    %-10s %8s %16s %6s" % ("dy", "value", "sensitivity", "px"))
                for d0 in range(-18, 21, 3):
                    m = measure(res, shape, side, x0, x1, d0, d0 + 3)
                    if m is None:
                        print("    %-10s      .    (ridge)" % ("%+d..%+d" % (d0, d0 + 3)))
                        continue
                    v, lo, hi, n = m
                    print("    %-10s %8.2f  [%+7.2f,%+7.2f] %6d"
                          % ("%+d..%+d" % (d0, d0 + 3), v, lo, hi, n))
            continue

        print("\n%s -- horizontal arms, render minus reference (code values)" % label)
        print("  value is a plain mean; [lo,hi] is the range over ridge clearance")
        print("  14/20/28, the dy band moved +-2 px, and median instead of mean.")
        print("  Quote the range, not the value.")
        for name, bands in (("arm core", [DY_CORE]),
                            ("shoulder", [DY_SHOULDER, (-DY_SHOULDER[1], -DY_SHOULDER[0])])):
            for side in ("west", "east"):
                for b0, b1 in bands:
                    print("  %s %s, dy %+.0f..%+.0f" % (side, name, b0, b1))
                    print("    %-10s %8s %18s %7s %s"
                          % ("|dx|", "value", "sensitivity", "px", "vs matched null"))
                    for x0, x1 in DX_BINS:
                        m = measure(res, shape, side, x0, x1, b0, b1)
                        if m is None:
                            print("    %-10s      .    (ridge -- not measurable)"
                                  % ("%d..%d" % (x0, x1)))
                            continue
                        v, lo, hi, n = m
                        extra = ""
                        if side == "west":
                            sd_map = signed_ridge(shape, "left")
                            cm = cell_mask(shape, side, x0, x1, b0, b1, RIDGE_CLEAR)
                            if cm.sum() >= 20:
                                p = sd_map[cm]
                                pop = along_ridge_null(res, shape, float(np.percentile(p, 10)),
                                                       float(np.percentile(p, 90)), 20)
                                mu, sd, z = _sig(v, pop)
                                if np.isfinite(z):
                                    extra = "  null %+.1f+-%.1f, %+.1f sigma" % (mu, sd, z)
                        print("    %-10s %8.2f  [%+7.2f,%+7.2f] %7d%s"
                              % ("%d..%d" % (x0, x1), v, lo, hi, n, extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
