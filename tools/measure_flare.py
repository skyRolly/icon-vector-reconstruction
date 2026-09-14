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
#: composite then measures.  They differ: the rendered chord-excess FWHM comes
#: out about 14% narrow on the upper left and 5% wide on the lower left, because
#: the excess is read against a background the other layers also shape.  So each
#: is calibrated closed-loop against `tools/ray_report.py`, the same way the
#: amplitudes are, and the measured targets are 10.6, 8.3, 3.9 and 4.6 px.
RAY_GEOMETRY = {
    "flare_ray_a": (113.6, 12.3, 12.0, 1.00, 132.0, 0.49),   # upper-left
    "flare_ray_b": (249.7,  7.9,  8.0, 1.25, 110.0, 0.60),   # lower-left
    # The right-hand pair runs much further out than the left.  An angular
    # high-pass -- a moving average 24 px of arc wide subtracted from the
    # annulus, which removes a smooth background of any curvature and leaves
    # only narrow structure -- finds the reference still carrying 1-2.8 counts
    # at theta 45.6 out to r = 230, and 2-3.6 counts at theta 327.8 out to
    # r = 170, where a len of 105 and 112 had both died by r = 110.
    "flare_ray_e": (45.6,   4.35, 4.0, 1.30, 215.0, 0.28),   # upper-right
    "flare_ray_c": (327.8,  4.9,  4.0, 1.60, 185.0, 0.32),   # lower-right
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
    for lid, (th, fwhm, h, sp, ln, pk) in RAY_GEOMETRY.items():
        L = by_id[lid]
        sb = blur_for(fwhm, h)
        L.update(rot=-th, height=h, blur=round(sb, 4), spread=sp, len=ln, peak_at=pk)
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

    with tempfile.TemporaryDirectory() as work:
        for it in range(a.rounds):
            img = render(a.params, work)
            params = json.load(open(a.params))
            by_id = {L["id"]: L for L in params["layers"]}
            cur = ray_peaks(img, dmin)
            bits, worst = [], 0.0
            for name, lid in RAY_LAYER.items():
                if lid not in by_id:
                    continue
                ratio = target[name] / max(cur[name], 1e-3)
                worst = max(worst, abs(math.log(max(ratio, 1e-3))) / 0.06)
                scale(by_id[lid], float(np.clip(ratio ** 0.8, 0.33, 3.0)))
                bits.append("%s %.2f/%.2f" % (name[0] + name.split("-")[1][0],
                                              cur[name], target[name]))
            for lid, m in sectors.items():
                if lid not in by_id or not m.any():
                    continue
                err = float((img - ref)[m].mean())
                lvl = max(float(img[m].mean()), 1.0)
                head = max(1.0 - lvl / 255.0, 0.05)
                here = max(float(np.mean(by_id[lid]["color"])), 0.5)
                worst = max(worst, abs(err) / 0.4)
                scale(by_id[lid], float(np.clip(1.0 + (-err) / (here * head), 0.5, 2.0)))
                bits.append("%s %+.2f" % (lid[-2:], err))
            print("  round %d: %s" % (it, "  ".join(bits)))
            if worst <= 1.0:
                print("  converged")
                break
            json.dump(params, open(a.params, "w"), indent=1, sort_keys=True)
    print("wrote", a.params)
    return 0


if __name__ == "__main__":
    sys.exit(main())
