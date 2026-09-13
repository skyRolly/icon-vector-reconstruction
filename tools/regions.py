#!/usr/bin/env python3
"""Measured anchors and region geometry shared by the fitter and the diagnostics.

Both the fitting weight and the diagnostic reports need to talk about the same
places -- "the concave side of the left curve, 70 px out", "within 110 px of
the central light" -- so those definitions live here once rather than being
restated (and drifting) in each tool.

All coordinates are SVG user space at 1024 px; every helper scales to the
shape it is given.
"""
from __future__ import annotations

import numpy as np

#: Centroid of the reference's off-arc pixels above luminance 245, which agrees
#: with the peak of the isolated flare to within a pixel.
FLARE_CORE = (530.95, 513.33)

#: Fitted lens ellipses of the two luminous curves.  Used only to define
#: distance-from-the-curve; the rendered curves are cubic Beziers.
ARCS = {"left": (78.913, 515.286, 386.05, 467.47),
        "right": (923.121, 515.048, 378.12, 463.35)}

#: Frame centre-lines, from the opaque-bar fits in src/params.json.  Only used
#: to keep the frame's own stroke and rim glow out of the curve-profile bins.
FRAME = {"left": 66.5225, "top": 34.3555, "right": 951.57, "bottom": 991.6551}

#: Signed-distance bin edges for the cross-curve profile.  Negative is the
#: concave side (the lobe, towards the nearer frame edge), positive the convex
#: side (between the two curves).  The +-9 px gap skips the core stroke itself,
#: whose sub-pixel edge placement dominates any comparison there.
PROFILE_EDGES = (-300, -240, -190, -150, -115, -90, -70, -52, -38, -28, -20, -14, -9,
                 9, 14, 20, 28, 38, 52, 70, 90, 115, 150)


def curve_frame(shape):
    """Signed distance to the nearer curve, its along-curve angle, flare radius.

    `d < 0` is the concave side.  The distance is the ellipse's radial distance
    scaled to pixels, which agrees with the true normal distance to better than
    1% over the range used here.
    """
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    sx, sy = w / 1024.0, h / 1024.0
    X = (xx + 0.5) / sx
    Y = (yy + 0.5) / sy
    dsig = np.full((h, w), 1e9, np.float32)
    tang = np.zeros((h, w), np.float32)
    for side, (cx, cy, rx, ry) in ARCS.items():
        a = (X - cx) / rx
        b = (Y - cy) / ry
        rr = np.sqrt(a * a + b * b)
        d = (rr - 1.0) * np.sqrt((a * rx) ** 2 + (b * ry) ** 2) / np.maximum(rr, 1e-6)
        t = np.degrees(np.arctan2(b, a if side == "left" else -a))
        take = np.abs(d) < np.abs(dsig)
        dsig = np.where(take, d, dsig).astype(np.float32)
        tang = np.where(take, t, tang).astype(np.float32)
    rfl = np.hypot(X - FLARE_CORE[0], Y - FLARE_CORE[1]).astype(np.float32)
    return dsig, tang, rfl


def interior(shape, margin=18.0):
    """Inside the frame by `margin` px, in SVG user space."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    X = (xx + 0.5) / (w / 1024.0)
    Y = (yy + 0.5) / (h / 1024.0)
    return ((X > FRAME["left"] + margin) & (X < FRAME["right"] - margin)
            & (Y > FRAME["top"] + margin) & (Y < FRAME["bottom"] - margin))


#: Along-curve bands for the 2-D profile cells.  `t` is the lens ellipse's
#: parametric angle, 0 at the waist.  The bands stop at 66 degrees because that
#: is where the drawn curves end: the four Bezier endpoints sit at |t| = 66.1,
#: 66.8, 67.6 and 68.9 degrees.  Beyond them there is no curve, so a cell there
#: would be asking the glow layers to light a region that has no source -- the
#: light the reference does have past the tips belongs to the frame's interior
#: corners, which is a separate element (`corner_in`).
PROFILE_T_BANDS = ((0, 22), (22, 40), (40, 54), (54, 66))


def profile_cells(shape, flare_exclude=200.0, min_px=150, margin=18.0,
                  t_bands=PROFILE_T_BANDS):
    """Masks for signed-distance x along-curve cells, pooled over both curves.

    The 1-D pooled bins below hide an error the cells expose: with the curve
    tips left out, the fit drained them, and the lobe within 80 px of a tip
    ended up 20-30% too dark while every pooled bin looked fine.  Scoring
    cells instead of bins is what keeps the whole length of each curve in the
    objective.
    """
    dsig, tang, rfl = curve_frame(shape)
    keep = (rfl > flare_exclude) & interior(shape, margin)
    at = np.abs(tang)
    out = []
    for lo, hi in zip(PROFILE_EDGES[:-1], PROFILE_EDGES[1:]):
        if lo == -9:
            continue
        band = keep & (dsig >= lo) & (dsig < hi)
        for t0, t1 in t_bands:
            m = band & (at >= t0) & (at < t1)
            if m.sum() >= min_px:
                out.append((lo, hi, t0, t1, m))
    return out


#: Distance-from-the-frame bands for the interior corner cells.
CORNER_EDGES = (12, 45, 100, 170)


def frame_distance(shape):
    """Distance inside the frame's bounding box, in SVG user units."""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    X = (xx + 0.5) / (w / 1024.0)
    Y = (yy + 0.5) / (h / 1024.0)
    return np.minimum(np.minimum(X - FRAME["left"], FRAME["right"] - X),
                      np.minimum(Y - FRAME["top"], FRAME["bottom"] - Y)).astype(np.float32)


def corner_cells(shape, min_px=300, corner_span=230.0):
    """Masks for the light in the four interior corners.

    Past the curve ends there is no curve glow, but the reference is not dark
    there: within 100 px of the frame the corner quadrants read 9.5-11.0 code
    values against 7.0-8.3 rendered before `corner_in` was added, while the
    edge midpoints agreed to 0.1-0.7.  These cells put that region in the
    objective on the same footing as the curve profile.
    """
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    X = (xx + 0.5) / (w / 1024.0)
    Y = (yy + 0.5) / (h / 1024.0)
    dsig, tang, rfl = curve_frame(shape)
    dfr = frame_distance(shape)
    near_corner = ((np.minimum(np.abs(X - FRAME["left"]), np.abs(X - FRAME["right"])) < corner_span)
                   & (np.minimum(np.abs(Y - FRAME["top"]), np.abs(Y - FRAME["bottom"])) < corner_span))
    keep = interior(shape, 12.0) & near_corner & (dsig < -40.0) & (rfl > 250.0)
    out = []
    for lo, hi in zip(CORNER_EDGES[:-1], CORNER_EDGES[1:]):
        for top in (True, False):
            m = keep & (dfr >= lo) & (dfr < hi) & ((Y < 512) if top else (Y >= 512))
            if m.sum() >= min_px:
                out.append((lo, hi, "top" if top else "bottom", m))
    return out


def weight_cells(shape, min_px=300):
    """Every cell the fitting weight equalises: curve profile plus corners.

    The two sets are made disjoint.  Overlapping cells would each be given a
    per-pixel weight computed as if they owned their pixels outright, and the
    shared pixels would then take whichever value was written last -- which
    silently unbalances both (the cost of a 1% error went from 2.3x to 6.2x
    across cells when they were allowed to overlap).
    """
    prof = profile_cells(shape)
    taken = np.zeros(shape[:2], bool)
    for cell in prof:
        taken |= cell[-1]
    out = list(prof)
    for lo, hi, half, m in corner_cells(shape):
        m = m & ~taken
        if m.sum() >= min_px:
            out.append((lo, hi, half, m))
    return out


def profile_bins(shape, flare_exclude=200.0, t_limit=62.0, min_px=200, margin=18.0):
    """Masks for the signed-distance bins, pooled over both curves.

    Pixels nearer the flare than `flare_exclude` are dropped: the flare is a
    separate element and would otherwise be read as curve glow.  `t_limit`
    keeps to the part of each curve whose normal stays inside the frame, and
    `margin` keeps the frame's own stroke out: where the curves are furthest
    apart the inter-curve bins reach the top and bottom edges, and including
    the frame there tripled those bins' internal brightness spread.
    """
    dsig, tang, rfl = curve_frame(shape)
    keep = (rfl > flare_exclude) & (np.abs(tang) < t_limit) & interior(shape, margin)
    out = []
    for lo, hi in zip(PROFILE_EDGES[:-1], PROFILE_EDGES[1:]):
        if lo == -9:
            continue
        m = keep & (dsig >= lo) & (dsig < hi)
        if m.sum() >= min_px:
            out.append((lo, hi, m))
    return out
