#!/usr/bin/env python3
"""The recurring visual failures, as checks that compare against the reference.

    python3 tools/visual_regression.py out/render_1024.png

Seven structures have each been reported wrong, fixed, and reported wrong again
across iterations.  A whole-image metric cannot protect any of them: every one
of them is worth less than 0.01 MAE, so an optimiser will trade all seven away
for a hundredth of a code value and the aggregate will improve.

Every check here is therefore stated as a RATIO TO THE REFERENCE rather than as
a threshold on the render.  A hard-coded pixel count would encode one release's
accidents -- and on an image with real JPEG blocking it would encode some of the
compression as well.  The reference is measured with the same estimator as the
render, on the same cells, and the check is that the two agree to within a band.

The bands are deliberately WIDE.  These are not accuracy tests; the diagnostics
do accuracy.  They are presence tests, and the failure they exist to catch is a
structure quietly going to zero -- which is what "the optimiser smoothed the
rays away again" looks like from the inside.

Each check returns (value, lo, hi) where `value` is the render's statistic as a
fraction of the reference's, so 1.00 is agreement and the interval says how far
from it is tolerable.  `None` means the ratio could not be formed, and WHICH
SIDE could not form it decides the verdict: the reference unable to establish
the structure is a pass, because a check that cannot see its structure in the
source must not claim the render lost it; the render unable to, while the
reference can, is a failure, because that is what losing it looks like.

PRESENCE, NOT FIDELITY.  Every band here is a gate against a structure
disappearing or being over-driven, and several floors are set where the CURRENT
artwork sits rather than where agreement with the reference would be: the two
right rays pass at 0.49 and 0.76 of the reference because that is what they
measure today, and the floors exist only to stop them getting worse.  A green
run therefore means "nothing the reference has has vanished from the render",
NOT "the render agrees with the reference".  Fidelity is what out/metrics.json
and tools/diagnose.py report; read those for how close the artwork is, and read
this for whether a change has quietly deleted something.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from regions import ARCS, FLARE_CORE  # noqa: E402

CORE = (FLARE_CORE[0] - 0.5, FLARE_CORE[1] - 0.5)

#: The four ray axes, in the theta = 0 east, counter-clockwise convention.
#: These are SAMPLING angles for a presence test, not the artwork's geometry --
#: a ray displaced by a few px still has to show up here, which is the point.
#: ...and the radii each is measurable at.  These are NOT the same for the two
#: sides and pretending they were is a mistake this file made first: the right
#: curve ridge crosses only ~15 px east of the core, so at r 55-105 the eastern
#: annulus is mostly deleted by the 20 px clearance and what survives is field
#: rather than ray.  Deleting all four rays then moved the upper-right statistic
#: only from 7.54 to 6.31 -- a check that barely notices its structure being
#: removed.  Further out the same rays clear the ridge by 35-85 px.
#: Each ray's radii are the ones at which THAT ray dominates the statistic, and
#: they were chosen by deleting all four rays and asking how much of the number
#: disappeared.  At r 55-105 for all four, deleting every ray moved the
#: upper-right figure by 5% -- the check was reading the right arc's glow.  At
#: the radii below the ray's own share is 98 / 82 / 80 / 92 per cent.
#:
#: The lower-left ray is no longer read here but on its measured line in
#: LINE_AXES.  It does not pass through the core: fitted band by band, its ridge
#: is a line at 255.2 degrees missing the core by 7 px (the geometry of record
#: had noted the "+4.5 deg with a compensating -7 px offset" and declined to
#: apply it), and the reference also carries a real 267-degree ray in exactly
#: the window this statistic takes as the empty flank.  Once both are drawn
#: where the reference has them, the wedge compares a ray with a ray: removing
#: the 267-degree segment alone moves it from -0.41 to +1.71 while the lower-left
#: ray's own line profile is unchanged.  A presence test that a correctly
#: placed ray fails and a misplaced one passes is testing the placement.
RAY_AXES = (("upper-left", 113.6, 55.0, 105.0),
            ("upper-right", 44.9, 40.0, 90.0), ("lower-right", 328.1, 45.0, 110.0))

_GEOM = {}


def geometry(shape):
    """r, theta and ridge distance for a canvas of this shape, memoised."""
    key = tuple(shape[:2])
    if key in _GEOM:
        return _GEOM[key]
    h, w = key
    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx - CORE[0]
    dy = yy - CORE[1]
    r = np.hypot(dx, dy)
    th = np.degrees(np.arctan2(-dy, dx)) % 360.0
    dmin = np.full((h, w), 1e9)
    for _side, (ax, ay, rx, ry) in ARCS.items():
        u, v = (xx - ax) / rx, (yy - ay) / ry
        rr = np.sqrt(u * u + v * v)
        d = np.abs((rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6))
        dmin = np.minimum(dmin, d)
    out = (dx, dy, r, th, dmin)
    _GEOM[key] = out
    return out


def _mean(a, m, floor=40):
    return float(a[m].mean()) if m.sum() >= floor else None


def _ratio(rec_v, ref_v, lo, hi, floor):
    """The render's statistic as a fraction of the reference's -- three outcomes.

    `floor` is the smallest reference value this statistic can be trusted at.
    Below it the ratio is two noise numbers divided by each other and will swing
    wildly for reasons that have nothing to do with the artwork -- the
    lower-right ray reads -0.18 in the REFERENCE at r 55-105, because the right
    ridge deletes most of that annulus, and dividing by it produced a confident
    "4.13x" out of nothing.  A check whose reference signal is below its own
    floor has nothing to test and says so.

    The two ways a statistic can come back None are NOT the same thing, and
    collapsing them is how a suite built to catch vanished structure let
    vanished structure through.  A None on the REFERENCE side means the source
    image cannot establish the structure, so there is nothing to hold the render
    to: skip, and that is a pass.  A None on the RENDER side, when the reference
    is measurable, means the opposite -- every candidate-side gate here
    (`near - base < 1.0` in `line_skirt`, the `_mean` population floors) goes
    false precisely BECAUSE the structure is not there.  Measured: against an
    all-black candidate, `west_flatness` and `line_skirt` both returned None and
    both were reported "NOT MEASURABLE", so 8 of 12 checks failed where 10
    should have.  That is now a failure, and the caller is told which kind it is
    rather than being handed a None to format as a number.

    Returns (ratio, lo, hi, measurable).  `ratio` is None in both unmeasurable
    cases; `measurable` is what separates them.
    """
    if ref_v is None or abs(ref_v) < floor:
        return None, lo, hi, True
    if rec_v is None:
        return None, lo, hi, False
    return rec_v / ref_v, lo, hi, True


# --------------------------------------------------------------------------- #
# 1. the westward region must not be a filled slab
# --------------------------------------------------------------------------- #
def west_flatness(a):
    """How FLAT the west field's transverse profile is at |dx| 84-130.

    The defect this exists for is a quadrilateral: a `ray` primitive wide enough
    to cover the west field puts the same value at every dy inside its edges,
    which is 1.00 on this statistic, and then falls off a cliff.  The reference
    is peaked there, so it reads well under 1.

    Each image is measured against ITS OWN light far from the flare's row, so
    the statistic is a shape and neither image's absolute level enters.
    """
    dx, dy, _r, _th, dmin = geometry(a.shape)
    v = a.mean(2)
    band = (dx <= -84) & (dx > -130) & (dmin > 20)
    base = _mean(v, band & (np.abs(dy) >= 100) & (np.abs(dy) < 150))
    near = _mean(v, band & (np.abs(dy) < 25))
    far = _mean(v, band & (np.abs(dy) >= 55) & (np.abs(dy) < 90))
    if base is None or near is None or far is None or near - base < 1.0:
        return None
    return (far - base) / (near - base)


# --------------------------------------------------------------------------- #
# 2. the vertical diffraction structure must stay present
# --------------------------------------------------------------------------- #
def vertical_amplitude(a):
    """Column high-pass amplitude of the vertical line, in R, NORTH of the core.

    R because G and B are clipped within ~12 px of the core, which is what hid
    this structure for four iterations: through mean(RGB) it is nearly invisible.
    N = (4*A_2 - A_4)/3 cancels any background quadratic in x over +-4 px.

    NORTH ONLY, and the first version of this pooled both sides -- which is the
    very fault that had just been found in tools/vstreak_report.py and fixed
    there.  The reference's line is north-dominated (south/north 0.44 in B, 0.63
    in R), so correcting the model's south_gain from 1.0 to 0.55 LOWERS a pooled
    statistic and a pooled check would have read that correction as a 12% loss of
    structure.  A guard that cannot see an asymmetry will argue against fixing
    one; writing this check before fixing the tool would have baked the same
    blindness into the regression suite.

    AND THIS CHECK NOW HAS THE SAME BLINDNESS ONE LEVEL DOWN, which is recorded
    here rather than quietly lived with.  It pools |dy| 16-50, and across that
    span the render is too BRIGHT inside 36 and too DIM outside it -- A_4 12.31
    and 9.79 against the reference's 10.57 and 8.26 over 16-26 and 26-36, then
    4.50 and 2.14 against 5.74 and 2.66 over 36-50 and 50-70.  The two errors
    partly cancel, so the pooled ratio of 0.561 is flattered by the inner excess:
    correcting the northern falloff improves every band (tools/vstreak_report.py
    rms 1.76 -> 1.16) and LOWERS this number to about 0.55.  Until this is split
    per band, a fall here is not by itself evidence that the line got weaker, and
    `flare_vline`'s note says why its north was left alone.
    """
    _dx, dy, _r, _th, dmin = geometry(a.shape)
    R = a[..., 0]
    rows = (dy[:, 0] <= -16) & (dy[:, 0] > -50)
    x0 = int(round(CORE[0]))
    out = []
    for k in (2, 4):
        col = R[rows, x0] - 0.5 * (R[rows, x0 - k] + R[rows, x0 + k])
        ok = dmin[rows, x0] > 12
        out.append(col[ok].mean() if ok.sum() >= 10 else np.nan)
    if not np.all(np.isfinite(out)):
        return None
    return float((4 * out[0] - out[1]) / 3.0)


# --------------------------------------------------------------------------- #
# 3. the lower horizontal features must stay represented
# --------------------------------------------------------------------------- #
def line_amplitudes(a):
    """Transverse high-pass amplitude at each of the three measured line rows.

    dy 0, +7 and +18: line A on the core row, the short east-heavy B, and the
    faint long C.  A 3-tap transverse high-pass at the row itself, pooled over
    the |dx| windows where each line is measurable at all.
    """
    dx, dy, _r, _th, dmin = geometry(a.shape)
    v = a.mean(2)
    hp = v - 0.5 * (np.roll(v, 4, axis=0) + np.roll(v, -4, axis=0))
    out = {}
    for name, row, (xa, xb) in (("A", 0, (45, 260)), ("B", 7, (45, 105)), ("C", 18, (80, 260))):
        m = (np.abs(dy - row) < 1.0) & (np.abs(dx) >= xa) & (np.abs(dx) < xb) & (dmin > 26)
        out[name] = _mean(hp, m, floor=30)
    return out


def line_skirt(a):
    """Share of the horizontal line's light that lies OUTSIDE its narrow core.

    The standing complaint is "too thin, too hard, isolated", and the thing that
    makes a line read that way is a missing broad component rather than a wrong
    core width.  Measured on the north flank only, which is free of lines B and
    C, over the east band where the reference's own signal clears its null.
    """
    dx, dy, _r, _th, dmin = geometry(a.shape)
    v = a.mean(2)
    band = (np.abs(dx) >= 80) & (np.abs(dx) < 190) & (dmin > 26)
    base = _mean(v, band & (dy <= -34) & (dy > -46))
    core = _mean(v, band & (np.abs(dy) < 3))
    flank = _mean(v, band & (dy <= -5) & (dy > -18))
    if None in (base, core, flank) or core - base < 1.0:
        return None
    return (flank - base) / (core - base)


# --------------------------------------------------------------------------- #
# 4. the four rays must stay present
# --------------------------------------------------------------------------- #
def ray_excess(a, theta, r0=55.0, r1=105.0, half=6.0, gap=(11.0, 20.0)):
    """A ray's brightness above the MEDIAN of its own annulus.

    The first version of this compared the axis with two windows 14-26 degrees
    to either side, and that was wrong in a way worth recording: the lower-left
    ray sits 10 degrees from the lower-left flank's peak and the upper-left ray
    sits inside its own flank, so for two of the four the "background" window
    held another structure and the statistic came out NEGATIVE -- the reference
    reading darker on the ray than beside it.  A ratio of two negative numbers
    is not a presence test.

    The annulus median is not the fix either, and the second attempt is worth
    recording too: this field is strongly anisotropic -- the horizontal axis is
    far brighter than the diagonals -- so the ring median sits ABOVE the left
    rays and both images then read negative.  A statistic that is negative for
    the reference is measuring the field, not the ray.

    What works is the QUIETER of the two flanking windows.  A neighbouring
    structure raises one side, so taking the smaller of the two means the ray is
    compared with whichever side is actually empty.  The ray only has to stand
    above the quieter side, which is the weakest statement that still amounts to
    "there is a directional structure here".
    """
    _dx, _dy, r, th, dmin = geometry(a.shape)
    v = a.mean(2)
    d = (th - theta + 180.0) % 360.0 - 180.0
    ring = (r >= r0) & (r < r1) & (dmin > 20)
    on = _mean(v, ring & (np.abs(d) < half))
    lo_side = _mean(v, ring & (d >= gap[0]) & (d < gap[1]))
    hi_side = _mean(v, ring & (d <= -gap[0]) & (d > -gap[1]))
    sides = [q for q in (lo_side, hi_side) if q is not None]
    if on is None or not sides:
        return None
    return on - min(sides)


#: Rays that do NOT pass through the core, and the one short lobe that must stay
#: short, each on the line measured for it in the reference by a 2D centreline
#: fit (per-band Gaussian + line across the ray, then a weighted TLS line through
#: the fitted centres).  (name, foot, direction, L0, L1, half-width): `foot` is a
#: point on the line in canvas coordinates (pixel i spans [i, i+1]), the
#: direction is counter-clockwise from east with y up, and L0-L1 is the stretch
#: of the line, measured from the foot, where that structure is the one being
#: read.
#:
#: `ray_excess` cannot see the upper-left pair, and that is why these exist: it
#: samples a wedge about the CORE, and the pair misses the core by 17 and 26 px.
#: The previous release, which drew nothing at 140-150 degrees at all, scored
#: 7.50 there against the reference's 6.63 -- a presence test that a missing
#: structure passes.  Following the measured line and comparing it with its own
#: flanks reads 6.13 for the reference and 0.06 for that release, and a line
#: rotated 10 degrees either way reads -2.4 to +1.5 on the reference.
LINE_AXES = (("lower-left", (524.2, 511.7), 255.2, 50.0, 110.0, 12.0),
             ("upper-left A", (519.9, 526.9), 140.4, 115.0, 195.0, 14.0),
             ("upper-left B", (518.0, 535.6), 150.0, 90.0, 150.0, 14.0),
             ("upper-right core", (534.8, 517.0), 47.6, 70.0, 140.0, 14.0),
             ("lower-left lobe", (531.0, 513.5), 231.0, 36.0, 66.0, 12.0))


def _bilinear(a, x, y):
    """Bilinear sample of a 2-D array at float pixel-index coordinates."""
    h, w = a.shape[:2]
    x0 = np.clip(np.floor(x).astype(int), 0, w - 1)
    y0 = np.clip(np.floor(y).astype(int), 0, h - 1)
    x1, y1 = np.clip(x0 + 1, 0, w - 1), np.clip(y0 + 1, 0, h - 1)
    fx, fy = x - x0, y - y0
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def line_peak(a, foot, theta, L0, L1, hw=14.0):
    """Mean over L0..L1 of the transverse G peak within 4 px of a measured line.

    Each 10 px stretch of the line is averaged along its length, a straight
    line fitted to the outer 4 px of each flank is removed (the local ramp of
    the curves' glow), and the largest remaining value within |s| <= 4 is the
    stretch's reading.  G is the carrier: every ray here is cyan.
    """
    g = a[..., 1]
    t = np.radians(theta)
    ux, uy, nx, ny = np.cos(t), -np.sin(t), -np.sin(t), -np.cos(t)
    s = np.arange(-hw, hw + 0.01, 1.0)
    edge, inner = np.abs(s) >= hw - 4, np.abs(s) <= 4
    vals = []
    for L in np.arange(L0, L1, 10.0):
        r = np.arange(L, L + 10.0, 0.5)
        xs = foot[0] + r[:, None] * ux + s[None, :] * nx - 0.5
        ys = foot[1] + r[:, None] * uy + s[None, :] * ny - 0.5
        v = _bilinear(g, xs, ys).mean(0)
        c = np.polyfit(s[edge], v[edge], 1)
        vals.append(float((v - np.polyval(c, s))[inner].max()))
    return float(np.mean(vals))


# --------------------------------------------------------------------------- #
# 5. the core must not become an oversized white mass
# --------------------------------------------------------------------------- #
def white_radius(a, thresh=230.0):
    """Equivalent radius of the truly-white region, min(R,G,B) >= thresh.

    min() and not the mean: a pixel is white only if every channel is high, so
    this cannot be satisfied by a bright cyan.
    """
    _dx, _dy, r, _th, dmin = geometry(a.shape)
    m = (a.min(2) >= thresh) & (r < 45) & (dmin > 8)
    return float(np.sqrt(m.sum() / np.pi))


# --------------------------------------------------------------------------- #
# 6. the flare must not drift back towards a white wash
# --------------------------------------------------------------------------- #
def cyan_fraction(a):
    """How much of the mid-radius bloom's light is cyan rather than white.

    In this colour model white is the only red-carrying primary, so 1 - R/G is
    a direct readout of the cyan share at a given place.  Measured in the
    annulus r 20-55 away from the horizontal axis, which is where the render's
    surround has repeatedly gone white.
    """
    _dx, _dy, r, th, dmin = geometry(a.shape)
    m = ((r >= 20) & (r < 55) & (dmin > 8) & (a.max(2) < 250)
         & (((th > 60) & (th < 120)) | ((th > 240) & (th < 300))))
    if m.sum() < 60:
        return None
    R, G = a[..., 0][m].mean(), a[..., 1][m].mean()
    return float(1.0 - R / max(G, 1e-6))


# --------------------------------------------------------------------------- #
#: name, statistic, (lo, hi) on render/reference, the reference floor below
#: which the statistic cannot be trusted, and what a failure would mean.
#: The floors are in the statistic's own units: code values for the line, ray
#: and vertical amplitudes, dimensionless for the three shape ratios.
CHECKS = (
    ("west field is not a filled slab", "west_flatness", (0.55, 1.15), 0.05,
     "the west field's transverse profile is the wrong shape: above the band it "
     "has gone FLAT, which is what a wide quadrilateral looks like and what "
     "reads as a triangular region; below it the west structure has gone"),
    # 0.58 of the reference on the current artwork, and that is NOT read as a
    # deficit: re-compressing test renders at q 88-96 moves this statistic by
    # x1.17-1.27 in R, which is the same size as the shortfall, so the line's
    # absolute amplitude is not recoverable from this image.  The band is set
    # around where it sits, and the ratio between the two SIDES -- which is
    # immune to that systematic -- is what the artwork was actually fitted to.
    ("the vertical diffraction is present", "vertical", (0.45, 2.20), 0.8,
     "the vertical line through the core has faded or been over-driven"),
    ("line A is present", "lineA", (0.45, 2.00), 1.0, "the core-row line has faded"),
    ("line B is present", "lineB", (0.35, 2.40), 1.0, "the short secondary line has faded"),
    ("line C is present", "lineC", (0.25, 3.00), 0.5, "the faint long line has faded"),
    ("the horizontal line keeps its skirt", "skirt", (0.50, 1.80), 0.05,
     "the line has become a hard isolated stroke without its broad component"),
    ("upper-left ray is present", "ray upper-left", (0.40, 2.20), 1.0,
     "a ray has been smoothed away"),
    # Read on its measured line (LINE_AXES), not on a wedge about the core --
    # see the note above RAY_AXES.  Reference 9.52; lines rotated 10 degrees
    # either way read -2.7 and -5.2 on the reference.
    ("lower-left ray is present", "line lower-left", (0.40, 2.20), 1.0,
     "a ray has been smoothed away"),
    # The band's floor is set where the CURRENT artwork sits, not where it
    # ought to: on the shipped render the upper-right ray measures 0.49 of the
    # reference and the lower-right 0.76, so these two still guard a structure
    # that is known to be too weak.  That is recorded here rather than hidden in
    # a comfortable band, and the floor's job is only to stop it getting worse.
    # Both were 0.36 and 0.61 two iterations ago and were improved by being
    # widened rather than brightened -- the error is transverse distribution, not
    # amplitude.  The numbers moved again afterwards and these comments did not,
    # which is why they now name the reading they were written against: the
    # upper-right lost 0.05 to re-centring flare_halo (the statistic subtracts
    # the quieter flank, and the shift raises the background east) while no ray
    # parameter changed, and the lower-right gained 0.10 from the same pass.
    # The floors are deliberately NOT retightened onto 0.49/0.76 -- 0.45 leaves
    # the upper-right only 0.04 of margin as it is.
    # D61: both now read 0.95 and 0.91 of the reference, because both rays were
    # rebuilt as a narrow core plus a soft flank on their measured lines.  The
    # floors stay where they were: a floor is a guard against loss, and raising
    # it to meet the artwork would make the next honest refit look like one.
    ("upper-right ray is present", "ray upper-right", (0.45, 2.20), 1.0,
     "a ray has been smoothed away (this one is already 0.49 of the reference)"),
    ("lower-right ray is present", "ray lower-right", (0.55, 2.20), 1.0,
     "a ray has been smoothed away (this one is already 0.76 of the reference)"),
    # The line-following checks (LINE_AXES).  The pair and the upper-right core
    # were ABSENT from the release before these were written -- 0.01, -0.01 and
    # 0.46 of the reference -- so the floors are real presence floors, not
    # where the artwork happened to sit.  The lower-left lobe is the opposite
    # failure: a fit once drew it 2.3x the reference as a long blue ray, which
    # is an invented structure, so its ceiling matters as much as its floor.
    ("the upper-left ray A is present", "line upper-left A", (0.50, 2.00), 1.0,
     "the outer of the two upper-left rays, off the core, has gone"),
    ("the upper-left ray B is present", "line upper-left B", (0.50, 2.00), 1.0,
     "the inner of the two upper-left rays, off the core, has gone"),
    ("the upper-right ray keeps its sharp core", "line upper-right core", (0.50, 2.00), 1.0,
     "the upper-right ray is back to a soft slab without its narrow core"),
    # Read at 231 degrees, between the reference's lobe (peak 226-229) and
    # where the over-drawn ray sat (235): the reference reads 5.50, the release
    # without the lobe 0.22x and the over-drawn ray 2.47x.
    ("the lower-left lobe is short, not a long ray", "line lower-left lobe", (0.45, 1.80), 1.0,
     "the short lower-left lobe has vanished (below) or been drawn as a long "
     "over-bright ray (above)"),
    ("the white core is not oversized", "white radius", (0.0, 1.35), 0.5,
     "the compact white region has grown into a blob"),
    ("the bloom has not gone white", "cyan fraction", (0.90, 1.12), 0.05,
     "the mid-radius surround has drifted back towards a white wash"),
)


def statistics(a):
    """Every structural statistic for one image, by the name CHECKS uses."""
    out = {"west_flatness": west_flatness(a),
           "vertical": vertical_amplitude(a),
           "skirt": line_skirt(a),
           "white radius": white_radius(a),
           "cyan fraction": cyan_fraction(a)}
    for k, v in line_amplitudes(a).items():
        out["line" + k] = v
    for name, theta, r0, r1 in RAY_AXES:
        out["ray " + name] = ray_excess(a, theta, r0, r1)
    for name, foot, theta, L0, L1, hw in LINE_AXES:
        out["line " + name] = line_peak(a, foot, theta, L0, L1, hw)
    return out


def report(ref, rec):
    """[(name, ratio, lo, hi, ok, ref_value, rec_value, meaning), ...].

    `ratio is None and ok` is a genuine skip: the reference cannot establish the
    structure.  `ratio is None and not ok` is the structure being absent from the
    render while the reference has it.  Both leave `ratio` unformattable, so a
    caller printing failures must handle None.
    """
    sref, srec = statistics(ref), statistics(rec)
    rows = []
    for name, key, (lo, hi), floor, meaning in CHECKS:
        ratio, lo, hi, measurable = _ratio(srec.get(key), sref.get(key), lo, hi, floor)
        ok = measurable if ratio is None else (lo <= ratio <= hi)
        rows.append((name, ratio, lo, hi, ok, sref.get(key), srec.get(key), meaning))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("render")
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    a = ap.parse_args()
    load = lambda p: np.asarray(Image.open(p).convert("RGB")).astype(np.float64)  # noqa: E731
    rows = report(load(a.reference), load(a.render))
    bad = 0
    print("%-38s %9s %9s %16s  %s" % ("structure", "reference", "render", "render/ref", ""))
    for name, ratio, lo, hi, ok, rv, cv, _meaning in rows:
        if ratio is None:
            bad += not ok
            print("%-38s %9s %9s %16s  %s"
                  % (name, "%.4g" % rv if rv is not None else "-",
                     "%.4g" % cv if cv is not None else "-", "-",
                     "NOT MEASURABLE" if ok else "MISSING FROM RENDER"))
            continue
        bad += not ok
        print("%-38s %9.4g %9.4g %8.3f [%.2f,%.2f]  %s"
              % (name, rv, cv, ratio, lo, hi, "ok" if ok else "FAIL"))
    print()
    print("%d of %d structural checks failed" % (bad, len(rows)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
