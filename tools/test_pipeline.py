#!/usr/bin/env python3
"""Regression checks for the optimisation pipeline's correctness.

These guard the properties that, when they broke, made optimisation results
untrustworthy without changing any metric: a trial was scored against artwork
that the parameters no longer described, or a parameter was never evaluated at
all.  Run after any change to tools/optimize.py or src/build_svg.py.

    python3 tools/test_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import build_svg  # noqa: E402
import optimize as O  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    print("%-4s %s%s" % ("PASS" if ok else "FAIL", name, ("  -- " + detail) if detail else ""))
    if not ok:
        FAIL.append(name)


def centroid(a, thresh=0.02):
    m = a > thresh
    if not m.any():
        return None
    ys, xs = np.nonzero(m)
    w = a[m]
    return float((xs * w).sum() / w.sum()), float((ys * w).sum() / w.sum())


def main():
    params = json.load(open(os.path.join(ROOT, "src", "params.json")))

    # ---- 1. every layer that reads the global flare centre actually moves --
    deps = build_svg.flare_dependent_layers(params)
    check("flare-dependent layers are discovered from the builder",
          set(deps) >= {L["id"] for L in params["layers"]
                        if L["kind"] in build_svg.FLARE_ANCHORED_KINDS
                        and "cx" not in L and "cy" not in L},
          "found %s" % deps)

    spec = [s for s in O.geometry_specs(params) if s["path"] == "flare/cx"][0]
    check("flare/cx declares every dependent layer",
          set(spec["affects"]) == set(deps),
          "declared %s" % sorted(spec["affects"]))

    obj = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1)
    before = {lid: obj.basis(params, lid).copy() for lid in deps}
    O.set_path(params, "flare/cx", float(O.get_path(params, "flare/cx")) + 6.0)
    obj.invalidate(spec["affects"])
    moved, stuck = [], []
    for lid in deps:
        after = obj.basis(params, lid)
        c0, c1 = centroid(before[lid]), centroid(after)
        dx = (c1[0] - c0[0]) if (c0 and c1) else 0.0
        (moved if dx > 1.0 else stuck).append("%s(dx=%+.2f)" % (lid, dx))
    check("moving flare/cx by 6 px moves every dependent layer",
          not stuck, "stuck: %s" % ", ".join(stuck) if stuck else "moved: %s" % ", ".join(moved))
    O.set_path(params, "flare/cx", float(O.get_path(params, "flare/cx")) - 6.0)

    # ---- 2. the cache cannot serve a stale field -------------------------- #
    a0 = obj.basis(params, deps[0]).copy()
    O.set_path(params, "flare/cx", float(O.get_path(params, "flare/cx")) + 9.0)
    a1 = obj.basis(params, deps[0])          # deliberately WITHOUT invalidate()
    check("content-addressed cache re-renders without an explicit invalidate",
          float(np.abs(a1 - a0).max()) > 0.01,
          "max delta %.4f" % float(np.abs(a1 - a0).max()))
    O.set_path(params, "flare/cx", float(O.get_path(params, "flare/cx")) - 9.0)

    # ---- 3. every generated spec's interval contains its current value ---- #
    allspecs = (O.layer_specs(params) + O.taper_specs(params)
                + O.geometry_specs(params) + O.field_specs(params))
    bad = [(s["path"], float(O.get_path(params, s["path"])), s["lo"], s["hi"])
           for s in allspecs if not (s["lo"] <= float(O.get_path(params, s["path"])) <= s["hi"])]
    check("every search interval contains the current value", not bad,
          "out of range: %s" % bad)

    # ---- 4. nested and anisotropic parameters are not silently omitted ---- #
    fpaths = {s["path"] for s in O.field_specs(params)}
    radial_canvas = [(i, L) for i, L in enumerate(params["layers"])
                     if isinstance(L.get("paint"), dict) and L["paint"].get("kind") == "radial"
                     and L["kind"] in ("canvas", "field_radial", "radial")]
    missing = [L["id"] for i, L in radial_canvas if "layers/%d/paint/cx" % i not in fpaths]
    check("radial gradient centres stored under paint/ are optimisable", not missing,
          "missing: %s" % missing)

    # A list-valued parameter must yield one spec per component, each with its
    # own interval.  The shipped artwork happens to state the streak's
    # cross-section as a scalar `sigma_y` and derive the blur pair from it, so
    # this is checked against a probe layer as well -- otherwise the check
    # passes vacuously the moment the artwork stops using a list.
    def aniso_missing(pp):
        spaths = {s["path"] for s in O.layer_specs(pp)}
        aniso = [(i, L) for i, L in enumerate(pp["layers"]) if isinstance(L.get("blur"), list)]
        bad = [L["id"] for i, L in aniso
               if not all("layers/%d/blur/%d" % (i, j) in spaths for j in range(len(L["blur"])))]
        return bad, len(aniso), spaths

    missing, n_real, _ = aniso_missing(params)
    probe = json.loads(json.dumps(params))
    probe["layers"].append({"id": "probe_aniso", "kind": "streak", "half_len": 100.0,
                            "sigma_y": 2.0, "blur": [1.0, 3.0],
                            "profile": {"kind": "exp", "scale": 0.2},
                            "bounds": {"blur": [[0.0, 3.0], [0.5, 8.0]]}})
    pmissing, n_probe, pspaths = aniso_missing(probe)
    i = len(probe["layers"]) - 1
    intervals = {s["path"]: (s["lo"], s["hi"]) for s in O.layer_specs(probe)}
    per_component = (intervals.get("layers/%d/blur/0" % i) == (0.0, 3.0)
                     and intervals.get("layers/%d/blur/1" % i) == (0.5, 8.0))
    check("anisotropic blur components are optimisable",
          not missing and not pmissing and per_component,
          "artwork missing %s (%d list-valued layers); probe missing %s; "
          "per-component intervals %s"
          % (missing, n_real, pmissing, "kept" if per_component else "COLLAPSED"))

    # ---- 5. the fitting weight really does police the two regions -------- #
    import fit_photometry as FP
    import regions as RG
    from PIL import Image as _Image
    tgt = np.asarray(_Image.open(os.path.join(ROOT, "reference.png")).convert("RGB"))
    tgt = tgt.astype(np.float32) / 255.0
    W = FP.make_weight(tgt)
    W0 = FP.make_weight(tgt, emphasis=False)
    bins = RG.weight_cells(tgt.shape)
    # What matters is that no cell of the glow's cross-section is invisible to
    # the fit.  The objective is a weighted sum of squares, so the test is what
    # a 1% relative error in a cell actually costs: sum(w * (0.01*L)^2) over
    # the cell.  Equal cost across cells is the property; equal per-pixel
    # weight or equal weight mass would both be equalising the wrong thing,
    # since the cells differ 250x in area and 6x in brightness.  Cells, not
    # distance-only bins: pooling along the curve hid the tips, and the fit
    # drained them to 20-30% below the reference while every pooled bin still
    # looked fine.
    lum = tgt.mean(2)

    def bin_cost(weight):
        c = np.array([float((weight[c_[-1]] * (0.01 * lum[c_[-1]]) ** 2).sum()) for c_ in bins])
        return c / c.mean()

    cost, cost0 = bin_cost(W), bin_cost(W0)
    spread = float(cost.max() / cost.min())
    spread0 = float(cost0.max() / cost0.min())
    cov = np.zeros(tgt.shape[:2], bool)
    for c_ in bins:
        cov |= c_[-1]
    # The outermost along-curve band must be covered out to where the drawn
    # curves actually end: pooling over t hid it, and the fit then drained the
    # ends to 20-30% below the reference.  The interior corners, past the curve
    # ends, must be lifted too -- they were 30% too dark with no emphasis on
    # them at all.
    at = np.abs(RG.curve_frame(tgt.shape)[1])
    pcov = np.zeros(tgt.shape[:2], bool)
    for c_ in RG.profile_cells(tgt.shape):
        pcov |= c_[-1]
    tips = pcov & (at >= RG.PROFILE_T_BANDS[-1][0])
    dsig = RG.curve_frame(tgt.shape)[0]
    hh, ww = tgt.shape[:2]
    gy, gx = np.mgrid[0:hh, 0:ww]
    FR = RG.FRAME
    dfr = np.minimum(np.minimum(gx + 0.5 - FR["left"], FR["right"] - gx - 0.5),
                     np.minimum(gy + 0.5 - FR["top"], FR["bottom"] - gy - 0.5))
    corners = (RG.interior(tgt.shape, 12.0) & (dsig < -40) & (dfr < 100)
               & (np.minimum(np.abs(gx + 0.5 - FR["left"]), np.abs(gx + 0.5 - FR["right"])) < 230)
               & (np.minimum(np.abs(gy + 0.5 - FR["top"]), np.abs(gy + 0.5 - FR["bottom"])) < 230))
    corner_cov = float((cov & corners).sum() / max(corners.sum(), 1))
    flare_m = FP.region_masks(tgt.shape)["flare"]
    check("the fitting weight equalises the profile cells and lifts the flare",
          len(bins) >= 60 and spread < 3.0 and spread < spread0
          and tips.sum() > 20000 and W[cov].mean() > W0[cov].mean()
          and corner_cov > 0.9
          and W[flare_m].mean() > W0[flare_m].mean() * 1.5,
          "%d cells (%d px in the outermost along-curve band), cost of a 1%% error "
          "spread %.2fx (was %.2fx un-emphasised), region lift %.2fx, interior "
          "corners %.0f%% covered, flare %.2fx"
          % (len(bins), int(tips.sum()), spread, spread0,
             W[cov].mean() / W0[cov].mean(), 100 * corner_cov,
             W[flare_m].mean() / W0[flare_m].mean()))

    # ---- 6. the objective scores the same artwork the SVG rebuild emits --- #
    A = np.stack([obj.basis(params, L["id"]) for L in params["layers"]])
    an = FP.composite(A, FP.colors(FP.params_wc(params)), FP.normal_flags(params))
    import render as R
    import io
    from PIL import Image
    png = R.render_resvg_string(build_svg.build(params), 1024) if hasattr(R, "render_resvg_string") \
        else None
    if png is None:
        import resvg_py
        png = bytes(resvg_py.svg_to_bytes(svg_string=build_svg.build(params), width=1024, height=1024))
    real = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(np.float32) / 255.0
    d = float(np.abs(an - real).mean() * 255)
    check("objective composite matches the rebuilt SVG render", d < 1.0, "MAE %.4f code values" % d)

    print()
    if FAIL:
        print("%d check(s) failed: %s" % (len(FAIL), ", ".join(FAIL)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
