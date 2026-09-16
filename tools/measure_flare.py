#!/usr/bin/env python3
"""Set the flare's rays and flanks from measurement rather than from the fit.

    python3 tools/measure_flare.py [--params src/params.json] [--geometry]

Two jobs, and the second is the one that has to be repeated whenever anything
under the flare changes:

  * `--geometry` writes each ray's measured angle and width into its layer, and
    inserts the two broad flank layers if they are absent. Widths go in through
    the primitive's own optics -- a slab of height h blurred by sigma_b has
    sigma_eff^2 = sigma_b^2 + h^2/12 -- so (height, blur) is determined once the
    measured FWHM is fixed. This is a one-time structural edit; see D26.

  * always, the amplitudes. Each ray's colour is scaled until its chord-excess
    peak matches the reference's, and each flank's until the mean signed error
    over its own angular sector reaches zero. Screen compositing is not linear
    in a layer's amplitude -- a ray over a background of luminance b contributes
    about (1 - b) of what it would over black -- so this measures, scales and
    re-measures rather than solving once.

Why the amplitudes are not left to `tools/fit_photometry.py`: that objective is
a weighted error over the whole image, and a ray is a few code values over a few
hundred pixels. Measured, the fit leaves the lower-left and upper-right rays 2.3
and 2.4 times too bright and the lower-right 3.9 times too dim. That is not a
defect in the fit; it is a question the fit was never asked. The intended order
is geometry, then these amplitudes, then `fit(free=...)` over the bloom with
these layers held out, then these amplitudes again -- because the bloom fit
moves the background the peaks were measured against.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ray_report as RR  # noqa: E402

#: ray layer -> (theta, measured FWHM in px, slab height, spread, len, peak_at).
#: The angles and widths are D26's; the right-hand pair is at 45.6 and 327.8
#: degrees, not the 32 and 310 an earlier pass reported, and is 4-5 px wide
#: against the left pair's 8-11 -- they are not mirror images.
#: The second number is the width the SLAB is built to, not the width the
#: composite then measures; each is calibrated closed-loop against
#: `tools/ray_report.py`.
#:
#: THIS IS THE GEOMETRY OF RECORD, not a historical starting point. `--geometry`
#: writes it into the params, so a stale entry here silently reverts shipped
#: work -- and did: this table once held 45.6/215 and 327.8/185 for the right
#: pair after both had been superseded, so running `--geometry` would have
#: undone an axis correction and re-lengthened a ray that measurement had
#: shortened. `tools/test_pipeline.py` now asserts that this table and
#: `src/params.json` agree, so it cannot drift again without a check failing.
#:
#: The angles carry real uncertainty and are NOT known to the decimal place
#: printed. Measured by matched filter with an injection-recovery null, the
#: lower-right axis is 328.0 +- 0.8 degrees -- an interval that does not separate
#: 327.8 from 328.35, and an earlier claim of +-0.15 was about five times too
#: tight. The upper-right is 44.9 +- 0.4. The reference's rays are asymmetric
#: (the lower-right has a counter-clockwise shoulder, FWHM 7.3-10.1 px against
#: the render's symmetric 5.4-6.1), so six reasonable definitions of "centre"
#: disagree by 1.2-1.7 px and no axis here is defined to better than about a
#: degree. The values below are the centre of the supported range, not a claim
#: of precision.
#: dx, dy are part of this table because the table is the geometry OF RECORD and
#: they are geometry: `flare_ray_a` carries (-4.783, +2.090) and `flare_ray_c`
#: (+1.581, -2.550), which are the measured offsets of those rays' origins from
#: the flare centre.  They were held only in `src/params.json`, so --geometry
#: could not recreate them and `test_pipeline`'s drift check could not police
#: them -- the check asserted six numbers per ray and silently ignored the two
#: that place it.  Zero means "on the flare centre", and a zero is written by
#: REMOVING the key rather than setting it, so the params stay as small as the
#: model is.
RAY_GEOMETRY = {
    # Upper-left: the reference's ray is NOT parallel to the rendered one.  Over
    # 39 estimator variants the transverse centre difference fits
    # Delta = a + b*r with b = -3.7 to -8.9 deg (median -6.5) and a = +1.8 to
    # +7.6 px (median +5.2); a straight line beat a pure translation in 39 of 39,
    # median sum-of-squares ratio 0.09.  a and b are strongly anti-correlated, so
    # the defensible statement is the Delta(r) curve and not either alone.  The
    # rotation lives here; the +5.22 px offset along the normal is the layer's
    # own dx/dy, which the builder supports.  len 132 -> 100 and height 12 -> 9
    # because beyond r 70 the ray carried 1.8-3.0x too much light and reached too
    # far: the reference is at 0.29 of its peak by r 100 where the model held
    # 0.67.  peak_at 0.62 keeps the longitudinal peak at r = 62.
    "flare_ray_a": (107.1, 12.3,  9.0, 1.00, 100.0, 0.62, -4.783, 2.09),   # upper-left
    # Lower-left: too SHORT.  Bias-calibrated peak ratios render/reference run
    # 1.18/1.07/0.92/0.33 at r 76/88/100/112 -- the reference is still at half its
    # peak where a len of 110 has gone out.  124 is inside the defensible 118-128;
    # a trial at 130 overshot the outermost band and moved flare r<110 the wrong
    # way.  peak_at 0.532 keeps the longitudinal peak near r = 66.  Its angle is
    # also about +4.5 deg out with a compensating -7 px offset, but that is worth
    # only 3.5% of the sector error and is recorded rather than applied.
    "flare_ray_b": (249.7,  7.9,  8.0, 1.25, 124.0, 0.532, 0.0, 0.0),  # lower-left
    # Upper-right: axis 44.9 +- 0.4.  45.6, which tools/ray_report.py scans at,
    # is excluded at about 6 sigma: the reference's line lies -0.42 +- 0.28 px
    # from the 44.9 axis over r 65-145 across 15 analysis choices.  It ends at
    # r = 140 +- 15, so len 150 is right and anything at or beyond 170 is
    # excluded; the earlier "a continuation past r 150 is bounded at 11% of the
    # amplitude inside r 120" was too strong and the supported bound is 35-45%.
    # fwhm 4.35 -> 10.0 and height 4.0 -> 8.0: the reference's transverse FWHM is
    # 10.0 px (left half-width 6.0, right 4.0) against the render's 5.50, and its
    # broad wings survive all eight matched nulls -- the same cell at theta -14
    # and -20, and four along-ridge placements at +-200/+-300 px, all read
    # |values| <= 0.6 cv where the ray holds 1.2-1.9 cv at |s| 4.5-6.
    "flare_ray_e": (44.9,  10.0,  8.0, 1.30, 150.0, 0.28, 0.0, 0.0),   # upper-right
    # Lower-right: direction 327.3-328.1 and NOT resolvable further.  An earlier
    # note here said the reference's line and the render's are "PARALLEL
    # (328.18 +- 0.21 against 328.40)"; that precision was not supported.  The
    # two available criteria disagree inside the interval -- a transverse-position
    # matched filter prefers 327.2-327.5, corridor pixel error prefers
    # 327.8-328.1 -- and a residual -0.78 deg rotation is favoured only by a wide
    # estimator (2.9 sigma) that a narrow one does not reproduce (-0.28 +- 0.34).
    # So rot stays at 328.1 and the angle is left alone until the width is right.
    # The 3 px dx/dy translation is CONFIRMED and must not be revisited: removing
    # it costs +0.42 corridor MAE and pushes the position residual to
    # +1.58 +- 0.19 px, and the two criteria bracket the true offset at
    # 1.2 +- 0.4 px where the shipped value sits at 1.62.
    # fwhm 4.9 -> 7.4 and height 4.85 -> 7.0 because this is a REDISTRIBUTION
    # error, not an amplitude one: stacked over r 55-140 the reference and the
    # render carry equal flux (49.2 against 53.1 cv.px) but the render's core is
    # too bright and too narrow (peak 7.41 against 5.97) and lacks the skirt,
    # which is strongest on the counter-clockwise side.  The naive narrow-template
    # reading says the ray is 2-3x too bright at r 95-150 and should be
    # SHORTENED; that reading is an artefact of the template and shortening makes
    # the picture worse.  Measured extent 165 +- 20, so len 185 is at the upper
    # edge of what the data allows and must not be increased.
        "flare_ray_c": (328.1,  7.4,  7.0,  1.90, 185.0, 0.32, 1.5809, -2.5497),  # lower-right
}
#: ray name in tools/ray_report.py -> the layer that carries it
RAY_LAYER = {"upper-left": "flare_ray_a", "lower-left": "flare_ray_b",
             "upper-right": "flare_ray_e", "lower-right": "flare_ray_c"}
#: flank layer -> the angular sector whose signed error it exists to zero
FLANK_SECTOR = {"flare_flank_ul": (100.0, 140.0), "flare_flank_dl": (205.0, 262.0)}
FLANK_RADII = (20.0, 80.0)
CHANNELS = ("white", "cyan", "blue")

FLANKS = [
    {"id": "flare_flank_dl", "kind": "ray", "rot": -234.0, "height": 30.0,
     "spread": 1.7, "len": 110.0, "peak_at": 0.20, "blur": 6.0,
     "note": ("the lower-left ray is a sharp spike on a broad fan; this is the fan, "
              "found as the angular deficit left when the ray was narrowed to its "
              "measured 8.3 px width -- theta 210-260, peaking 13.5 cv at 225"),
     "bounds": {"blur": [3.0, 14.0], "height": [12.0, 55.0], "len": [80.0, 190.0],
                "peak_at": [0.12, 0.6], "rot": [-252.0, -216.0], "spread": [1.0, 4.0]},
     "color": [0.0, 18.0, 26.0], "white": 0.0, "cyan": 0.07, "blue": 0.03},
    {"id": "flare_flank_ul", "kind": "ray", "rot": -118.0, "height": 22.0,
     "spread": 2.0, "len": 110.0, "peak_at": 0.20, "blur": 6.0,
     "note": ("the upper-left ray's fan, the companion to its 10.6 px spike; found "
              "the same way and second, which is what makes the pair a decomposition "
              "rather than a patch"),
     "bounds": {"blur": [3.0, 14.0], "height": [10.0, 45.0], "len": [80.0, 190.0],
                "peak_at": [0.12, 0.6], "rot": [-136.0, -100.0], "spread": [1.0, 4.0]},
     "color": [0.0, 16.0, 22.0], "white": 0.0, "cyan": 0.06, "blue": 0.025},
]


def blur_for(fwhm, h):
    s2 = (fwhm / 2.355) ** 2 - h * h / 12.0
    if s2 <= 0:
        raise SystemExit("a slab of height %.1f already exceeds FWHM %.1f" % (h, fwhm))
    return math.sqrt(s2)


def apply_geometry(params):
    by_id = {L["id"]: L for L in params["layers"]}
    for lid, (th, fwhm, h, sp, ln, pk, dx, dy) in RAY_GEOMETRY.items():
        L = by_id[lid]
        sb = blur_for(fwhm, h)
        L.update(rot=-th, height=h, blur=round(sb, 4), spread=sp, len=ln, peak_at=pk)
        for key, val in (("dx", dx), ("dy", dy)):
            if val:
                L[key] = val
            else:
                L.pop(key, None)
        b = L.setdefault("bounds", {})
        # The right-hand rays are 3.9 and 4.6 px across and no (h >= 6,
        # blur >= 2) pair can make either: blur 2 alone is 4.7 px of FWHM.
        b.update(blur=[0.6, 10.0], height=[3.0, 40.0], spread=[1.0, 3.0],
                 rot=[-th - 6.0, -th + 6.0],
                 len=[max(60.0, ln - 45.0), ln + 60.0], peak_at=[0.2, 0.75])
        print("  %-14s theta %6.1f  FWHM %4.1f px (h %.1f, blur %.2f)"
              % (lid, th, 2.355 * math.sqrt(sb * sb + h * h / 12.0), h, sb))
    ids = [L["id"] for L in params["layers"]]
    at = ids.index("flare_ray_b")
    for fl in FLANKS:
        if fl["id"] not in ids:
            params["layers"].insert(at, json.loads(json.dumps(fl)))
            print("  inserted %s" % fl["id"])


def scale(layer, k):
    layer["color"] = [round(float(v) * k, 5) for v in layer["color"]]
    for ch in CHANNELS:
        if ch in layer:
            layer[ch] = round(float(layer[ch]) * k, 6)


def render(params_path, work):
    svg = os.path.join(work, "m.svg")
    png = os.path.join(work, "m.png")
    subprocess.run([sys.executable, os.path.join(ROOT, "src", "build_svg.py"),
                    "--params", params_path, "--out", svg], check=True, capture_output=True)
    subprocess.run([sys.executable, os.path.join(HERE, "render.py"), svg, png],
                   check=True, capture_output=True)
    return RR.load(png).mean(2)


def ray_peaks(img, dmin):
    out = {}
    for name, th in RR.RAYS:
        prof = [p for p in RR.ray_profile(img, dmin, th)
                if p and np.isfinite(p[2]) and p[2] > 0]
        out[name] = float(np.mean([p[0] for p in prof])) if prof else 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--geometry", action="store_true",
                    help="also write the measured ray geometry and insert the flanks")
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--rays-only", action="store_true",
                    help="pin the four narrow rays and leave the broad flanks alone "
                         "(their amplitudes come from an angular measurement that a "
                         "sector mean would overwrite)")
    a = ap.parse_args()

    params = json.load(open(a.params))
    if a.geometry:
        print("geometry:")
        apply_geometry(params)
        json.dump(params, open(a.params, "w"), indent=1, sort_keys=True)

    ref = RR.load(a.reference).mean(2)
    dmin = RR.ridge_distance(ref.shape)
    target = ray_peaks(ref, dmin)
    print("reference ray peaks: " + "  ".join("%s %.2f" % (k, v) for k, v in target.items()))

    h, w = ref.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(xx - RR.CORE[0], yy - RR.CORE[1])
    th = np.degrees(np.arctan2(-(yy - RR.CORE[1]), xx - RR.CORE[0])) % 360.0
    ring = (dmin > RR.RIDGE_CLEAR) & (rr >= FLANK_RADII[0]) & (rr < FLANK_RADII[1])
    sectors = {lid: ring & (th >= lo) & (th < hi) for lid, (lo, hi) in FLANK_SECTOR.items()}

    def assess(img, by_id, apply=True):
        """Measure the render against every target; optionally apply the scaling.

        Returns (worst, report) where `worst` is the largest deviation expressed
        in units of its own tolerance, so `worst <= 1.0` means every target is
        met.  With apply=False nothing is written, which is what makes a final
        verification pass possible.
        """
        bits, worst = [], 0.0
        cur = ray_peaks(img, dmin)
        for name, lid in RAY_LAYER.items():
            if lid not in by_id:
                continue
            ratio = target[name] / max(cur[name], 1e-3)
            worst = max(worst, abs(math.log(max(ratio, 1e-3))) / 0.06)
            if apply:
                scale(by_id[lid], float(np.clip(ratio ** 0.8, 0.33, 3.0)))
            bits.append("%s %.2f/%.2f" % (name[0] + name.split("-")[1][0],
                                          cur[name], target[name]))
        for lid, m in sectors.items():
            if a.rays_only or lid not in by_id or not m.any():
                continue
            err = float((img - ref)[m].mean())
            lvl = max(float(img[m].mean()), 1.0)
            head = max(1.0 - lvl / 255.0, 0.05)
            here = max(float(np.mean(by_id[lid]["color"])), 0.5)
            worst = max(worst, abs(err) / 0.4)
            if apply:
                scale(by_id[lid], float(np.clip(1.0 + (-err) / (here * head), 0.5, 2.0)))
            bits.append("%s %+.2f" % (lid[-2:], err))
        return worst, "  ".join(bits)

    with tempfile.TemporaryDirectory() as work:
        converged = False
        it = -1                      # so --rounds 0 reports honestly rather than raising
        for it in range(a.rounds):
            img = render(a.params, work)
            params = json.load(open(a.params))
            by_id = {L["id"]: L for L in params["layers"]}
            worst, report = assess(img, by_id)
            print("  round %d: %s" % (it, report))
            if worst <= 1.0:
                # The file already renders to this state, so it is left alone --
                # writing the round's own scaling here would save something that
                # has never been rendered.
                converged = True
                break
            json.dump(params, open(a.params, "w"), indent=1, sort_keys=True)

        # Whatever happened above, the file on disk is what ships, so measure
        # THAT.  Without this the non-converged path saved a state that was
        # never rendered and reported nothing about it, and the converged path
        # could not be told apart from a stale one.
        img = render(a.params, work)
        params = json.load(open(a.params))
        final, report = assess(img, {L["id"]: L for L in params["layers"]}, apply=False)
        status = "converged" if final <= 1.0 else "NOT converged"
        print("  verified (rendered from %s): %s" % (os.path.basename(a.params), report))
        print("  %s: worst deviation %.2f of its tolerance after %d round(s)"
              % (status, final, it + 1))
        if not converged and final > 1.0:
            print("  note: the round budget ran out; re-run with a larger --rounds")
    print("wrote", a.params)
    # The exit status is the whole point of the verification pass above: any
    # corrections computed on the way are already saved, so a caller that only
    # looked at the file could not tell a calibrated state from an uncalibrated
    # one. Returning 0 here regardless meant automation accepted parameters that
    # had never met their tolerance.
    if final > 1.0:
        print("  FAILED: calibration did not converge (worst deviation %.2f of "
              "its tolerance); the saved parameters are NOT calibrated" % final)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
