#!/usr/bin/env python3
"""Set the flare's rays from measurement rather than from the fit.

    python3 tools/measure_flare.py [--params src/params.json] [--geometry] [--rounds N]

Two jobs, and the second is the one that has to be repeated whenever anything
under the flare changes:

  * `--geometry` writes the GEOMETRY OF RECORD (RAY_GEOMETRY below) into every
    ray layer: direction, origin offset, length, longitudinal profile and
    transverse width.  Every layer of kind `ray` has an entry; a ray layer
    without one is an error, not something to leave where the last search put
    it.  It writes values and nothing else: a layer's `bounds` are its SEARCH
    space, a different thing from its measured geometry, and are never
    rewritten here (D62).

  * always, the amplitudes -- calibrated against each ray's measured PROFILE,
    not a pooled peak.  A visible ray is often several layers: the lower-left
    ray is an inner and an outer segment on one line, the upper-right ray a
    narrow core inside a soft flank, the lower-right ray a bright inner segment
    and a long tail.  So the unit of calibration is a FAMILY (FAMILIES below):
    one measured line plus every layer that puts light on it.  Each family is
    read band by band along its line with the reference's own transverse
    template held fixed (tools/ray_lines.py), which makes every band's amplitude
    a linear functional of the image; all families' per-layer scale factors are
    then solved JOINTLY by least squares through an exact composite of the
    layer stack.  Each layer's scale moves only the part of the profile that
    layer controls, so fixing an inner segment cannot drag an outer one with it.

Screen compositing is not linear in a layer's amplitude -- a ray over a
background of luminance b contributes about (1 - b) of what it would over black
-- and the composite is solved exactly rather than linearised, then the saved
parameters are RE-RENDERED in full and re-measured.  Converged means the
correction that re-measurement asks for is within TOL of 1 for every calibrated
layer.  The exit status is 1 otherwise, and the corrections computed on the way
are saved either way.

Why the amplitudes are not left to `tools/fit_photometry.py`: that objective is
a weighted error over the whole image, and a ray is a few code values over a few
hundred pixels.  The global fit moves light into rays that belongs to a broad
glow, because the rays are the levers it has (D61 caught it drawing a lower-left
ray 2.5x the reference).  So fit_photometry and optimize.py HOLD the calibrated
layers (CALIBRATED_LAYERS) by default, and the intended order is: shapes and
photometry of everything else, then `--geometry`, then this calibration --
which is what tools/optimize_all.sh runs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
import ray_lines as RL  # noqa: E402

#: The geometry keys of a `ray` layer, in the builder's terms.  `rot` is the
#: SVG rotation (the direction is -rot, degrees counter-clockwise from east);
#: `dx`/`dy` put the ray's ORIGIN relative to the flare centre -- the ray runs
#: from there along its direction; `len` is its length from the origin; `onset`,
#: `peak_at` and `tail` place the longitudinal profile as fractions of `len` (0
#: before `onset`, 1.0 at `peak_at`, 0.42 at peak_at + tail, 0 at the end);
#: `height` is the near-end width, `spread` the far end's width as a multiple of
#: it, and `blur` the Gaussian softening of both.  None means "absent from the
#: layer": the builder's default (0 for dx/dy/onset, 0.35 for tail) applies,
#: and the key is removed so the params stay as small as the model is.
GEOMETRY_KEYS = ("rot", "dx", "dy", "len", "onset", "peak_at", "tail", "height", "spread", "blur")

#: THE GEOMETRY OF RECORD, for every ray layer in the model.  `--geometry`
#: writes it into the params, so a stale entry silently reverts shipped work --
#: and did: this table once held 45.6/215 and 327.8/185 for the right pair after
#: both had been superseded.  `tools/test_pipeline.py` asserts that this table
#: and `src/params.json` agree for every key of every ray, that every ray layer
#: has an entry, and that a deliberately displaced ray comes back.
#:
#: Until D62 only the original four rays were here and the table held a
#: measured FWHM from which the blur was derived.  The nine rays added in D61
#: were not, so a geometry rebuild restored four rays and left nine wherever the
#: last shape search had put them.  Every entry now stores `blur` directly: the
#: FWHM was never the quantity that round-tripped (see the upper-right note).
#:
#: The angles carry real uncertainty and are NOT known to the decimal place
#: printed.  The reference's rays are asymmetric and six reasonable definitions
#: of "centre" disagree by 1.2-1.7 px, so no axis here is defined to better than
#: about a degree.  The values below are the centre of the supported range.
RAY_GEOMETRY = {
    # Upper-left inner ray.  The reference's ray is NOT parallel to a ray from
    # the core: over 39 estimator variants the transverse centre difference fits
    # Delta = a + b*r with b = -3.7 to -8.9 deg and a = +1.8 to +7.6 px; a and b
    # are strongly anti-correlated, so the defensible statement is the Delta(r)
    # curve, not either alone.  The rotation is here and the +5.22 px normal
    # offset is dx/dy.  height 12 -> 9 because beyond r 70 the ray carried
    # 1.8-3.0x too much light (D38).  Its LONGITUDINAL profile is D62's: the
    # reference peaks at r ~60 (G 22.7), is 0.42 of that by r ~90 and fades
    # slowly to ~0 by r ~125 (G 7.0 / 5.3 / 3.7 / 1.9 at r 92-116); the old
    # len 100 with the fixed 0.35 fade dropped from 0.42 to nothing between
    # r 97 and 100.  Fitted to the line-following amplitudes with the
    # reference's own templates: peak 54 px, 0.42-point 89 px, end 148 px.
    "flare_ray_a": dict(rot=-107.1, dx=-4.783, dy=2.09,
                        len=148.0, onset=None, peak_at=0.3649, tail=0.2365,
                        height=9.0, spread=1.0, blur=4.5309),
    # Upper-left pair (D61).  Neither passes through the core: per-band ridge
    # centres fit lines at 140.4 deg through (519.9, 526.9) and 149.5 deg
    # through (518.0, 535.6), 17 and 26 px from the core; both are visible only
    # beyond the left curve.  A is narrow (FWHM 6-11 px), B fainter.  B was
    # drawn broad (height 10, blur 4.0: sigma 5.3-5.9 px on its line), but
    # beyond r 104, where its line is clear of the curve's glow, the
    # reference's sigma is 3.6-4.1 in every band; the broad reading comes from
    # r 84-100, 20-30 px off the curve's ridge.  Too wide a ray reads low
    # through a fixed template and is calibrated too BRIGHT to compensate --
    # it came out 1.5x the reference's peak -- so D62 gives B the measured
    # width (height 6, blur 3.2: sigma 3.5-4.0).
    "flare_ray_ula": dict(rot=-140.4, dx=-10.05, dy=12.57,
                          len=215.0, onset=0.42, peak_at=0.65, tail=None,
                          height=4.0, spread=1.0, blur=2.8),
    "flare_ray_ulb": dict(rot=-149.5, dx=-11.95, dy=21.27,
                          len=175.0, onset=0.35, peak_at=0.55, tail=None,
                          height=6.0, spread=1.0, blur=3.2),
    # Lower-left ray, on its measured line: 255.2 deg through (524.2, 511.7),
    # 7.0 px from the core, the reference's ridge within +-1.5 px of the line in
    # every band from r 40 to 128.  Its profile along the line is a plateau
    # (G 11.1-12.2 at r 56-64, 9.5-11.2 at r 72-104, 4.5 by r 112), which one
    # single-peaked gradient cannot hold, so it is two segments on the same line.
    "flare_ray_b": dict(rot=-255.2, dx=-5.75, dy=-2.63, len=95.4483, onset=0.4463, peak_at=0.4011, tail=None,
                        height=9.4638, spread=1.25, blur=2.4209),
    "flare_ray_b2": dict(rot=-255.2, dx=-5.75, dy=-2.63, len=133.3837, onset=0.4049, peak_at=0.7294, tail=None,
                         height=9.4638, spread=1.0, blur=2.4209),
    # The short lower-left lobe at 229 deg (D61), through the core, broad
    # (sigma 4.3-6.1 px).  D62 splits it by COLOUR along its length, because
    # one layer has one colour: the reference is WHITE at r 24-40 (R 11.0,
    # 19.2, 7.5 at r 24/32/40, ~0 by r 48) and CYAN at r 32-56 (G 13.4, 13.2,
    # 10.5 at r 32/40/48), and gone by r ~60 -- the single white+cyan layer put
    # white along the whole lobe (R 5-6 at r 40-56) and ran ~10 px too long
    # (G 12.1 / 7.4 at r 56/64 against 4.9 / 0.2).  Same line, same width:
    # llc_in is the white near-core part, llc the cyan lobe and its fade.
    "flare_ray_llc_in": dict(rot=-229.0, dx=1.05, dy=-0.83,
                             len=46.0, onset=0.5, peak_at=0.6504, tail=0.153,
                             height=5.6348, spread=1.0, blur=5.0159),
    "flare_ray_llc": dict(rot=-229.0, dx=1.05, dy=-0.83,
                          len=60.9874, onset=0.5636, peak_at=0.6691, tail=0.1057,
                          height=5.6348, spread=1.0, blur=5.0159),
    # The 267-degree lower-left ray (D61): two maxima on one line, G 11.8 at
    # r 44 and 7.6 at r 92 with a dip to 3.4 between -- two segments.
    "flare_ray_lld": dict(rot=-265.5, dx=1.05, dy=-0.83, len=69.7979, onset=0.3729, peak_at=0.6011, tail=None,
                          height=8.0, spread=1.0, blur=2.8),
    "flare_ray_lld2": dict(rot=-266.5, dx=1.05, dy=-0.83, len=123.8089, onset=0.5074, peak_at=0.7073, tail=None,
                           height=3.1354, spread=1.0, blur=2.4),
    # Upper-right SOFT FLANK.  Axis 44.9 +- 0.4 (45.6 is excluded at ~6 sigma);
    # ends at r = 140 +- 15.  height 8 -> 26, spread 1.30 -> 1.00, len 150 -> 143
    # and a 5.4 px normal offset are a JOINT correction (D59): each alone is
    # worse than what it replaced.  A half-maximum is not a stable quantity in
    # this corridor (10.55 / 15.06 / 1.41 px over adjacent 20 px bands), which is
    # why the table no longer stores a "measured FWHM" for it.
    "flare_ray_e": dict(rot=-44.9, dx=-3.8117, dy=-3.825, len=143.0, onset=None, peak_at=0.28, tail=None,
                        height=26.0, spread=1.0, blur=3.5634),
    # Upper-right NARROW CORE (D61), on its own measured line: 47.6 deg,
    # 5.2 px off the core; width sigma 3.3-4.8 px in the reference.  D62: the
    # reference holds G ~7 from r 74 to 98 and is down to 4.5 by r 106; the
    # core's fade (0.42 at 146 px of 151) kept light at r 110-140 that belongs
    # at r 90-98.  Its onset and fade are re-fitted, not its amplitude alone:
    # onset 28 -> 46 px, 0.42-point 146 -> 106 px, peak and end unchanged.
    "flare_ray_ur": dict(rot=-47.6, dx=4.85, dy=2.67,
                         len=150.8106, onset=0.3036, peak_at=0.6192, tail=0.0848,
                         height=1.8314, spread=1.0, blur=2.4929),
    # Lower-right TAIL.  Direction 327.3-328.1 and NOT resolvable further: a
    # transverse-position matched filter prefers 327.2-327.5, corridor pixel
    # error 327.8-328.1.  The ~3 px dx/dy TRANSLATION is confirmed and must not
    # be turned back into a rotation: removing it costs +0.42 corridor MAE and a
    # rotation over-corrects inside r 70 and under-corrects beyond r 150,
    # because the measured offset is constant in pixels, not in degrees.  Its
    # measured extent is 165 +- 20 (a candidate at 215 was reverted in D61).
    # D62 re-checked the translation at near/mid/far radius: the reference's
    # ridge sits +0.45 / -0.95 / -1.15 px from this line at r 36-60 / 68-124 /
    # 132-172 -- flat beyond r 68, which a rotation cannot produce, and within
    # the 1.2-1.7 px spread of "centre" definitions -- so it stays.  D62 moved
    # the tail's light, not its line: the reference is 12-15 cv at r 60-84 and
    # down to 3.6 by r 132, where the old fade (peak 53 px, 0.42 at 116 px)
    # was 2-4 cv low inside r 84 and 1-2 cv high at r 108-132.
    "flare_ray_c": dict(rot=-328.1, dx=1.5809, dy=-2.5497,
                        len=177.2975, onset=None, peak_at=0.389, tail=0.1735,
                        height=5.4845, spread=2.1988, blur=3.0915),
    # Lower-right bright INNER segment on the same line (D61): the reference is
    # brightest and white next to the core (G 17.8, R 12.6 at r 44) and its
    # white is gone by r 52 (R 3.0), where the segment still gave R 9.6 (D62:
    # peak 30 -> 42 px, 0.42-point 54 -> 50 px).
    "flare_ray_c_in": dict(rot=-328.1, dx=1.58, dy=-2.55,
                           len=64.1046, onset=None, peak_at=0.6621, tail=0.1113,
                           height=6.5097, spread=1.0, blur=1.5175),
}

#: Layers removed in D61 and named in the record of their removal: two
#: straight-edged quadrilaterals fanning out of the core that together drew the
#: false triangle west of it.  `--geometry` used to RE-INSERT them from a
#: template; a retired id found in the params is now an error.
RETIRED_FLANKS = ("flare_flank_dl", "flare_flank_ul")

#: Calibration families: each measured line (tools/ray_lines.py LINES) and
#: EVERY layer that puts light on it.  A family's layers are solved jointly with
#: all the others, each with its own scale, so a family's relative profile --
#: what the segments were fitted to -- is kept and only corrected where the
#: measurement asks.  `broad` adds the mean transverse profile over L0..L1 at
#: half-width hw, which is what determines a soft flank that the narrow line
#: template mostly removes as ramp (the upper-right slab).  `r_min` drops the
#: bands nearer the line's foot than that: both upper-left lines cross the
#: left curve's ridge at r ~64-73 and their first bands lie 20-36 px beyond
#: it, inside the curve's glow, where the CURVE model's error reads as a
#: negative ray -- -3.5 and -4.6 cv at r 104 and 84 against +2.3 and +2.9 in
#: the reference -- and a solve that saw them brightened the ray to fill a dip
#: that is not the ray's (D62).
FAMILIES = {
    "upper-left inner": {"line": "upper-left inner", "layers": ("flare_ray_a",)},
    "upper-left A": {"line": "upper-left A", "layers": ("flare_ray_ula",), "r_min": 108.0},
    "upper-left B": {"line": "upper-left B", "layers": ("flare_ray_ulb",), "r_min": 104.0},
    "lower-left lobe": {"line": "lower-left 229", "layers": ("flare_ray_llc_in", "flare_ray_llc")},
    "lower-left": {"line": "lower-left", "layers": ("flare_ray_b", "flare_ray_b2")},
    "lower-left 268": {"line": "lower-left 268", "layers": ("flare_ray_lld", "flare_ray_lld2")},
    "upper-right": {"line": "upper-right", "layers": ("flare_ray_ur", "flare_ray_e"),
                    "broad": (60.0, 140.0, 30.0)},
    "lower-right": {"line": "lower-right", "layers": ("flare_ray_c_in", "flare_ray_c")},
}
CALIBRATED_LAYERS = tuple(dict.fromkeys(lid for f in FAMILIES.values() for lid in f["layers"]))

#: |ln(correction)| per layer below which the layer counts as calibrated.
TOL = 0.08
#: One round moves a layer by at most this factor either way, so a gross
#: deficit takes several verified rounds rather than one unverified jump.
ROUND_GAIN = 3.0
#: What a band's residual weighs.  A calibrated layer's scale keeps its hue,
#: so the one thing a scale can get right is the AMOUNT of light, and the amount
#: the eye reads is luminance (Rec. 709 weights).  Several of the reference's
#: rays are greener than the white/cyan/blue cone can draw -- B below G above
#: the local ramp, on the 267-degree ray, both upper-left rays and the
#: upper-right one -- and a residual that weighed G and B equally (R at half)
#: split that hue error by DIMMING those rays: after a converged solve their
#: luminance was 13-26% short of the reference's (D62).  Chroma still enters,
#: at CHROMA_WEIGHT, as the white-vs-green (R - G) and blue-vs-green (B - G)
#: differences: that is what tells a white segment from a cyan one when both
#: light the same line.
LUMA = np.array([0.2126, 0.7152, 0.0722])
CHROMA_WEIGHT = 0.3
BAND_WEIGHT = np.array([LUMA,
                        CHROMA_WEIGHT * np.array([1.0, -1.0, 0.0]),
                        CHROMA_WEIGHT * np.array([0.0, -1.0, 1.0])])
#: The broad term is a G profile; LUMA[1] puts it in luminance units.
BROAD_WEIGHT = 0.5
CHANNELS = ("white", "cyan", "blue")


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def geometry_problems(params):
    """Everything that stops the table above from being the model's geometry.

    Returns a list of strings: a ray layer without an entry, an entry without a
    layer, a key outside GEOMETRY_KEYS, and a canonical value outside the
    layer's own search bounds (which the optimiser would clip on its first
    trial, silently moving the ray off its measurement).
    """
    out = []
    rays = {L["id"]: L for L in params["layers"] if L.get("kind") == "ray"}
    for lid in rays:
        if lid not in RAY_GEOMETRY:
            out.append("%s is a ray layer with no geometry of record" % lid)
    for lid, g in RAY_GEOMETRY.items():
        L = rays.get(lid)
        if L is None:
            out.append("%s has geometry of record but no ray layer" % lid)
            continue
        extra = set(g) - set(GEOMETRY_KEYS)
        missing = set(GEOMETRY_KEYS) - set(g)
        if extra or missing:
            out.append("%s geometry keys: extra %s, missing %s" % (lid, sorted(extra), sorted(missing)))
        for k, v in g.items():
            b = L.get("bounds", {}).get(k)
            if v is not None and b is not None and not (b[0] <= v <= b[1]):
                out.append("%s/%s canonical %g outside its search bounds [%g, %g]" % (lid, k, v, b[0], b[1]))
    for L in params["layers"]:
        if L["id"] in RETIRED_FLANKS:
            out.append("retired flank layer %s is present" % L["id"])
    return out


def apply_geometry(params, verbose=True):
    """Write the geometry of record into every ray layer.  Bounds are NOT touched.

    Until D62 this also rewrote each ray's `bounds` to generic wide intervals
    (rot +-6 deg, height 3-40, blur 0.6-10, len -45/+60 ...), which replaced the
    measured narrow intervals a ray had been given -- `flare_ray_b`'s rotation
    window went from +-3 to +-6 degrees and its length window roughly doubled
    on every rebuild.  A search space is a separate decision from a
    measurement; the only thing checked here is that the canonical value lies
    inside it.
    """
    problems = geometry_problems(params)
    if problems:
        raise SystemExit("geometry of record cannot be applied:\n  " + "\n  ".join(problems))
    by_id = {L["id"]: L for L in params["layers"]}
    for lid, g in RAY_GEOMETRY.items():
        L = by_id[lid]
        for k in GEOMETRY_KEYS:
            v = g[k]
            if v is None:
                L.pop(k, None)
            else:
                L[k] = v
        if verbose:
            print("  %-15s direction %6.1f  origin %+7.2f %+7.2f  len %6.1f  h %5.2f blur %4.2f"
                  % (lid, -g["rot"], g["dx"] or 0.0, g["dy"] or 0.0, g["len"], g["height"], g["blur"]))


# --------------------------------------------------------------------------- #
# measurement: fixed linear functionals of the image
# --------------------------------------------------------------------------- #
class Lines:
    """Every family's measurement, built once from the REFERENCE.

    For each band of a family's line whose reference fit is a real measurement
    (not sitting on a bound), the reference's own (s0, sigma) is frozen and the
    band's amplitude becomes `row . v`, with `v` the band-averaged transverse
    profile -- a linear functional of the image, identical for every image it
    is applied to.  The optional broad term is the band-averaged transverse
    profile with each band's ramp removed, also linear.
    """

    def __init__(self, ref):
        RL.check_canvas(ref, "the reference")
        self.fam = {}
        xs_all, ys_all = [], []
        for name, spec in FAMILIES.items():
            foot, d, r0, r1 = RL.LINES[spec["line"]]
            hw = RL.HALF_WIDTH.get(spec["line"], 12.0)
            rows = RL.profile(ref, foot, d, r0, r1, hw=hw)
            bands = []
            for r, _ar, _ag, _ab, s0, sg in rows:
                if abs(s0) >= 3.95 or sg <= 0.85 or sg >= 8.95:
                    continue                   # the reference has no clean ray here
                if r < spec.get("r_min", 0.0):
                    continue                   # inside another structure's glow
                s, xs, ys = RL.band_coords(foot, d, r - 4.0, 8.0, hw)
                bands.append({"r": float(r), "xs": xs, "ys": ys, "row": RL.amplitude_row(s, s0, sg)})
                xs_all.append(xs)
                ys_all.append(ys)
            f = {"bands": bands, "broad": None}
            if "broad" in spec:
                L0, L1, bhw = spec["broad"]
                grids = []
                for L in np.arange(L0, L1, 10.0):
                    s, xs, ys = RL.band_coords(foot, d, L, 10.0, bhw)
                    grids.append((xs, ys))
                    xs_all.append(xs)
                    ys_all.append(ys)
                X = np.stack([np.ones_like(s), s], 1)
                edge = np.abs(s) >= bhw - 4.0
                ramp = X @ np.linalg.pinv(X[edge])          # (n_s, n_edge)
                M = np.eye(len(s))
                M[:, edge] -= ramp
                keep = np.arange(0, len(s), 4)             # every 2 px
                f["broad"] = {"grids": grids, "M": M[keep]}
            self.fam[name] = f
        xa = np.concatenate([x.ravel() for x in xs_all])
        ya = np.concatenate([y.ravel() for y in ys_all])
        # The crop every measurement reads: compositing only this window is what
        # makes a joint solve over the whole stack fast enough to iterate.
        self.box = (int(max(0, math.floor(ya.min()) - 2)), int(min(1024, math.ceil(ya.max()) + 3)),
                    int(max(0, math.floor(xa.min()) - 2)), int(min(1024, math.ceil(xa.max()) + 3)))
        self.target = self.measure(ref)

    def measure(self, img, cropped=False):
        """{family: {"bands": (n, 3) amplitudes, "broad": (m,) G profile or None}}."""
        y0, _y1, x0, _x1 = self.box
        oy, ox = (y0, x0) if cropped else (0, 0)
        out = {}
        for name, f in self.fam.items():
            amps = []
            for b in f["bands"]:
                v = np.stack([RL._bilinear(img[..., k], b["xs"] - ox, b["ys"] - oy).mean(0)
                              for k in range(3)])
                amps.append(v @ b["row"])
            bro = None
            if f["broad"] is not None:
                acc = 0.0
                for xs, ys in f["broad"]["grids"]:
                    acc = acc + f["broad"]["M"] @ RL._bilinear(img[..., 1], xs - ox, ys - oy).mean(0)
                bro = acc / len(f["broad"]["grids"])
            out[name] = {"bands": np.array(amps).reshape(-1, 3), "broad": bro}
        return out

    def residual(self, meas):
        """Weighted residual vector, family by family, in code values of
        luminance and chroma (BAND_WEIGHT)."""
        parts = []
        for name in self.fam:
            m, t = meas[name], self.target[name]
            parts.append(((m["bands"] - t["bands"]) @ BAND_WEIGHT.T).ravel())
            if t["broad"] is not None:
                parts.append((m["broad"] - t["broad"]) * math.sqrt(BROAD_WEIGHT) * LUMA[1])
        return np.concatenate(parts)


# --------------------------------------------------------------------------- #
# the exact composite, over the measurement crop
# --------------------------------------------------------------------------- #
class Stack:
    """Coverage of every layer over the measurement crop, and the colours.

    The composite is the renderer's own algebra (fit_photometry.composite:
    screen and normal layers alike, in stack order), so scaling a calibrated
    layer's colour needs no re-render at all -- coverage depends only on shape.
    """

    def __init__(self, params, box):
        import build_svg
        import fit_photometry as FP
        self.FP = FP
        y0, y1, x0, x1 = box
        A, names = FP.basis_stack(params)
        self.A = A[:, y0:y1, x0:x1].astype(np.float32)
        self.names = names
        self.WC = FP.params_wc(params).astype(np.float64)
        self.normal = FP.normal_flags(params)
        missing = [lid for lid in CALIBRATED_LAYERS if lid not in names]
        if missing:
            raise SystemExit("calibrated layer(s) missing from the params: %s" % ", ".join(missing))
        self.idx = [names.index(lid) for lid in CALIBRATED_LAYERS]
        self.build = build_svg.build

    def image(self, k):
        WC = self.WC.copy()
        for j, i in enumerate(self.idx):
            WC[i] = WC[i] * k[j]
        return self.FP.composite(self.A, self.FP.colors(WC).astype(np.float32), self.normal) * 255.0


def solve(lines, stack, lo, hi, iters=12, verbose=False):
    """Levenberg-Marquardt over the per-layer scale factors, bounded to [lo, hi]."""
    n = len(stack.idx)
    k = np.ones(n)

    def res(kk):
        return lines.residual(lines.measure(stack.image(kk), cropped=True))

    r = res(k)
    cost = float(r @ r)
    lam = 1e-3
    for _it in range(iters):
        J = np.empty((r.size, n))
        for j in range(n):
            h = 0.02 * k[j]
            kk = k.copy()
            kk[j] += h
            J[:, j] = (res(kk) - r) / h
        JtJ, g = J.T @ J, J.T @ r
        D = np.diag(np.diag(JtJ)) + 1e-9 * np.eye(n)
        improved = False
        while lam < 1e8:
            step = -np.linalg.solve(JtJ + lam * D, g)
            kn = np.clip(k + step, lo, hi)
            rn = res(kn)
            cn = float(rn @ rn)
            if cn < cost:
                k, r, lam, improved = kn, rn, max(lam / 3.0, 1e-6), True
                rel = (cost - cn) / max(cost, 1e-9)
                cost = cn
                break
            lam *= 4.0
        if not improved or rel < 1e-5:
            break
    return k, J


def correction(lines, stack, meas):
    """The per-layer scale a fresh measurement still asks for (1.0 = none).

    One Gauss-Newton step from the measured state, through the composite's
    Jacobian: exactly the question "would the calibration move this layer?".
    Layers that no measurement sees (a zero Jacobian column) are reported as 1.
    """
    n = len(stack.idx)
    base = lines.measure(stack.image(np.ones(n)), cropped=True)
    r0 = lines.residual(base)
    J = np.empty((r0.size, n))
    for j in range(n):
        kk = np.ones(n)
        kk[j] += 0.02
        J[:, j] = (lines.residual(lines.measure(stack.image(kk), cropped=True)) - r0) / 0.02
    r = lines.residual(meas)
    JtJ = J.T @ J
    seen = np.diag(JtJ) > 1e-6
    corr = np.ones(n)
    if seen.any():
        Js = J[:, seen]
        corr[seen] = 1.0 - np.linalg.solve(Js.T @ Js + 1e-6 * np.eye(int(seen.sum())), Js.T @ r)
    return corr, J


def control(lines, J):
    """Which radial interval each layer controls, from the Jacobian (G rows)."""
    out, row = {}, 0
    names = list(CALIBRATED_LAYERS)
    for fname, f in lines.fam.items():
        nb = len(f["bands"])
        G = np.abs(J[row:row + 3 * nb].reshape(nb, 3, -1)[:, 1, :])
        tot = G.sum(1) + 1e-12
        for lid in FAMILIES[fname]["layers"]:
            j = names.index(lid)
            share = G[:, j] / tot
            rs = [b["r"] for b, sh in zip(f["bands"], share) if sh >= 0.5]
            out[lid] = (fname, (min(rs), max(rs)) if rs else None)
        row += 3 * nb + (len(f["broad"]["M"]) if f["broad"] is not None else 0)
    return out


def scale(layer, k):
    """Scale a layer's light by k, hue kept: white/cyan/blue and the colour."""
    import fit_photometry as FP
    wc = [float(layer.get(c, 0.0)) * k for c in CHANNELS]
    for c, v in zip(CHANNELS, wc):
        layer[c] = round(v, 6)
    layer["color"] = [round(float(v) * 255.0, 2) for v in FP.color_from_wc(wc)]


def render_full(params):
    import build_svg
    import fit_photometry as FP
    return FP.render_array(build_svg.build(params)).astype(np.float64) * 255.0


def report(lines, meas, label):
    """Per family: luminance gain and rms (what the solve matches) and the G
    and B gains, whose disagreement is the hue the colour cone cannot draw."""
    print("  %s:" % label)
    for name in lines.fam:
        t, m = lines.target[name]["bands"], meas[name]["bands"]
        yt, ym = t @ LUMA, m @ LUMA
        gain = lambda a, b: float(a @ b / max(b @ b, 1e-9))  # noqa: E731
        rms = float(np.sqrt(np.mean((ym - yt) ** 2))) if len(yt) else float("nan")
        print("    %-17s Y-gain %.2f rms %.1f   (G-gain %.2f, B-gain %.2f)"
              % (name, gain(ym, yt), rms, gain(m[:, 1], t[:, 1]), gain(m[:, 2], t[:, 2])))


def calibrate(params_path, ref, rounds=8, verbose=True, lines=None, stack=None):
    """Calibrate every family jointly; returns (worst, corrections) of the SAVED file.

    `lines` and `stack` may be passed in to share their set-up between runs on
    parameter files that differ only in COLOUR (the regression checks do):
    coverage depends on shape alone, and the stack's colours are re-read from
    the file here, so a stack built from the same shapes is exact.
    """
    params = json.load(open(params_path))
    lines = lines if lines is not None else Lines(ref)
    if stack is None or stack.names != [L["id"] for L in params["layers"]]:
        stack = Stack(params, lines.box)
    else:
        stack.WC = stack.FP.params_wc(params).astype(np.float64)
    by_id = {L["id"]: L for L in params["layers"]}
    first = None
    for it in range(rounds):
        k, J = solve(lines, stack, 1.0 / ROUND_GAIN, ROUND_GAIN)
        if first is None:
            first = J
        for lid, kk in zip(CALIBRATED_LAYERS, k):
            scale(by_id[lid], float(kk))
        json.dump(params, open(params_path, "w"), indent=1)
        stack.WC = stack.FP.params_wc(params).astype(np.float64)
        if verbose:
            print("  round %d: scales %s" % (it, " ".join("%s %.3f" % (lid[10:], v)
                                                         for lid, v in zip(CALIBRATED_LAYERS, k))))
        corr, _J = correction(lines, stack, lines.measure(render_full(params)))
        if np.abs(np.log(np.clip(corr, 1e-3, None))).max() / TOL <= 1.0:
            break
    # Whatever happened above, the file on disk is what ships, so measure THAT.
    img = render_full(json.load(open(params_path)))
    meas = lines.measure(img)
    corr, J = correction(lines, stack, meas)
    worst = float(np.abs(np.log(np.clip(corr, 1e-3, None))).max() / TOL)
    if verbose:
        report(lines, meas, "verified (full render of %s)" % os.path.basename(params_path))
        ctl = control(lines, first if first is not None else J)
        for lid, c in zip(CALIBRATED_LAYERS, corr):
            fam, span = ctl[lid]
            print("    %-15s %-17s controls %-13s still asks x%.3f"
                  % (lid, fam, ("r %g-%g" % span) if span else "(shared)", c))
    return worst, dict(zip(CALIBRATED_LAYERS, corr))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--geometry", action="store_true",
                    help="write the geometry of record into every ray layer first")
    ap.add_argument("--rounds", type=int, default=8,
                    help="solve-and-verify rounds; 0 only verifies the file as it is")
    a = ap.parse_args()

    params = json.load(open(a.params))
    if a.geometry:
        print("geometry:")
        apply_geometry(params)
        json.dump(params, open(a.params, "w"), indent=1)
    else:
        problems = geometry_problems(params)
        if problems:
            print("  warning: " + "\n  warning: ".join(problems))
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float64)
    worst, _corr = calibrate(a.params, ref, rounds=a.rounds)
    status = "converged" if worst <= 1.0 else "NOT converged"
    print("  %s: worst remaining correction %.2f of its tolerance (TOL %.2f in ln)"
          % (status, worst, TOL))
    print("wrote", a.params)
    # The exit status is the whole point of the verification pass: corrections
    # computed on the way are already saved, so a caller that only looked at the
    # file could not tell a calibrated state from an uncalibrated one.
    if worst > 1.0:
        print("  FAILED: calibration did not converge; the saved parameters are NOT "
              "calibrated -- re-run with a larger --rounds")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
