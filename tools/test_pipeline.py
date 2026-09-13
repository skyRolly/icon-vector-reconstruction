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
    A = np.stack([obj.basis(params, L["id"]) for L in params["layers"]])
    tgt = np.asarray(_Image.open(os.path.join(ROOT, "reference.png")).convert("RGB"))
    tgt = tgt.astype(np.float32) / 255.0
    W = FP.make_weight(tgt)
    W0 = FP.make_weight(tgt, emphasis=False)
    bins = RG.weight_cells(tgt.shape)
    # What matters is that no cell of the glow's cross-section is invisible to
    # the fit.  The cost below is computed the way `fit()` ACTUALLY computes it
    # -- residual times weight, then squared -- rather than the way the
    # weighting was once described.  That distinction is the whole point of
    # this check: while it charged `sum(w * r^2)` it passed at 2.3x spread
    # while the production objective `sum((w*r)^2)` was running at 183x, i.e.
    # the test validated a formula the code did not implement.
    # Cells, not distance-only bins: pooling along the curve hid the tips, and
    # the fit drained them to 20-30% below the reference while every pooled bin
    # still looked fine.
    lum = tgt.mean(2)

    def bin_cost(weight):
        """Cost the production objective charges for a uniform 1% relative error."""
        c = np.array([float(((weight[c_[-1]] * 0.01 * lum[c_[-1]]) ** 2).sum())
                      for c_ in bins])
        return c / c.mean()

    # And prove it is the production formula: reproduce `fit`'s own sse for a
    # known perturbation, from make_weight's output, to 1e-6 relative.
    rng = np.random.default_rng(7)
    pert = (rng.standard_normal(tgt.shape).astype(np.float32) * 0.01)
    sse_here = float((((pert) * W[..., None]) ** 2).sum())
    sse_fit = FP.weighted_sse(pert, W)
    check("the regression check scores the same objective fit() minimises",
          abs(sse_here - sse_fit) <= 1e-6 * max(sse_fit, 1e-12),
          "check %.8g vs fit %.8g" % (sse_here, sse_fit))

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
    fams = {}
    for c_ in bins:
        key = c_[0] if isinstance(c_[0], str) else ("profile" if len(c_) == 5 else "corner")
        fams.setdefault(key, 0)
        fams[key] += 1
    # every family must be present, and the cost of a 1% relative error must be
    # comparable across ALL of them - otherwise one region silently buys
    # accuracy from another, which is how the flare's comb and spokes came to
    # be missing while the global metric improved.
    ok_fams = set(fams) >= {"comb", "sector", "profile", "corner"}
    check("the fitting weight equalises the profile cells and lifts the flare",
          len(bins) >= 150 and ok_fams and spread < 6.0 and spread < spread0
          and tips.sum() > 20000 and W[cov].mean() > W0[cov].mean()
          and corner_cov > 0.9
          and W[flare_m].mean() > W0[flare_m].mean() * 1.4,
          "%d cells %s (%d px in the outermost along-curve band), cost of a 1%% error "
          "spread %.2fx (was %.2fx un-emphasised), region lift %.2fx, interior "
          "corners %.0f%% covered, flare %.2fx"
          % (len(bins), fams, int(tips.sum()), spread, spread0,
             W[cov].mean() / W0[cov].mean(), 100 * corner_cov,
             W[flare_m].mean() / W0[flare_m].mean()))

    # ---- 5b. the Jacobian must match the objective it differentiates ------ #
    # A layer whose fitted colour saturates in a channel has zero derivative
    # in that channel.  Ignoring the clip made arc_core's analytic gradient
    # 1.6x too large; LM's line search hid it.
    sub = slice(None, None, 8)
    Asub = A[:, sub, sub]
    tsub = np.minimum(tgt, 254.4 / 255.0)[sub, sub]
    Wsub = FP.make_weight(tsub)
    WC = FP.params_wc(params)
    nfl = FP.normal_flags(params)
    worst = (0.0, None)
    for lid in ("arc_core", "arc_glow1", "frame_rim"):
        li = [k for k, L in enumerate(params["layers"]) if L["id"] == lid]
        if not li:
            continue
        li = li[0]
        for j in range(FP.NB):
            h = 1e-4
            wp, wm = WC.astype(np.float64).copy(), WC.astype(np.float64).copy()
            wp[li, j] += h
            wm[li, j] -= h
            def f(w):
                # float64 throughout: the central difference of a float32 sum
                # of 3e5 terms loses the signal to cancellation, which is what
                # made this check report 2.5% error on an exact derivative.
                M = FP.composite(Asub.astype(np.float64),
                                 FP.colors(w).astype(np.float64), nfl)
                e = (M - tsub.astype(np.float64)) * Wsub.astype(np.float64)[..., None]
                return float((e * e).sum())
            num = (f(wp) - f(wm)) / (2 * h)
            ana = FP.analytic_grad(Asub, tsub, WC, Wsub, nfl, li, j)
            den = max(abs(num), 1e-9)
            rel = abs(ana - num) / den
            if rel > worst[0]:
                worst = (rel, "%s/%s" % (lid, FP.COMPONENTS[j]))
    check("the analytic gradient matches the objective, clipped colours included",
          worst[0] < 0.02, "worst relative error %.4f at %s" % worst)

    # ---- 5b. the documentation names layers that actually exist ---------- #

    # Every layer id the docs mention in backticks must be in params.json, and
    # the deliverable's own metadata must be generated rather than remembered.
    # Both drifted for a whole iteration: the README claimed 28 layers and
    # ~68 KB against 29 and 74 KB, described "three blurred copies" of each
    # curve where the model ships six glow strokes, and named `arc_glow2b` as
    # "the one component offset outward" when `arc_glow1b` is offset outward
    # too -- while `arc_glow1b` and `corner_in_top` went unmentioned entirely.
    ids = {L["id"] for L in params["layers"]}
    # Names that look like layer ids but are not: parameters, functions, region
    # helpers, and builder kinds or layers the docs name *because* they were
    # rejected or removed -- `arc_field` and `arc_lens` are both recorded in
    # DECISIONS as things that are deliberately not in the model, and a record
    # of a rejection is not a claim that the thing exists.
    NOT_LAYERS = {"corner_model", "corner_r_blend", "corner_r_main",
                  "corner_blend_deg", "corner_note", "flare_dependent_layers",
                  "flare_cells", "field_grad_note", "arc_d", "arc_field",
                  "arc_lens", "arc_station", "flare_report", "field_specs",
                  "corner_cells", "flare_cx",
                  # built, measured, and NOT shipped -- the docs name these to
                  # record what was tested and rejected, which is not a claim
                  # that they are in the model (docs/DECISIONS.md D22)
                  "arc_glow1c", "flare_sat2", "flare_ray_up", "flare_ray_dn",
                  "flare_ray_dl", "lobe_field_left", "lobe_field_right"}
    import re as _re
    named, missing = set(), {}
    for doc in ("README.md", os.path.join("docs", "METHOD.md"),
                os.path.join("docs", "DECISIONS.md")):
        fp = os.path.join(ROOT, doc)
        if not os.path.exists(fp):
            continue
        for tok in _re.findall(r"`([a-z][a-z0-9_]*)`", open(fp).read()):
            if not tok.startswith(("arc_", "corner_", "field_", "flare_",
                                   "frame_", "exterior", "lobe_")):
                continue
            if tok in NOT_LAYERS:
                continue
            named.add(tok)
            if tok not in ids:
                missing.setdefault(tok, []).append(doc)
    check("every layer the docs name exists in params.json",
          not missing,
          "%d named, unknown: %s" % (len(named), ", ".join(
              "%s (%s)" % (k, v[0]) for k, v in sorted(missing.items())) or "none"))

    rd = os.path.join(ROOT, "README.md")
    rt = open(rd).read() if os.path.exists(rd) else ""
    gen = "<!-- DELIVERABLE:START -->" in rt
    stale = _re.search(r"\*\*Primary deliverable.{0,80}?(\d+) named", rt, _re.S)
    check("the deliverable's layer count and size are generated, not prose",
          gen and (stale is None or int(stale.group(1)) == len(ids)),
          "markers present: %s; states %s layers, params.json has %d"
          % (gen, stale.group(1) if stale else "n/a", len(ids)))

    # ---- 6. the objective scores the same artwork the SVG rebuild emits --- #

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

    # ---- 6b. isolation is valid where it is used -------------------------- #

    # A screen contribution under a later NORMAL-blended layer is not
    # recoverable by (ref - M)/(1 - M): the normal layer is an affine step, so
    # both `ref` and `M` have been through a map that the division does not
    # undo.  The shipped stack ends with two normal frame layers, so every
    # isolated arc-glow measurement near the rim went through this.  Synthetic
    # here, because then the answer is known exactly.
    import isolate as ISO
    Hs = Ws = 24
    Asyn = np.stack([np.full((Hs, Ws), 0.35, np.float32),
                     np.full((Hs, Ws), 0.55, np.float32),
                     np.zeros((Hs, Ws), np.float32)])
    Asyn[2][:, 10:] = 0.60
    Ksyn = np.array([[0.20, 0.45, 0.60], [0.50, 0.70, 0.90], [0.30, 0.32, 0.35]], np.float32)
    nfs = [False, False, True]
    refs = FP.composite(Asyn, Ksyn, nfs)
    f_true = Asyn[1][..., None] * Ksyn[1][None, None, :]
    keep = [0, 2]
    Ak, Kk, nfk = Asyn[keep], Ksyn[keep], [nfs[i] for i in keep]
    Msyn = FP.composite(Ak, Kk, nfk)
    f_old = np.clip((refs - Msyn) / np.maximum(1.0 - Msyn, 1e-4), 0.0, 1.0)
    p_pre, q_pre = ISO._affine_u(Ak, Kk, nfk, [0])
    p_post, q_post = ISO._affine_u(Ak, Kk, nfk, [1])
    f_new = np.clip(1.0 - ((1.0 - refs) - q_post) / p_post
                    / np.maximum(p_pre + q_pre, 1e-4), 0.0, 1.0)
    under = slice(10, Ws)
    e_new = float(np.abs(f_new[:, under] - f_true[:, under]).max())
    e_old = float(np.abs(f_old[:, under] - f_true[:, under]).max())
    e_free = float(np.abs(f_new[:, 0:10] - f_true[:, 0:10]).max())
    check("isolation recovers a screen contribution under a normal layer",
          e_new < 1e-5 and e_free < 1e-5 and e_old > 0.05,
          "corrected %.2e under the normal layer, %.2e clear of it; the old "
          "formula was off by %.3f" % (e_new, e_free, e_old))

    bad = None
    try:
        ISO.isolate(params, np.zeros((8, 8, 3), np.float32), ["frame"])
    except ISO.UnsupportedIsolation as exc:
        bad = str(exc)
    except Exception as exc:                                   # noqa: BLE001
        bad = "WRONG EXCEPTION: %r" % exc
    check("isolation refuses orderings its algebra cannot express",
          bad is not None and "normal-blended" in bad,
          (bad or "no exception raised")[:110])

    # ---- 6c. the profile weight belongs to the target it was built for ---- #

    # `_PROFILE_CACHE` keyed on the luminance SUM, and the weights come from
    # per-cell MEAN luminance: move a bright patch from one cell to another and
    # the sum is unchanged while the correct weights are not, so the second
    # target silently received the first one's.
    tgt_a = np.minimum(tgt, 254.4 / 255.0)[::4, ::4].copy()
    tgt_b = tgt_a.copy()
    src, dst = (slice(60, 80), slice(40, 60)), (slice(150, 170), slice(30, 50))
    hold = tgt_b[src].copy()
    tgt_b[src] = tgt_b[dst]
    tgt_b[dst] = hold
    Wa = FP.make_weight(tgt_a)
    Wb = FP.make_weight(tgt_b)
    Wa2 = FP.make_weight(tgt_a.copy())
    same_sum = abs(float(tgt_a.mean(2).sum()) - float(tgt_b.mean(2).sum())) < 1e-3
    check("the profile weight is keyed on the target, not on its luminance sum",
          same_sum and not np.array_equal(Wa, Wb) and np.array_equal(Wa, Wa2),
          "equal sums: %s; different layouts give different weights: %s; an "
          "identical target still reuses the cache: %s"
          % (same_sum, not np.array_equal(Wa, Wb), np.array_equal(Wa, Wa2)))

    # ---- 6d. a geometry trial is scored against an equivalent baseline ---- #

    # `evaluate(free=family)` re-fits that family inside the trial, while
    # `best_sse` was left by the previous accepted move, which re-fitted a
    # DIFFERENT family.  The trial then gets a colour refit the baseline never
    # received, and the refit's gain is credited to the geometry.  sweep() must
    # re-score the unchanged geometry under each new family's freedom first.
    calls = []
    real_eval = O.Objective.evaluate

    def spy(self, prms, fit_iters=None, stride=None, full=False, free=None):
        calls.append(tuple(free) if free is not None else "all")
        return real_eval(self, prms, fit_iters=fit_iters, stride=stride,
                         full=full, free=free)

    probe = json.loads(json.dumps(params))
    two = [sp for sp in O.layer_specs(probe)
           if sp["affects"] != "all" and sp["affects"][0].startswith("arc_")][:1]
    two += [sp for sp in O.layer_specs(probe)
            if sp["affects"] != "all" and sp["affects"][0].startswith("flare_")][:1]
    ok_bases = None
    if len(two) == 2:
        O.Objective.evaluate = spy
        try:
            obj = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1)
            O.sweep(obj, probe, two, log=lambda *a, **k: None)
        finally:
            O.Objective.evaluate = real_eval
        fams = [tuple(obj.families(probe, sp["affects"])) for sp in two]
        # every family that was searched must appear as a baseline evaluate
        # before any trial of that family
        ok_bases = True
        for fam in fams:
            if fam not in calls:
                ok_bases = False
        # and the two families must genuinely differ, or the test proves nothing
        ok_bases = ok_bases and fams[0] != fams[1]
    check("a geometry trial is scored against a baseline with the same colour freedom",
          bool(ok_bases),
          "%d evaluate() calls, %d distinct free-sets, both searched families "
          "re-baselined: %s" % (len(calls), len(set(calls)), ok_bases))

    # ---- 7. the lobe banding has not come back ---------------------------- #

    # The target is set by the reference, not by a taste for smoothness, and it
    # is two-sided: `banding_worst_dev` compares the render's *coherent*
    # cross-curve band-pass amplitude with the reference's own, and a render
    # with less of it than the reference fails as well as one with more --
    # which is what blurring the lobes until the stripes stop showing would
    # produce.  The two percentages are the along-curve-averaged profile error
    # in the two regions that have different causes (docs/DECISIONS.md D19).
    # The ceilings sit just above the shipped values so a regression trips.
    BAND_DEV_MAX = 2.00
    BAND_INTERIOR_MAX = 5.00
    BAND_RIDGE_MAX = 5.00
    import io as _io
    import contextlib as _cl
    import diagnose as _D
    bres = {}
    with _cl.redirect_stdout(_io.StringIO()):
        _D.band_report(_D.load(os.path.join(ROOT, "reference.png")),
                       (real * 255.0).astype(np.float64), bres)
    check("the lobe banding stays within the reference-calibrated target",
          bres["banding_worst_dev"] <= BAND_DEV_MAX
          and bres["banding_interior_pct"] <= BAND_INTERIOR_MAX
          and bres["banding_ridge_pct"] <= BAND_RIDGE_MAX,
          "coherent band-pass %.2fx of the reference (max %.2f, two-sided); "
          "profile error interior %.2f%% (max %.2f), ridge %.2f%% (max %.2f)"
          % (bres["banding_worst_dev"], BAND_DEV_MAX,
             bres["banding_interior_pct"], BAND_INTERIOR_MAX,
             bres["banding_ridge_pct"], BAND_RIDGE_MAX))

    print()
    if FAIL:
        print("%d check(s) failed: %s" % (len(FAIL), ", ".join(FAIL)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
