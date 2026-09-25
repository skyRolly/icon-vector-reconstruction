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

#: The geometry keys of a `ray` layer: EVERY key the builder reads to place and
#: shape one (src/build_svg.py, kind "ray").  `rot` is the SVG rotation (the
#: direction is -rot, degrees counter-clockwise from east).  `cx`/`cy` are the
#: ray's ORIGIN in canvas coordinates -- the ray runs from there along its
#: direction -- and `dx`/`dy` are an offset added to it; the builder falls back
#: to the flare centre for a missing `cx`/`cy`.  `len` is the length from the
#: origin; `onset`, `peak_at` and `tail` place the longitudinal profile as
#: fractions of `len` (0 before `onset`, 1.0 at `peak_at`, 0.42 at peak_at +
#: tail, 0 at the end); `height` is the near-end width, `spread` the far end's
#: width as a multiple of it, and `blur` the Gaussian softening of both.  None
#: means "absent from the layer": the builder's default (0 for dx/dy/onset,
#: 0.35 for tail) applies, and the key is removed so the params stay as small
#: as the model is.
#:
#: POSITION IS ABSOLUTE (D63).  Every ray's origin of record is its measured
#: foot in canvas pixels, pinned with `cx`/`cy`, and `dx`/`dy` are absent.
#: Until D63 the rays stored dx/dy relative to `flare.cx/cy`, and the
#: optimiser's geometry stage searches the flare centre +-30 px: a search that
#: moved the centre moved all thirteen rays off their measured lines, and
#: `--geometry` then restored the RELATIVE offsets, so it could not bring them
#: back.  The lines were measured in canvas coordinates (tools/ray_lines.py
#: LINES), several of them do not pass through the core at all, and a ray
#: pinned to its own origin is not in `build_svg.flare_dependent_layers`, so the
#: flare-centre search no longer touches it.
GEOMETRY_KEYS = ("rot", "cx", "cy", "dx", "dy", "len", "onset", "peak_at", "tail",
                 "height", "spread", "blur")

#: What the builder does to a ray's longitudinal stops (src/build_svg.py): the
#: onset is clamped to ONSET_CLAMP * peak_at and the 0.42 stop to TAIL_CLAMP of
#: `len`.  A value past either clamp renders as the clamp, so a table holding
#: it records a geometry nobody sees; geometry_problems() reports it.
ONSET_CLAMP = 0.95
TAIL_CLAMP = 0.999
DEFAULT_TAIL = 0.35

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
    # offset is in its origin.  height 12 -> 9 because beyond r 70 the ray carried
    # 1.8-3.0x too much light (D38).  Its LONGITUDINAL profile is D62's: the
    # reference peaks at r ~60 (G 22.7), is 0.42 of that by r ~90 and fades
    # slowly to ~0 by r ~125 (G 7.0 / 5.3 / 3.7 / 1.9 at r 92-116); the old
    # len 100 with the fixed 0.35 fade dropped from 0.42 to nothing between
    # r 97 and 100.  Fitted to the line-following amplitudes with the
    # reference's own templates: peak 54 px, 0.42-point 89 px, end 148 px.
    "flare_ray_a": dict(rot=-107.1, cx=525.167, cy=516.42, dx=None, dy=None,
                        len=148.0, onset=None, peak_at=0.3649, tail=0.2365,
                        height=9.0, spread=1.0, blur=4.5309),
    # The white NORTH-WEST arm of the core (D63): the inner part of the
    # upper-left light, white where the ray itself is cyan.  The reference is
    # whiter than the model in a radial blob at 110-120 deg, r 13-27 (R -19 to
    # -25 against the reference, G and B -9 to -13 with it, so it is light, not
    # hue), stable from sigma 1 to 4 and 12-15 px across -- two to three JPEG
    # blocks, in all three channels.  Its ridge runs through the core at 116.6
    # deg; fitted as a short white segment on the core's 2D residual (4 px x 15
    # deg bins, r 2-64) it lands on 116.4 deg, onset 7, peak 21, end 35 px.
    # That is not the outer ray's line (107.1 deg from 6 px off the core), so it
    # has its own origin on the core.
    "flare_ray_a_in": dict(rot=-116.438, cx=531.0, cy=513.5, dx=None, dy=None,
                           len=35.388, onset=0.192, peak_at=0.6019, tail=0.25,
                           height=6.654, spread=1.0, blur=4.239),
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
    # (A's tail is the drawn 0.349: the default 0.35 sat 0.001 past the clamp.)
    "flare_ray_ula": dict(rot=-140.4, cx=519.9, cy=526.9, dx=None, dy=None,
                          len=215.0, onset=0.42, peak_at=0.65, tail=0.349,
                          height=4.0, spread=1.0, blur=2.8),
    "flare_ray_ulb": dict(rot=-149.5, cx=518.0, cy=535.6, dx=None, dy=None,
                          len=175.0, onset=0.35, peak_at=0.55, tail=None,
                          height=6.0, spread=1.0, blur=3.2),
    # Lower-left ray, on its measured line: 255.2 deg through (524.2, 511.7),
    # 7.0 px from the core, the reference's ridge within +-1.5 px of the line in
    # every band from r 40 to 128.  Its profile along the line is a plateau
    # (G 11.1-12.2 at r 56-64, 9.5-11.2 at r 72-104, 4.5 by r 112), which one
    # single-peaked gradient cannot hold, so it is two segments on the same line.
    # D63 corrected an onset the builder could not draw: the inner segment's
    # record held onset 0.4463 against peak_at 0.4011, an onset AFTER its own
    # peak, which rendered clamped at 0.381 (a hard start at 36 px).  The
    # reference fades in from r ~26 (centre minus flank 2.7-4.5 at r 28-40,
    # 7-11 by r 52-60, nothing at r 12-24), and the default tail put the outer
    # segment's 0.42 stop past its own end, so it stopped dead at 133 px.  Both
    # were refitted jointly on the line with every stop reachable and each
    # segment's end capped where the reference's ray has gone: inner onset 24,
    # peak 38, 0.42 at 72, end 119 px; outer onset 50, peak 97, 0.42 at 135,
    # end 149 px.  Band error 159 -> 49 on the reference's own templates.
    # The inner segment was then fitted JOINTLY with the 229-degree lobe on both
    # lines (a later D63 step): 7 px from the lobe's line at r ~30, its light
    # lies inside the lobe's measurement window, and a fit on its own line had
    # put light there that the lobe's line reads as the lobe's (onset 24 -> 25,
    # peak 38 -> 34 px; joint band error 40.8 -> 30.6).
    "flare_ray_b": dict(rot=-255.2, cx=524.2, cy=511.7, dx=None, dy=None,
                        len=119.4483, onset=0.2123, peak_at=0.2871, tail=0.2713,
                        height=9.4638, spread=1.25, blur=2.4209),
    "flare_ray_b2": dict(rot=-255.2, cx=524.2, cy=511.7, dx=None, dy=None,
                         len=149.3837, onset=0.3348, peak_at=0.6513, tail=0.2541,
                         height=9.4638, spread=1.0, blur=2.4209),
    # The short lower-left lobe at 229 deg (D61), through the core, broad
    # (sigma 4.3-6.1 px).  D62 splits it by COLOUR along its length, because
    # one layer has one colour: the reference is WHITE at r 24-40 (R 11.0,
    # 19.2, 7.5 at r 24/32/40, ~0 by r 48) and CYAN at r 32-56 (G 13.4, 13.2,
    # 10.5 at r 32/40/48), and gone by r ~60 -- the single white+cyan layer put
    # white along the whole lobe (R 5-6 at r 40-56) and ran ~10 px too long
    # (G 12.1 / 7.4 at r 56/64 against 4.9 / 0.2).  Same line, same width:
    # llc_in is the white near-core part, llc the cyan lobe and its fade.
    # D63: at r 32 the lobe read 1.7x the reference's G and 1.6x its R, at
    # sigma 8.1 against 4.3 -- too WIDE, not too long.  The white segment's
    # blur 5.0 -> 3.6 (sigma 6.0 on the line), and both segments' shapes and
    # colours refitted jointly with the lower-left ray's inner segment, whose
    # light shares this line's window at r 28-36.
    # D64: the white still peaked too far out -- R 6.9 / 22.5 / 5.8 at r
    # 24/32/40 (5.0 / 24.0 / 9.6 once the lobe took the teal primary) against
    # 10.3 / 19.2 / 7.5; now 10.3 / 19.1 / 3.9.  Its longitudinal shape and width
    # refitted on the line's ramp-removed corridor (r 16-64, with the cyan
    # segment's amplitude): onset 21 -> 15.5 px, peak 29 -> 28, end 42 -> 35,
    # blur 3.6 -> 2.65; corridor error 13.0 -> 11.0.
    # D65: the near lobe was right (R 12.0 against 11.0 at r 24 on the family's
    # own reading) but the white fell short from r 32 outward: R 15.3 / 3.5
    # against 19.2 / 7.5 at r 32 / 40.  Only the outer fade was moved -- onset
    # (15.5 px) and peak (28.3 px) held at the same radii, 0.42 of peak at
    # 33.5 -> 37.6, end 35 -> 40.  After
    # the family's recalibration, R at r 24/32/40/48 reads 9.4/18.3/7.2/0.0
    # against the reference's 11.0/19.2/7.5/-0.7 (base 12.0/15.3/3.5/1.3).
    "flare_ray_llc_in": dict(rot=-229.0, cx=531.0, cy=513.5, dx=None, dy=None,
                             len=40.0, onset=0.3876, peak_at=0.7067, tail=0.2333,
                             height=6.912, spread=1.0, blur=2.6461),
    "flare_ray_llc": dict(rot=-229.0, cx=531.0, cy=513.5, dx=None, dy=None,
                          len=59.9874, onset=0.5564, peak_at=0.6636, tail=0.1075,
                          height=5.6348, spread=1.0, blur=5.0159),
    # The 267-degree lower-left ray (D61): two maxima on one line, G 11.8 at
    # r 44 and 7.6 at r 92 with a dip to 3.4 between -- two segments.
    # The outer segment's tail is the value the builder already drew (D63):
    # the default 0.35 put its 0.42 stop past the end of the ray and was
    # clamped to 0.999.  Its fade is not measurable on its own line -- beyond
    # r 76 the fit there is the ray and the vertical line together -- so the
    # drawn profile is kept and only made explicit.
    "flare_ray_lld": dict(rot=-265.5, cx=531.0, cy=513.5, dx=None, dy=None,
                          len=69.7979, onset=0.3729, peak_at=0.6011, tail=None,
                          height=8.0, spread=1.0, blur=2.8),
    "flare_ray_lld2": dict(rot=-266.5, cx=531.0, cy=513.5, dx=None, dy=None,
                           len=123.8089, onset=0.5074, peak_at=0.7073, tail=0.2917,
                           height=3.1354, spread=1.0, blur=2.4),
    # The white SOUTH arm of the core (D63), and the whiter south vertical line
    # near the core.  South of the core the reference carries a broad white
    # ridge centred 2-4 px west of the vertical line at dy +12..+28 (R ~90 at dy
    # +20, FWHM ~10 px), R -20 to -25 against the model and G/B -9 to -12 with
    # it; the vertical line is one narrow cyan layer and cannot be it.  Fitted
    # on the same 2D residual as the north-west arm: a vertical white segment
    # 5 px west of the core, onset dy +11, peak +17, end +29.
    "flare_ray_s_in": dict(rot=-270.0, cx=526.08, cy=518.515, dx=None, dy=None,
                           len=23.83, onset=0.25, peak_at=0.5135, tail=0.28,
                           height=8.746, spread=1.0, blur=4.821),
    # The white EAST extension of the core to the right curve (D65).  Between
    # the core and the curve, at dx +4..+8 and dy -8..+10, the model was R -12.5
    # with G -1.7 (white missing, not light), and just past the curve's ridge
    # R -5.7 with G +5.3; the reference's R >= 230 core runs 16.8 px east to
    # the curve where the model's stopped at 5.6.  (The one-column R/G/B spikes
    # on the curve's own inner edge, at every height, are the curve's edge
    # placement and are not this.)  Fitted on dx -8..+24, |dy| <= 16 about the
    # core with the edge columns dx +9..+13 and clipped pixels left out: box
    # error 50.7 -> 36.9, dx +4..+8 R -12.5 -> -2.3, beyond the ridge R -5.7 ->
    # -0.1 (G +5.3 -> +6.4), the west side unchanged.
    "flare_ray_east_in": dict(rot=5.694, cx=531.0, cy=513.5, dx=None, dy=None,
                              len=25.4144, onset=0.1, peak_at=0.576, tail=0.052,
                              height=22.2101, spread=1.0, blur=2.6831),
    # Upper-right SOFT FLANK.  Axis 44.9 +- 0.4 (45.6 is excluded at ~6 sigma);
    # ends at r = 140 +- 15.  height 8 -> 26, spread 1.30 -> 1.00, len 150 -> 143
    # and a 5.4 px normal offset are a JOINT correction (D59): each alone is
    # worse than what it replaced.  A half-maximum is not a stable quantity in
    # this corridor (10.55 / 15.06 / 1.41 px over adjacent 20 px bands), which is
    # why the table no longer stores a "measured FWHM" for it.
    "flare_ray_e": dict(rot=-44.9, cx=526.1383, cy=510.505, dx=None, dy=None,
                        len=143.0, onset=None, peak_at=0.28, tail=None,
                        height=26.0, spread=1.0, blur=3.5634),
    # Upper-right NARROW CORE (D61), on its own measured line: 47.6 deg,
    # 5.2 px off the core; width sigma 3.3-4.8 px in the reference.  D62: the
    # reference holds G ~7 from r 74 to 98 and is down to 4.5 by r 106; the
    # core's fade (0.42 at 146 px of 151) kept light at r 110-140 that belongs
    # at r 90-98.  Its onset and fade are re-fitted, not its amplitude alone:
    # onset 28 -> 46 px, 0.42-point 146 -> 106 px, peak and end unchanged.
    "flare_ray_ur": dict(rot=-47.6, cx=534.8, cy=517.0, dx=None, dy=None,
                         len=150.8106, onset=0.3036, peak_at=0.6192, tail=0.0848,
                         height=1.8314, spread=1.0, blur=2.4929),
    # Lower-right TAIL.  Direction 327.3-328.1 and NOT resolvable further: a
    # transverse-position matched filter prefers 327.2-327.5, corridor pixel
    # error 327.8-328.1.  The ~3 px TRANSLATION of its origin off the core is
    # confirmed (it was a dx/dy offset until D63) and must not
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
    # D63: the tail is a LINE, not a widening band.  Beyond r 128 the
    # reference's ray is narrow -- sigma 2.2 [2.0..3.1] at r 136 over window
    # 9/12/15 px and a +-1 px line offset, 3.2-4.4 at r 128-168 -- where the
    # spread-2.2 wedge measured 5.0-5.8 and carried 2-4x the reference's light at
    # r 128-144.  Parallel-sided (spread 1.0), blur 3.1, the fade refitted
    # (0.42-point 100 -> 103 px, end 177 -> 185 px): sigma 3.5-3.7 along the ray,
    # fixed-template band error 32.4 -> 28.2.  The translation is unchanged.
    # D64: the narrow line stays; the widening D61 saw and D63 removed is real
    # but belongs to a separate soft flank on the same line (flare_ray_c_fl).
    # D65: read with a narrow AND a broad template per band (FAMILIES split),
    # the reference's narrow line is nearly gone beyond r ~105 (r 108-140: 1.4
    # against the model's 4.0, robust in sign and size over six template
    # choices) while its soft flank carries the light.  The line's fade was
    # refitted on that reading with the flank's: peak r 69 -> 59, 0.42 of peak
    # at r 103 -> 91, end r 185 -> 131.  Translation, width and blur unchanged.
    "flare_ray_c": dict(rot=-328.1, cx=531.5309, cy=511.7803, dx=None, dy=None,
                        len=130.7436, onset=None, peak_at=0.4541, tail=0.2451,
                        height=5.4845, spread=1.0, blur=3.1),
    # Lower-right bright INNER segment on the same line (D61): the reference is
    # brightest and white next to the core (G 17.8, R 12.6 at r 44) and its
    # white is gone by r 52 (R 3.0), where the segment still gave R 9.6 (D62:
    # peak 30 -> 42 px, 0.42-point 54 -> 50 px).
    "flare_ray_c_in": dict(rot=-328.1, cx=531.53, cy=511.78, dx=None, dy=None,
                           len=64.1046, onset=None, peak_at=0.6621, tail=0.1113,
                           height=6.5097, spread=1.0, blur=1.5175),
    # Lower-right SOFT FLANK (D64), on the same line: the ray is two parts, as
    # the upper-right one is (a narrow line inside a soft slab).  Averaged over
    # 16-28 px bands with each band's ramp removed at |s| 16-22, the reference's
    # transverse sigma grows 2.6 (r 60-88) -> 4.75 (92-108) -> 5.4 (108-128) ->
    # 5.7-5.8 (132-184), identical after a 2x box downsample, where the narrow
    # line alone gave a flat 3.0-3.6 and 0.07-0.75 of the reference's flux.
    # D63's "narrow tail" reading came from the free-template band fit, which
    # takes the flank into its ramp.  Fitted with the narrow segments'
    # amplitudes in the same ramp-removed domain over r 40-184: corridor error
    # 3.50 -> 2.44, against 2.68 for the narrow ray widened alone (a spread-3.6
    # wedge).  Starts 81 px out, peaks at 93, 0.42 of peak by 151, gone by 200.
    # D65: fitted jointly with the narrow line's fade on the split reading: peak
    # r 93 -> 98, 0.42 of peak at r 151 -> 175, end r 200 -> 192.
    "flare_ray_c_fl": dict(rot=-329.362, cx=600.9434, cy=554.3329, dx=None, dy=None,
                           len=110.5395, onset=0.0115, peak_at=0.1538, tail=0.6948,
                           height=8.0227, spread=1.0, blur=7.4125),
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
    "lower-right": {"line": "lower-right", "layers": ("flare_ray_c_in", "flare_ray_c", "flare_ray_c_fl"),
                    "split": (88.0, 184.0, 3.0, 7.5, 22.0)},
}
CALIBRATED_LAYERS = tuple(dict.fromkeys(lid for f in FAMILIES.values() for lid in f["layers"]))

#: |ln(correction)| per layer below which the layer counts as calibrated.
TOL = 0.08
#: A calibrated layer with NO light at all is outside what calibration can do
#: (see dark_report): it scales a layer's light, and any scale of zero is zero.
#: Such a layer fails the calibration when the reference asks it for more than
#: this much light, in code values of band luminance, and that light explains
#: at least MISSING_EXPLAINED of the residual where the layer reaches.  Both
#: are set from the shipped rays (D66): zeroing any one of the fourteen, the
#: reference asks for 3.7-20.5 cv, explaining 0.90-1.00; a zero-light copy of a
#: calibrated ray, which the reference has no use for, is asked 0.01-0.05 cv.
MISSING_CV = 1.0
MISSING_EXPLAINED = 0.5
#: The white amount a dark layer is probed with.  Its hue is unknown -- it has
#: none -- so only the luminance rows are read, and the probe is small enough
#: to stay in the composite's linear range.
PROBE_WHITE = 0.05
#: A calibrated layer counts as DARK when its basis amounts sum to less than
#: this: at full coverage it would add under ~0.5 cv, which no calibrated ray
#: legitimately does (the faintest shipped one, flare_ray_b2, holds ~0.044).
#: Exactly zero was the first definition; a ray scaled to 1e-9 is no less
#: missing, and its Jacobian column is just as unusable (D66 review).
DARK_AMOUNT = 2e-3
#: A dark layer whose probe response is, all but this fraction, a re-scaling of
#: lit calibrated layers is indistinguishable from them: the reference cannot
#: say it is needed rather than they are under-scaled, so it is "not needed".
DISTINCT_MIN = 0.1
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
CHANNELS = ("white", "cyan", "blue", "teal")
#: The ray layers allowed the fourth primary, TEAL (0, 1, 0.7) in
#: tools/fit_photometry.py (D64).  Each belongs to a family whose own line reads
#: B below G above the local ramp -- beyond what white/cyan/blue can draw --
#: measured as amplitude-weighted B/G over the family's clean bands against
#: cyan's floor of ~1.06: upper-left A 0.73, the upper-right 0.78-0.80, the
#: 267-degree pair 0.85-0.86, the 229-degree lobe 0.74-0.76.  The lobe's WHITE
#: segment is white and stays in the cone.  Every other layer is a cone layer,
#: and test_pipeline requires that the params agree with this list exactly.
TEAL_LAYERS = ("flare_ray_ula", "flare_ray_ur", "flare_ray_e", "flare_ray_lld",
               "flare_ray_lld2", "flare_ray_llc")


# --------------------------------------------------------------------------- #
# geometry
# --------------------------------------------------------------------------- #
def profile_problems(lid, g):
    """Longitudinal values of one ray (a table entry or a layer) that the
    builder would not render as written.

    The builder clamps two stops (src/build_svg.py, kind "ray"): the onset to
    ONSET_CLAMP * peak_at, and the 0.42 stop, peak_at + tail, to TAIL_CLAMP of
    `len`.  A value past a clamp renders as the clamp.  Until D63 nothing said
    so: `flare_ray_b`'s record held onset 0.4463 against peak_at 0.4011, i.e.
    an onset AFTER the peak, and rendered at 0.381 -- the table described a ray
    that was never drawn, and a search that moved the onset anywhere above the
    clamp changed nothing.  An absent tail is the builder's default and is held
    to the same rule: `flare_ray_b2` and `flare_ray_lld2` peak so late that
    the default put their 0.42 stop past the end of the ray.
    """
    out = []
    pk = g.get("peak_at")
    pk = 0.3 if pk is None else float(pk)
    on = g.get("onset")
    on = 0.0 if on is None else float(on)
    tl = g.get("tail")
    tl_s = "tail %g" % tl if tl is not None else "the default tail %g" % DEFAULT_TAIL
    tl = DEFAULT_TAIL if tl is None else float(tl)
    if not 0.0 < pk < TAIL_CLAMP:
        out.append("%s: peak_at %g is outside (0, %g)" % (lid, pk, TAIL_CLAMP))
    if on < 0.0:
        out.append("%s: onset %g is negative" % (lid, on))
    elif on > 0.0 and on > ONSET_CLAMP * pk + 1e-9:
        out.append("%s: onset %g is past the builder's clamp %g x peak_at %g = %.4f, so it "
                   "renders as %.4f -- the record is not the ray that is drawn"
                   % (lid, on, ONSET_CLAMP, pk, ONSET_CLAMP * pk, ONSET_CLAMP * pk))
    if tl <= 0.0:
        out.append("%s: tail %g is not positive" % (lid, tl))
    elif pk + tl > TAIL_CLAMP + 1e-9:
        out.append("%s: peak_at %g + %s = %.4f is past the builder's clamp %g, so the 0.42 "
                   "stop renders at %g -- record the tail that is drawn"
                   % (lid, pk, tl_s, pk + tl, TAIL_CLAMP, TAIL_CLAMP))
    return out


def geometry_problems(params):
    """Everything that stops the table above from being the model's geometry.

    Returns a list of strings: a ray layer without an entry, an entry without a
    layer, a key outside GEOMETRY_KEYS, an entry without an absolute origin, a
    longitudinal value the builder would clamp (profile_problems), a canonical
    value outside the layer's own search bounds (which the optimiser would clip
    on its first trial, silently moving the ray off its measurement), and a
    retired flank.  These are problems of the RECORD: `--geometry` refuses to
    apply a record that has any.  What a layer currently holds is drift(),
    which `--geometry` exists to repair.
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
        if g.get("cx") is None or g.get("cy") is None:
            out.append("%s has no absolute origin (cx/cy): its position would follow the flare "
                       "centre, which the geometry search moves" % lid)
        out += profile_problems(lid, g)
        for k, v in g.items():
            b = L.get("bounds", {}).get(k)
            if v is not None and b is not None and not (b[0] <= v <= b[1]):
                out.append("%s/%s canonical %g outside its search bounds [%g, %g]" % (lid, k, v, b[0], b[1]))
            if v is None and b is not None:
                out.append("%s/%s is absent from the record but still carries search bounds %s"
                           % (lid, k, b))
    for L in params["layers"]:
        if L["id"] in RETIRED_FLANKS:
            out.append("retired flank layer %s is present" % L["id"])
    return out


def drift(params):
    """(layer, key, record, value) wherever a ray layer differs from its record,
    plus any ray layer whose own longitudinal values the builder would clamp.
    Empty means the params draw exactly the geometry of record."""
    out = []
    for L in params["layers"]:
        if L.get("kind") != "ray":
            continue
        g = RAY_GEOMETRY.get(L["id"])
        if g is not None:
            for k in GEOMETRY_KEYS:
                want, got = g.get(k), L.get(k)
                if (want is None) != (got is None) or (
                        want is not None and abs(float(want) - float(got)) > 1e-9):
                    out.append((L["id"], k, want, got))
        for msg in profile_problems(L["id"], L):
            out.append((L["id"], "profile", None, msg))
    return out


def apply_geometry(params, verbose=True):
    """Write the geometry of record into every ray layer.  Bounds are NOT touched.

    Until D62 this also rewrote each ray's `bounds` to generic wide intervals
    (rot +-6 deg, height 3-40, blur 0.6-10, len -45/+60 ...), which replaced the
    measured narrow intervals a ray had been given -- `flare_ray_b`'s rotation
    window went from +-3 to +-6 degrees and its length window roughly doubled
    on every rebuild.  A search space is a separate decision from a
    measurement; the only thing checked here is that the canonical value lies
    inside it.  Every key of GEOMETRY_KEYS is written or removed, so a key a
    search added (an offset, a per-layer centre) does not survive a rebuild.
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
            print("  %-16s direction %6.1f  origin (%7.2f, %7.2f)  len %6.1f  h %5.2f blur %4.2f"
                  % (lid, -g["rot"], g["cx"], g["cy"], g["len"], g["height"], g["blur"]))


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

    The optional SPLIT reading (D65) is for a line drawn as a narrow segment
    inside a soft flank: over its radial range each band is read with TWO
    fixed templates at once -- a narrow and a broad Gaussian on the
    reference's own centre, above a ramp -- so the band yields a narrow and a
    broad amplitude per channel, both linear in the image.  A single template
    cannot tell a flank's light from a line's; the pair can (condition number
    3.7 on the lower-right line), which is what lets a flank be calibrated at
    all instead of being traded for the line.
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
            split_r0 = spec["split"][0] if "split" in spec else float("inf")
            for r, _ar, _ag, _ab, s0, sg in rows:
                if abs(s0) >= 3.95 or sg <= 0.85 or sg >= 8.95:
                    continue                   # the reference has no clean ray here
                if r < spec.get("r_min", 0.0):
                    continue                   # inside another structure's glow
                if r >= split_r0:
                    continue                   # read by the split templates instead
                s, xs, ys = RL.band_coords(foot, d, r - 4.0, 8.0, hw)
                bands.append({"r": float(r), "xs": xs, "ys": ys, "row": RL.amplitude_row(s, s0, sg)})
                xs_all.append(xs)
                ys_all.append(ys)
            f = {"bands": bands, "broad": None, "split": []}
            if "split" in spec:
                q0, q1, sn, sb, shw = spec["split"]
                for r in np.arange(q0, q1, 8.0):
                    s, xs, ys = RL.band_coords(foot, d, r, 8.0, shw)
                    s0 = RL.fit_gauss_line(s, RL._bilinear(ref[..., 1], xs, ys).mean(0))[1]
                    X = np.stack([np.exp(-0.5 * ((s - s0) / sn) ** 2),
                                  np.exp(-0.5 * ((s - s0) / sb) ** 2), np.ones_like(s), s], 1)
                    f["split"].append({"r": float(r + 4.0), "xs": xs, "ys": ys,
                                       "rows": np.linalg.pinv(X)[:2]})
                    xs_all.append(xs)
                    ys_all.append(ys)
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
        """{family: {"bands": (n, 3) amplitudes, "broad": (m,) G profile or None,
        "split": (k, 2, 3) narrow and broad amplitudes (k = 0 without a split)}}."""
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
            spl = np.zeros((len(f["split"]), 2, 3))
            for j, b in enumerate(f["split"]):
                v = np.stack([RL._bilinear(img[..., k], b["xs"] - ox, b["ys"] - oy).mean(0)
                              for k in range(3)])            # (3, n_s)
                spl[j] = b["rows"] @ v.T                     # (2, 3): narrow, broad
            out[name] = {"bands": np.array(amps).reshape(-1, 3), "broad": bro, "split": spl}
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
            if len(t["split"]):
                parts.append(((m["split"] - t["split"]) @ BAND_WEIGHT.T).ravel())
        return np.concatenate(parts)

    def luma_rows(self):
        """Mask over residual(): the rows that measure luminance (each band's
        first BAND_WEIGHT row, and the broad G profile), not chroma."""
        nw = BAND_WEIGHT.shape[0]
        mask = []
        for name in self.fam:
            f, t = self.fam[name], self.target[name]
            mask += ([True] + [False] * (nw - 1)) * len(f["bands"])
            if t["broad"] is not None:
                mask += [True] * len(t["broad"])
            mask += ([True] + [False] * (nw - 1)) * (2 * len(f["split"]))
        return np.array(mask, bool)


# --------------------------------------------------------------------------- #
# the exact composite, over the measurement crop
# --------------------------------------------------------------------------- #
def basis_key(params, lid):
    """Fingerprint of one layer's COVERAGE: the digest of its white basis SVG.

    A basis document holds that one layer and nothing else, painted white
    (src/build_svg.py Builder.document), so its text changes with everything
    that decides where the layer puts light -- its geometry, position,
    rotation, blur, clip, taper, profile tables, the flare centre it may be
    anchored to and the frame and curve geometry its clip uses -- and with
    nothing else.  In particular a change of colour does not touch it.
    """
    import hashlib
    import build_svg
    return hashlib.sha256(build_svg.build(params, basis=lid).encode("utf-8")).hexdigest()


class Stack:
    """Coverage of every layer over the measurement crop, and the colours.

    The composite is the renderer's own algebra (fit_photometry.composite:
    screen and normal layers alike, in stack order), so scaling a calibrated
    layer's colour needs no re-render at all -- coverage depends only on shape.

    WHAT MAKES A STACK VALID FOR A PARAMETER FILE (D63).  Its coverage arrays
    are right for params only if all of these match: the layers and their
    order (`names`); each layer's coverage fingerprint (`keys`, basis_key());
    the crop (`box`, which is the measurement's); and the renderer and size
    the arrays were made with, which this process fixes.  The blend flags and
    the colours are not baked in: `refresh()` re-reads both.  Until D63
    `calibrate()` reused a supplied stack whenever the layer NAMES matched, so a
    caller that moved a ray before calibrating was solved on the old ray's
    coverage.  Every reuse now goes through `refresh()`, which re-renders
    exactly the layers whose fingerprint changed and nothing else.
    """

    def __init__(self, params, box):
        import build_svg
        import fit_photometry as FP
        self.FP = FP
        self.box = tuple(box)
        y0, y1, x0, x1 = box
        A, names = FP.basis_stack(params)
        self.A = A[:, y0:y1, x0:x1].astype(np.float32)
        self.names = names
        self.keys = [basis_key(params, lid) for lid in names]
        self.renders = len(names)            # basis renders this stack has cost
        self.WC = FP.params_wc(params).astype(np.float64)
        self.normal = FP.normal_flags(params)
        missing = [lid for lid in CALIBRATED_LAYERS if lid not in names]
        if missing:
            raise SystemExit("calibrated layer(s) missing from the params: %s" % ", ".join(missing))
        self.idx = [names.index(lid) for lid in CALIBRATED_LAYERS]
        self.build = build_svg.build

    def matches(self, params, box):
        """True if this stack can be REFRESHED to params (same layers, same crop)."""
        return tuple(box) == self.box and self.names == [L["id"] for L in params["layers"]]

    def refresh(self, params):
        """Bring the coverage up to `params`; returns the ids re-rendered.

        A colour-only change re-renders nothing: the fingerprints are unchanged
        and only the colours and blend flags are re-read.
        """
        if self.names != [L["id"] for L in params["layers"]]:
            raise ValueError("a stack cannot be refreshed to a different layer list")
        y0, y1, x0, x1 = self.box
        changed = []
        for i, lid in enumerate(self.names):
            k = basis_key(params, lid)
            if k != self.keys[i]:
                a = self.FP.render_array(self.build(params, basis=lid))[..., 0]
                self.A[i] = a[y0:y1, x0:x1]
                self.keys[i] = k
                changed.append(lid)
        self.renders += len(changed)
        self.WC = self.FP.params_wc(params).astype(np.float64)
        self.normal = self.FP.normal_flags(params)
        return changed

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


def is_dark(stack, j):
    """True if calibrated layer j (index into CALIBRATED_LAYERS) has, in effect, no light."""
    return float(np.sum(stack.WC[stack.idx[j]])) < DARK_AMOUNT


def dark_report(lines, stack, meas, J=None):
    """{layer: (verdict, asked_cv, explained)} for every calibrated layer with no light.

    correction() reports a layer no measurement sees as needing nothing (1.0),
    which is right for a layer that is lit but out of sight -- and was wrong for
    a layer with no light: its Jacobian column is zero because a scale of zero
    is zero, not because nothing measures it, so a ray whose colour had been
    zeroed read as perfectly calibrated and the calibration said "converged"
    with the ray missing (the D66 review finding).

    A dark layer (is_dark) is probed instead: given a small white amount, what
    would it add to each band's luminance (d)?  The evidence is what the
    reference asks of that shape BEYOND what re-scaling the lit calibrated
    layers can supply -- the residual's luminance rows and d are both projected
    off the span of the lit layers' Jacobian columns before the non-negative
    projection of one on the other.  Without that, the family solve pushed a
    dark ray's light onto its lit neighbours (zero flare_ray_e and round 0 took
    flare_ray_ur x2.09), and the residual left over no longer asked for the
    missing ray: it was called "not needed" and the calibration converged
    (the D66 review's second finding).  Projected, the verdict is the same
    before and after any such re-scaling, to first order.

      "missing"       the reference asks for at least MISSING_CV of it, and that
                      explains at least MISSING_EXPLAINED of what the lit layers
                      cannot supply where the layer reaches: the ray is absent
                      from a line that has it.  Calibration FAILS: it scales
                      light and cannot make it.
      "not needed"    the reference asks nothing of its shape, or its shape is
                      a re-scaling of lit layers (DISTINCT_MIN): they carry it.
      "unobservable"  no band sees the layer at all.

    Seeding a colour here instead was considered and not done: calibration is
    multiplicative by design -- it keeps each layer's hue and sets its amount
    -- and a layer with no light has no hue to keep, so any seed would be a
    colour decision this tool has no evidence for.  The colour fit can start
    from zero (tools/fit_photometry.py --fit-rays), or the last calibrated
    colour can be restored.
    """
    import fit_photometry as FP
    out = {}
    dark = [j for j in range(len(CALIBRATED_LAYERS)) if is_dark(stack, j)]
    if not dark:
        return out
    if J is None:
        _corr, J = correction(lines, stack, meas)
    Y = lines.luma_rows()
    r = lines.residual(meas)
    base = lines.residual(lines.measure(stack.image(np.ones(len(stack.idx))), cropped=True))
    lit = [j for j in range(len(CALIBRATED_LAYERS)) if j not in dark and float(J[Y, j] @ J[Y, j]) > 1e-6]
    JL = J[Y][:, lit] if lit else np.zeros((int(Y.sum()), 0))

    def off_lit(v):                              # v minus its least-squares part in span(JL)
        if JL.shape[1] == 0:
            return v
        c = np.linalg.solve(JL.T @ JL + 1e-9 * np.eye(JL.shape[1]), JL.T @ v)
        return v - JL @ c
    want = off_lit(-r[Y])                        # light the reference has, that re-scaling cannot give
    for j in dark:
        lid, i = CALIBRATED_LAYERS[j], stack.idx[j]
        WC = stack.WC.copy()
        WC[i] = 0.0
        WC[i, 0] = PROBE_WHITE
        img = FP.composite(stack.A, FP.colors(WC).astype(np.float32), stack.normal) * 255.0
        d = (lines.residual(lines.measure(img, cropped=True)) - base)[Y]
        dd = float(d @ d)
        if dd < 1e-8:
            out[lid] = ("unobservable", 0.0, 0.0)
            continue
        dp = off_lit(d)
        if float(dp @ dp) < DISTINCT_MIN ** 2 * dd:
            out[lid] = ("not needed", 0.0, 0.0)
            continue
        a = max(0.0, float(dp @ want) / float(dp @ dp))
        reach = np.abs(d) > 0.05 * np.abs(d).max()
        den = float((want[reach] ** 2).sum())
        expl = 1.0 - float(((want - a * dp)[reach] ** 2).sum()) / den if den > 1e-12 else 0.0
        asked = float(np.abs(a * d).max())
        verdict = "missing" if asked >= MISSING_CV and expl >= MISSING_EXPLAINED else "not needed"
        out[lid] = (verdict, asked, expl)
    return out


def control(lines, J):
    """Which radial interval each layer controls, from the Jacobian's luminance rows.

    Each band contributes BAND_WEIGHT's three rows (luminance, then two chroma
    differences); this reads the luminance row.  (Until D65 it read the second,
    a chroma row, as if it were G.)  A split band counts twice, once per
    template, so a flank that dominates the broad reading controls that band.
    """
    out, row = {}, 0
    names = list(CALIBRATED_LAYERS)
    nw = BAND_WEIGHT.shape[0]
    for fname, f in lines.fam.items():
        nb = len(f["bands"])
        Y = [np.abs(J[row:row + nw * nb].reshape(nb, nw, -1)[:, 0, :])]
        rr = [b["r"] for b in f["bands"]]
        row += nw * nb + (len(f["broad"]["M"]) if f["broad"] is not None else 0)
        ns = len(f["split"])
        if ns:
            Ys = np.abs(J[row:row + 2 * nw * ns].reshape(ns, 2, nw, -1)[:, :, 0, :])
            Y += [Ys[:, 0, :], Ys[:, 1, :]]
            rr += [b["r"] for b in f["split"]] * 2
            row += 2 * nw * ns
        Y = np.concatenate(Y, 0)
        tot = Y.sum(1) + 1e-12
        for lid in FAMILIES[fname]["layers"]:
            j = names.index(lid)
            share = Y[:, j] / tot
            rs = [r for r, sh in zip(rr, share) if sh >= 0.5]
            out[lid] = (fname, (min(rs), max(rs)) if rs else None)
    return out


def scale(layer, k):
    """Scale a layer's light by k, hue kept: its basis amounts and the colour."""
    import fit_photometry as FP
    wc = [float(layer.get(c, 0.0)) * k for c in CHANNELS]
    for c, v in zip(CHANNELS, wc):
        if c == "teal" and c not in layer:
            continue    # a cone layer is not given a teal amount by a scale
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
        ts, ms = lines.target[name]["split"], meas[name]["split"]
        if len(ts):
            print("    %-17s split r %g-%g: narrow Y-gain %.2f, broad Y-gain %.2f"
                  % ("", lines.fam[name]["split"][0]["r"] - 4, lines.fam[name]["split"][-1]["r"] + 4,
                     gain(ms[:, 0] @ LUMA, ts[:, 0] @ LUMA), gain(ms[:, 1] @ LUMA, ts[:, 1] @ LUMA)))


def calibrate(params_path, ref, rounds=8, verbose=True, lines=None, stack=None):
    """Calibrate every family jointly; returns (worst, corrections) of the SAVED file.

    `lines` and `stack` may be passed in to share their set-up between runs.
    A supplied stack is REFRESHED to this file before it is used (Stack.refresh):
    a layer whose coverage fingerprint differs -- a moved or reshaped ray, a
    changed blur -- is re-rendered, a colour-only difference costs nothing, and
    a stack for another layer list or crop is replaced.  The caller's stack is
    updated in place, so it stays valid for the file it was last used on.
    """
    params = json.load(open(params_path))
    lines = lines if lines is not None else Lines(ref)
    if stack is None or not stack.matches(params, lines.box):
        stack = Stack(params, lines.box)
    else:
        changed = stack.refresh(params)
        if verbose and changed:
            print("  stack: re-rendered %d layer(s) whose geometry changed: %s"
                  % (len(changed), ", ".join(changed)))
    by_id = {L["id"]: L for L in params["layers"]}
    first = None
    # A dark ray is judged BEFORE anything is solved.  The solve cannot move a
    # dark layer (a scale of nothing is nothing), so it pushes that layer's
    # light onto its lit neighbours and saves the result (D66 review).  If the
    # reference has the ray, stop here and fail, leaving the file untouched.
    if any(is_dark(stack, j) for j in range(len(CALIBRATED_LAYERS))):
        meas0 = lines.measure(render_full(params))
        corr0, J0 = correction(lines, stack, meas0)
        dark0 = dark_report(lines, stack, meas0, J0)
        if any(v[0] == "missing" for v in dark0.values()):
            if verbose:
                print("  a dark ray the reference has was found BEFORE solving: nothing was solved "
                      "and %s is unchanged" % os.path.basename(params_path))
            return _verdict(lines, meas0, corr0, J0, dark0, None, params_path, verbose)
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
    # This is deliberate and includes the rounding scale() applies when it saves
    # (basis amounts to 1e-6, colours to 0.01 cv): the convergence verdict is
    # about the colours that will be rendered, not the solver's floats.  That
    # rounding moves a band by well under 0.01 cv, far inside TOL (D65 review).
    img = render_full(json.load(open(params_path)))
    meas = lines.measure(img)
    corr, J = correction(lines, stack, meas)
    # A layer with no light has a zero Jacobian column, which correction()
    # reads as "needs nothing"; ask the reference instead (dark_report).
    return _verdict(lines, meas, corr, J, dark_report(lines, stack, meas, J), first,
                    params_path, verbose)


def _verdict(lines, meas, corr, J, dark, first, params_path, verbose):
    """(worst, corrections) of a verified state; a MISSING layer's correction is
    unbounded (inf), so the calibration fails."""
    corr = np.array(corr, dtype=float)
    for lid, (verdict, _asked, _expl) in dark.items():
        if verdict == "missing":
            corr[list(CALIBRATED_LAYERS).index(lid)] = np.inf
    worst = float(np.abs(np.log(np.clip(corr, 1e-3, None))).max() / TOL)
    if verbose:
        report(lines, meas, "verified (full render of %s)" % os.path.basename(params_path))
        ctl = control(lines, first if first is not None else J)
        for lid, c in zip(CALIBRATED_LAYERS, corr):
            fam, span = ctl[lid]
            if lid in dark:
                verdict, asked, expl = dark[lid]
                print("    %-15s %-17s HAS NO LIGHT: %s (beyond what its lit neighbours can supply, "
                      "the reference asks %.1f cv of it, explaining %.2f of the residual where it "
                      "reaches)" % (lid, fam, verdict.upper(), asked, expl))
                continue
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
    worst, corr = calibrate(a.params, ref, rounds=a.rounds)
    missing = [lid for lid, c in corr.items() if np.isinf(c)]
    status = "converged" if worst <= 1.0 else "NOT converged"
    if missing:
        print("  NOT converged: %s %s NO LIGHT where the reference has it (MISSING); a scale "
              "cannot create light -- restore %s colour from the last calibrated params, then "
              "calibrate again (tools/fit_photometry.py --fit-rays can fit a colour from zero, but "
              "it answers the whole-image question, not the ray's)"
              % (", ".join(missing), "has" if len(missing) == 1 else "have",
                 "its" if len(missing) == 1 else "their"))
    else:
        print("  %s: worst remaining correction %.2f of its tolerance (TOL %.2f in ln)"
              % (status, worst, TOL))
    print("wrote", a.params)
    # The exit status is the whole point of the verification pass: corrections
    # computed on the way are already saved, so a caller that only looked at the
    # file could not tell a calibrated state from an uncalibrated one.
    if missing:
        print("  FAILED: a calibrated ray is missing; the saved parameters are NOT calibrated")
        return 1
    if worst > 1.0:
        print("  FAILED: calibration did not converge; the saved parameters are NOT "
              "calibrated -- re-run with a larger --rounds")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
