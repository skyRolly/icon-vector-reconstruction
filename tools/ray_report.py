#!/usr/bin/env python3
"""Score the flare's diagonal rays against the reference, ray by ray.

    python3 tools/ray_report.py <label> <render.png> [<label> <render.png> ...]

Why this is not a job for the global metric, or even the flare-region one: the
errors here are a REDISTRIBUTION at nearly constant total light.  The reference
has a narrow ray where the reconstruction has a broad pedestal of similar
integrated energy, so a mean absolute error over the region barely moves while
the structure is plainly different.  Measured on the shipped renders, the two
that differ by 0.04 of whole-image MAE are bit-identical within 334 px of the
flare core, so that difference says nothing at all about this region.

Method, per ray direction:
  * sample an annulus in polar coordinates about the flare core;
  * drop every sample within 30 px of either curve ridge (ellipse distance,
    the tools/regions.py formula) -- the right ridge is only 14.5 px east of the
    core, so an unmasked scan reads the curve, not the flare;
  * within the surviving angular island at each radius, take the excess over the
    island's own chord (the straight line between its two ends).  That removes
    the curve-glow gradient without assuming a model for it;
  * report the peak of that excess, the angle it sits at, and the transverse
    FWHM of the peak.

`peak / FWHM` is the hardness: a render with the same integrated energy spread
over a wider ray has a lower value.  That is the number that decides whether a
ray is too hard or too soft, and it wants measuring rather than eyeballing.
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
sys.path.insert(0, HERE)
from regions import ARCS, FLARE_CORE  # noqa: E402

CORE = (FLARE_CORE[0] - 0.5, FLARE_CORE[1] - 0.5)
RIDGE_CLEAR = 30.0
#: SAMPLING angles, in the convention theta = 0 due east, increasing
#: counter-clockwise (y is down, so theta = degrees(atan2(-dy, dx))).
#:
#: THESE ARE NOT THE ARTWORK'S RAY AXES, and the two should not be reconciled by
#: copying one into the other.  `RAY_GEOMETRY` in tools/measure_flare.py holds
#: the layers' geometric axes -- the direction each quadrilateral is built along,
#: fitted to the reference's transverse centre as a function of radius.  What is
#: here is the angle this report SCANS, which only has to put the structure in
#: the window; and the `ref angle` row reports where a chord-excess PEAK lands
#: inside that window, which is a third quantity again, and a biased one.
#:
#: How biased: at 30 px clearance the cleared angular island around the
#: upper-left ray reaches only s = +5.8 / +4.2 / +3.0 px at r = 90 / 95 / 100
#: while extending to -31 / -35 / -38 on the other side, so the chord's positive
#: endpoint lands ON the ray.  Taking the render's own ray field, rotating it by
#: 5 degrees (total flux ratio 1.0000) and putting it back moved this report's
#: peak from 2.64 to 9.11 at r = 90 and from 0.59 to 7.69 at r = 100: a factor of
#: 3.5 to 13 from POSITION alone, with the light unchanged.  That is the whole of
#: a long-standing disagreement between this report and an integrated-flux audit
#: over the upper-left ray's amplitude, and the audit was right.
#: `ISLAND_MARGIN` below now makes those radii report nothing instead.
#:
#: The right-hand pair IS now scanned on the layers' own axes, 44.9 and 328.1.
#: The 45.6 and 327.8 they were scanned at before came with a claim that the
#: reference's peak "sits coherently at 45.6 and 327.8 degrees at every radius",
#: and this tool's own output contradicts it: run on reference.png the
#: upper-right `ref angle` row reads 44.0, 47.5, 45.2, 41.9, 55.1, 43.8, 31.3 --
#: no coherent angle at all -- and the lower-right reads a mean of 328.5 with an
#: sd of 0.8, not 327.8.  Measured properly, the reference's upper-right line
#: lies -0.42 +- 0.28 px from the 44.9 axis over r 65-145, which excludes 45.6 at
#: about 6 sigma.
#:
#: The upper-left is still scanned at 113.6 although its layer is now built at
#: 107.1 with a 5.2 px offset, and that is deliberate: pointing the scan at
#: 107.1 walks the window into the left ridge and costs r 50-70, the radii at
#: which that ray is brightest, while a +-26 px window is +-20 degrees at r = 75
#: and contains the structure comfortably either way.
#:
#: AN OFFSET RAY HAS NO SINGLE ANGLE.  A line displaced s from the sampling
#: origin has an apparent direction of direction + degrees(asin(s/r)), so its
#: angle depends on where it is measured from -- and the two files here do not
#: even share an origin (ray_report's CORE is 1.41 px from the params flare
#: centre).  Any ray angle quoted anywhere in this project has to name its
#: origin to mean anything.
RAYS = (("upper-left", 113.6), ("lower-left", 249.7),
        ("upper-right", 44.9), ("lower-right", 328.1))

#: A chord-excess peak measures BRIGHTNESS only if the chord's endpoints sit off
#: the structure.  This is the clearance, in px at the scan radius, that the
#: island must reach on BOTH sides for that to hold.  The rays here are 8-14 px
#: across, so a half-width is 4-7 px and 8 is that plus a little.
#:
#: What it costs, measured (min of the two island reaches, in px, per radius
#: r = 50..100 in steps of 5):
#:   upper-left    7.0  9.5 12.0 13.5 12.0 10.0  8.5  7.0  5.5  4.0  3.0
#:   lower-left    3.5  6.0  8.0 10.5 13.0 14.0 12.5 11.0 10.0  9.0  8.0
#:   upper-right    --   --   --   --  2.0  6.0  9.5 13.0 16.5 19.5 23.0
#:   lower-right    --  2.0  8.0 14.0 19.0 24.0 26.0 26.0 26.0 26.0 26.0
#: so the upper-left loses r >= 85 and r = 50, the lower-left r <= 55, the
#: upper-right r <= 75 and the lower-right r = 55.  Every one of those is a cell
#: where one chord endpoint sits on the ray; the columns that remain are the
#: ones where this statistic means what it says.
ISLAND_MARGIN = 8.0
RADII = (50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


_RIDGE_CACHE = {}


def ridge_distance(shape):
    """Distance to the nearer curve ridge, memoised by shape.

    Every report masks by this, several of them once per band per channel, and
    it is a pair of 1024x1024 evaluations each time.  Caching it turned a
    three-minute report into a six-second one; the result depends on nothing but
    the shape and the module-level ARCS, so there is nothing to invalidate.
    """
    key = tuple(shape[:2])
    if key in _RIDGE_CACHE:
        return _RIDGE_CACHE[key]
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    dmin = np.full((h, w), 1e9)
    for side, (cx, cy, rx, ry) in ARCS.items():
        u, v = (xx - cx) / rx, (yy - cy) / ry
        rr = np.sqrt(u * u + v * v)
        d = np.abs(rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6)
        dmin = np.minimum(dmin, d)
    dmin.setflags(write=False)
    _RIDGE_CACHE[key] = dmin
    return dmin


def _bilinear(a, x, y):
    h, w = a.shape[:2]
    x0 = np.clip(np.floor(x).astype(int), 0, w - 1)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx, fy = x - x0, y - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def ray_profile(lum, dmin, theta_deg, radii=RADII, half_window=26.0, step=0.5):
    """Chord-excess peak, its angle and its transverse FWHM, at each radius."""
    out = []
    for r in radii:
        dth = math.degrees(step / r)
        span = math.degrees(half_window / r)
        ths = np.arange(theta_deg - span, theta_deg + span + 1e-9, dth)
        rad = np.radians(ths)
        xs = CORE[0] + r * np.cos(rad)
        ys = CORE[1] - r * np.sin(rad)
        vals = _bilinear(lum, xs, ys)
        clear = _bilinear(dmin, xs, ys) > RIDGE_CLEAR
        if clear.sum() < 12:
            out.append(None); continue
        # the island: the contiguous clear run containing the target angle
        idx = np.flatnonzero(clear)
        mid = np.argmin(np.abs(ths - theta_deg))
        if not clear[mid]:
            out.append(None); continue
        lo = mid
        while lo - 1 in idx and clear[lo - 1]:
            lo -= 1
        hi = mid
        while hi + 1 < clear.size and clear[hi + 1]:
            hi += 1
        if hi - lo < 10:
            out.append(None); continue
        seg_t, seg_v = ths[lo:hi + 1], vals[lo:hi + 1]
        # Does the island reach far enough on BOTH sides for the chord's
        # endpoints to be off the structure?  Where it does not, the "peak" is a
        # statement about where the ray sits relative to the mask edge and not
        # about how bright it is -- see the comment on RAYS.  Report nothing.
        s_lo = math.radians(theta_deg - float(seg_t[0])) * r
        s_hi = math.radians(float(seg_t[-1]) - theta_deg) * r
        if min(s_lo, s_hi) < ISLAND_MARGIN:
            out.append(None); continue
        chord = np.linspace(seg_v[0], seg_v[-1], seg_v.size)
        ex = seg_v - chord
        k = int(np.argmax(ex))
        pk = float(ex[k])
        if pk <= 0:
            out.append((0.0, float(seg_t[k]), float("nan"))); continue
        half = pk / 2.0
        a = k
        while a > 0 and ex[a] > half:
            a -= 1
        b = k
        while b < ex.size - 1 and ex[b] > half:
            b += 1
        fwhm = math.radians(float(seg_t[b] - seg_t[a])) * r
        out.append((pk, float(seg_t[k]), fwhm))
    return out


#: Width of the moving average subtracted in the angular high-pass, in px of
#: arc.  Much wider than a ray, much narrower than the island.
THIN_WIN_PX = 24.0


def thin_amplitude(lum, dmin, theta_deg, r, span_px=70.0, core_px=6.0,
                   edge_guard=12.0):
    """Peak of an angular HIGH-PASS at this radius, near the ray's axis.

    The chord excess above is the right measure of a ray's shape, but it has a
    known failure mode: a straight chord across an island whose background is
    curved leaves a residual that peaks in the middle, which looks like a ray
    that is not there.  That matters most on the right-hand side, where the
    ridge mask makes the island narrow.

    So this measures the same place a different way, by removing a LOCAL LINEAR
    fit over a 24 px window rather than a moving average of it.  The difference
    is not cosmetic.  A boxcar mean is unbiased only where the background is
    flat; against a background with a slope it leaves a residual proportional to
    that slope, and the steepest slopes here are at the edge of the ridge mask,
    where the window is also truncated.  Measured, the boxcar read 4.67 code
    values for the reference's upper-right ray at r = 70 where this filter reads
    0.06 -- a factor of 78 -- and that over-reading is what made that ray appear
    to run out to r = 230 when an unbiased statistic ends it at 145 +- 15.

    `edge_guard` is the second half of the same fix: a radius whose ray axis
    lies within 12 px of arc of the mask edge is REFUSED rather than reported,
    because there the window cannot be centred and no filter can rescue it.
    """
    dth = math.degrees(0.5 / r)
    span = math.degrees(span_px / r)
    ths = np.arange(theta_deg - span, theta_deg + span + 1e-9, dth)
    rad = np.radians(ths)
    xs, ys = CORE[0] + r * np.cos(rad), CORE[1] - r * np.sin(rad)
    v = _bilinear(lum, xs, ys)
    ok = _bilinear(dmin, xs, ys) > RIDGE_CLEAR
    if ok.sum() < 40:
        return None
    # how far, in px of arc, the axis sits from the nearest masked sample
    idx = np.flatnonzero(ok)
    mid = int(np.argmin(np.abs(ths - theta_deg)))
    if not ok[mid]:
        return None
    lo = mid
    while lo - 1 >= 0 and ok[lo - 1]:
        lo -= 1
    hi = mid
    while hi + 1 < ok.size and ok[hi + 1]:
        hi += 1
    if min(mid - lo, hi - mid) * 0.5 < edge_guard:
        return None
    half = max(2, int(round(THIN_WIN_PX / 0.5)) // 2)
    out = []
    near = np.abs(ths - theta_deg) <= math.degrees(core_px / r)
    for i in np.flatnonzero(near & ok):
        a, b = max(lo, i - half), min(hi, i + half) + 1
        if b - a < 8:
            continue
        t = np.arange(a, b, dtype=float)
        y = v[a:b]
        # a straight line through the window, then the residual at its centre
        A = np.vstack([t - i, np.ones_like(t)]).T
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        out.append(float(v[i] - coef[1]))
    return max(out) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    ref = load(a.reference)
    dmin = ridge_distance(ref.shape)
    runs = [("reference", ref)]
    for label, path in zip(a.pairs[0::2], a.pairs[1::2]):
        runs.append((label, load(path)))
    for name, th in RAYS:
        print("\n%s ray, theta = %.1f deg  (chord excess, ridges masked at %.0f px)"
              % (name, th, RIDGE_CLEAR))
        print("  %-11s" % "r" + "".join("%8d" % r for r in RADII))
        store = {}
        for label, img in runs:
            prof = ray_profile(img.mean(2), dmin, th)
            store[label] = prof
            print("  %-11s" % (label + " pk") + "".join(
                "     .  " if p is None else "%8.2f" % p[0] for p in prof))
        # The peak's own angle, radius by radius.  A real ray holds one angle
        # across the whole span; a wandering angle means the "ray" is a local
        # maximum of something else, and the fix is not to add a ray element.
        print("  %-11s" % "ref angle" + "".join(
            "     .  " if p is None or p[0] <= 0 else "%8.1f" % p[1]
            for p in store["reference"]))
        print("  %-11s" % "ref FWHM" + "".join(
            "     .  " if p is None or not np.isfinite(p[2]) else "%8.1f" % p[2]
            for p in store["reference"]))
        for label, _ in runs[1:]:
            print("  %-11s" % (label[:8] + " FWHM") + "".join(
                "     .  " if p is None or not np.isfinite(p[2]) else "%8.1f" % p[2]
                for p in store[label]))
        for label, img in runs:
            amps = [thin_amplitude(img.mean(2), dmin, th, r) for r in RADII]
            good = [a for a in amps if a is not None]
            print("  %-11s" % (label[:8] + " thin") + "".join(
                "     .  " if a is None else "%8.2f" % a for a in amps)
                + ("   mean %.2f" % np.mean(good) if good else ""))
        for label, _ in runs:
            ps = [p for p in store[label] if p and np.isfinite(p[2]) and p[2] > 0]
            if ps:
                hard = float(np.mean([p[0] / p[2] for p in ps]))
                print("  %-11s peak/FWHM = %.3f   mean peak %.2f cv, mean FWHM %.1f px"
                      % (label, hard, np.mean([p[0] for p in ps]), np.mean([p[2] for p in ps])))


if __name__ == "__main__":
    sys.exit(main())
