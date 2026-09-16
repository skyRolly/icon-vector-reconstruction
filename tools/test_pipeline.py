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
import regions  # noqa: E402

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

    # A layer that pins ONE coordinate still reads the global centre for the
    # other, so it still moves when that one moves.  The rule used to require
    # both to be absent, which silently excluded the partial case -- and the
    # check above cannot catch that, because it only asserts a superset.  All
    # four combinations, against the builder's own rule:
    probe = json.loads(json.dumps(params))
    kind = build_svg.FLARE_ANCHORED_KINDS[0]
    fl = probe["flare"]
    cases = {"both-global": {}, "local-cx": {"cx": fl["cx"] + 3.0},
             "local-cy": {"cy": fl["cy"] + 3.0},
             "both-local": {"cx": fl["cx"] + 3.0, "cy": fl["cy"] + 3.0}}
    probe["layers"] = [dict({"id": "probe_" + n, "kind": kind, "r": 40.0,
                             "color": [0, 40, 60], "white": 0.0, "cyan": 0.1,
                             "blue": 0.05, "profile": {"kind": "exp", "scale": 0.2}},
                            **ov) for n, ov in cases.items()]
    got = set(build_svg.flare_dependent_layers(probe))
    want = {"probe_both-global", "probe_local-cx", "probe_local-cy"}
    check("a layer that pins one coordinate still depends on the other",
          got == want,
          "dependent: %s; expected %s" % (sorted(got), sorted(want)))

    spec = [s for s in O.geometry_specs(params) if s["path"] == "flare/cx"][0]
    check("flare/cx declares every dependent layer",
          set(spec["affects"]) == set(deps),
          "declared %s" % sorted(spec["affects"]))

    obj = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1)
    before = {lid: obj.basis(params, lid).copy() for lid in deps}
    O.set_path(params, "flare/cx", float(O.get_path(params, "flare/cx")) + 6.0)
    obj.invalidate(spec["affects"])
    # A dependent layer must follow flare/cx UNLESS it pins its own cx, in which
    # case it must NOT -- it depends on the centre only through cy.  Requiring
    # every dependent layer to move was right until the first layer pinned one
    # coordinate and not the other: `flare_vline`'s column is measured against
    # the image (array x 528.9 +- 0.5), not against the flare's centroid, so it
    # is pinned on purpose and moving with cx would be the bug.  Splitting the
    # assertion tests both halves instead of excusing the second.
    by_id = {L["id"]: L for L in params["layers"]}
    moved, stuck, held, drifted = [], [], [], []
    for lid in deps:
        after = obj.basis(params, lid)
        c0, c1 = centroid(before[lid]), centroid(after)
        dx = (c1[0] - c0[0]) if (c0 and c1) else 0.0
        pinned = "cx" in by_id.get(lid, {})
        label = "%s(dx=%+.2f)" % (lid, dx)
        if pinned:
            (held if abs(dx) <= 1.0 else drifted).append(label)
        else:
            (moved if dx > 1.0 else stuck).append(label)
    check("moving flare/cx by 6 px moves every layer that does not pin cx",
          not stuck, "stuck: %s" % ", ".join(stuck) if stuck else "moved: %s" % ", ".join(moved))
    check("a layer that pins its own cx stays put when flare/cx moves",
          not drifted,
          "drifted: %s" % ", ".join(drifted) if drifted else
          ("held: %s" % ", ".join(held) if held else "no layer pins cx"))
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
    # Against the UNION of the four spec builders, and over EVERY layer that
    # carries a radial paint.  Both widenings were needed and each hid a real
    # gap.  Restricting the builder to `field_specs` and the layers to kinds
    # canvas/field_radial/radial passed while `frame_rim` -- a `frame_ring`
    # whose paint is positioned rather than concentric -- had a centre that no
    # builder emitted at all, so it was frozen under every --spec including
    # `all`.  A check that is narrower than the thing it guards will pass
    # precisely because the gap is outside it.
    allspecs = (O.layer_specs(params) + O.taper_specs(params)
                + O.geometry_specs(params) + O.field_specs(params))
    apaths = {sp["path"] for sp in allspecs}
    radial_paints = [(i, L) for i, L in enumerate(params["layers"])
                     if isinstance(L.get("paint"), dict) and L["paint"].get("kind") == "radial"]
    missing = [L["id"] for i, L in radial_paints
               if any("layers/%d/paint/%s" % (i, k) not in apaths
                      for k in ("cx", "cy") if k in L["paint"])]
    check("radial gradient centres stored under paint/ are optimisable", not missing,
          "%d radial paints, missing: %s" % (len(radial_paints), missing or "none"))

    # ---- 4b. a declared bound must be reachable by some spec --------------- #
    # The failure this exists for is silent by construction: a parameter gets a
    # carefully measured `bounds` entry, its name is not in `layer_specs`' key
    # list, and every subsequent report says the shapes were optimised while it
    # never moved.  `flare_vline.sigma_x` and `flare_vline.south_gain` -- the
    # vertical streak's width and its north/south balance -- shipped that way
    # for a release.  Checking the two names would not have helped; checking
    # that NO bound is unreachable does.
    unreachable, invalid = O.verify_searchable(params, allspecs)
    check("every bound declared in params.json is reachable by some spec",
          not unreachable,
          "%d bounded parameters; unreachable: %s"
          % (sum(len(L.get("bounds", {})) for L in params["layers"]),
             ", ".join("%s/%s" % u for u in unreachable) or "none"))
    # and the guard is not vacuous: a truncated key list must be caught
    trunc = O.layer_specs(params, keys=("width", "blur", "r"))
    caught, _ = O.verify_searchable(params, trunc + O.taper_specs(params)
                                    + O.geometry_specs(params) + O.field_specs(params))
    check("the reachability guard detects a key list that has fallen behind",
          len(caught) > 5, "a 3-key spec list leaves %d bounds unreachable" % len(caught))

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
    NOT_LAYERS = {"frame_ring",        # a builder KIND, like arc_lens below
                  "corner_model", "corner_r_blend", "corner_r_main",
                  "corner_blend_deg", "corner_note", "flare_dependent_layers",
                  "flare_cells", "field_grad_note", "arc_d", "arc_field",
                  "arc_lens", "arc_station", "flare_report", "field_specs",
                  "corner_cells", "flare_cx",
                  # built, measured, and NOT shipped -- the docs name these to
                  # record what was tested and rejected, which is not a claim
                  # that they are in the model (docs/DECISIONS.md D22)
                  "arc_glow1c", "flare_sat2", "flare_ray_up", "flare_ray_dn",
                  "flare_ray_dl", "lobe_field_left", "lobe_field_right",
                  # removed in this iteration and named in the record OF its
                  # removal: a flat-topped quadrilateral standing in for the
                  # broad west lobe, replaced by `flare_arm_w2`
                  "flare_ray_d"}
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
    # One implementation of "rasterise with the acceptance renderer", shared with
    # tools/render.py.  This used to fall back to importing resvg_py here, so the
    # gate and the renderer could disagree about how resvg is invoked -- and an
    # absent resvg_py aborted the whole gate with a bare ImportError rather than
    # saying which documented dependency was missing.
    try:
        png = R.render_resvg_string(build_svg.build(params), 1024)
    except ImportError as exc:
        raise SystemExit(
            "the regression gate needs the acceptance renderer: %s\n"
            "README.md documents the dependencies; install them with\n"
            "  pip install numpy pillow resvg-py" % exc)
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

    # ---- 6e. the shipped tools import only what the README documents ------ #

    # `tools/diagnose.py` imported `scipy.ndimage` while the reproduction
    # instructions listed numpy, Pillow and resvg-py, so the documented setup
    # and the actual runtime disagreed and a documented command failed on a
    # clean install.  The dependency is gone (both median filters are numpy
    # now, verified identical to SciPy's); this keeps it gone.
    import ast as _ast
    # the third-party packages the README's `pip install` line actually names,
    # plus whatever ships with Python -- anything else is undocumented
    DOCUMENTED = {"numpy", "PIL", "resvg_py"} | set(
        getattr(sys, "stdlib_module_names", ())) | {"__future__"}
    # The repository's own modules, derived from what is actually on disk
    # rather than from a hand-kept list: a new diagnostic that imports a
    # sibling tool is not a new dependency, and a list that has to be edited
    # every time one is added will eventually be wrong in the other direction.
    LOCAL = {fn[:-3] for d in ("tools", "src")
             for fn in os.listdir(os.path.join(ROOT, d)) if fn.endswith(".py")}
    stray = {}
    for d in ("tools", "src"):
        for fn in sorted(os.listdir(os.path.join(ROOT, d))):
            if not fn.endswith(".py"):
                continue
            tree = _ast.parse(open(os.path.join(ROOT, d, fn)).read())
            for node in _ast.walk(tree):
                mods = []
                if isinstance(node, _ast.Import):
                    mods = [n.name for n in node.names]
                elif isinstance(node, _ast.ImportFrom) and node.module and not node.level:
                    mods = [node.module]
                for m in mods:
                    top = m.split(".")[0]
                    if top not in DOCUMENTED and top not in LOCAL:
                        stray.setdefault(top, set()).add("%s/%s" % (d, fn))
    check("the shipped tools import only documented dependencies",
          not stray,
          "undocumented: %s" % ("; ".join("%s (%s)" % (k, ", ".join(sorted(v)))
                                          for k, v in sorted(stray.items())) or "none"))

    # ---- 6c. the search actually refines below its first step ------------- #

    # A parameter whose optimum lies BETWEEN the first-pass proposals: v0 +- 1.0
    # are both worse, v0 + 0.45 is better.  The old loop exited the moment a
    # pass failed to move, so the step never halved and 0.45 was never tried.
    class _Toy:
        """A one-parameter objective with its minimum at +0.45 of one step."""
        def __init__(self):
            self.K = None
            self.n_render = 0
            self.seen = []
        def families(self, params, affects):
            return None
        def invalidate(self, affects):
            pass
        def evaluate(self, params, free=None):
            v = float(O.get_path(params, "toy"))
            self.seen.append(round(v, 4))
            self.n_render += 1
            return (v - 0.45) ** 2, 0.0, None

    toy_params = {"toy": 0.0}
    toy = _Toy()
    O.sweep(toy, toy_params, [{"path": "toy", "lo": -5.0, "hi": 5.0, "step": 1.0,
                               "affects": ["toy"]}], accept_tol=1e-9)
    landed = float(O.get_path(toy_params, "toy"))
    sub_step = [v for v in toy.seen if 0 < abs(v) < 0.9]
    check("the search refines below its first step when a whole step fails",
          abs(landed - 0.45) < 0.12 and bool(sub_step),
          "landed at %.4f after %d evaluations; sub-step proposals tried: %s"
          % (landed, toy.n_render, sorted(set(sub_step))[:6] or "NONE"))

    # ---- 6d. the fitting cells survive subsampling ------------------------ #

    # Cells are built on whatever grid the caller passes and the optimiser
    # passes a subsampled one, so a FIXED minimum pixel count deletes the
    # smallest cells exactly when the search is cheapest.  Measured before the
    # fix: 51 comb cells at full resolution, 0 at stride 3 and 0 at stride 4 --
    # which is every shape, taper, geometry and field stage of optimize_all.sh.
    comb_at = {}
    for st in (1, 2, 3, 4):
        shp = (1024 // st, 1024 // st, 3)
        comb_at[st] = sum(1 for c in regions.flare_cells(shp) if c[0] == "comb")
    full = comb_at[1]
    check("the flare comb cells survive stride 3 and stride 4",
          full > 40 and comb_at[3] >= 0.75 * full and comb_at[4] >= 0.75 * full,
          "comb cells by stride: " + ", ".join("%d:%d" % kv for kv in sorted(comb_at.items())))

    # ---- 6e. an `all` sweep does not search one path twice ---------------- #

    every = sum((b(params) for b in (O.layer_specs, O.taper_specs,
                                     O.field_specs, O.geometry_specs)), [])
    merged = O.merge_specs(every)
    paths = [sp["path"] for sp in merged]
    dupes = len(every) - len(merged)
    check("an `all` sweep searches each path once",
          len(paths) == len(set(paths)),
          "%d specs -> %d after merging (%d duplicate path(s) consolidated)"
          % (len(every), len(merged), dupes))

    # ---- 6f. the geometry preset is the geometry of record ---------------- #

    # `measure_flare.py --geometry` WRITES this table into the params, so a stale
    # entry silently reverts shipped work.  It did: the table held 45.6/215 and
    # 327.8/185 for the right-hand rays after both had been superseded, so running
    # --geometry would have undone an axis correction and re-lengthened a ray that
    # measurement had shortened.
    import measure_flare as MFL
    drift = []
    for lid, (th, fwhm, h, sp, ln, pk) in MFL.RAY_GEOMETRY.items():
        L = next((x for x in params["layers"] if x["id"] == lid), None)
        if L is None:
            drift.append("%s missing from params" % lid); continue
        for name, want, got in (("rot", -th, L.get("rot")), ("height", h, L.get("height")),
                                ("blur", round(MFL.blur_for(fwhm, h), 4), L.get("blur")),
                                ("spread", sp, L.get("spread")), ("len", ln, L.get("len")),
                                ("peak_at", pk, L.get("peak_at"))):
            if got is None or abs(float(want) - float(got)) > 1e-6:
                drift.append("%s/%s preset %.4g vs shipped %s" % (lid, name, want, got))
    check("the ray geometry preset matches the shipped params",
          not drift, "; ".join(drift) if drift else "all %d ray layers agree" % len(MFL.RAY_GEOMETRY))

    # ---- 6g. calibration that does not converge reports failure ----------- #

    # Any corrections computed on the way are saved, so a caller that only looked
    # at the file could not tell a calibrated state from an uncalibrated one.
    # Returning 0 regardless meant automation accepted parameters that had never
    # met their tolerance.
    import subprocess as _sp
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        bad = json.loads(json.dumps(params))
        for L in bad["layers"]:
            if L["id"] in MFL.RAY_LAYER.values():
                L["color"] = [round(v * 0.05, 5) for v in L["color"]]
                for ch in ("white", "cyan", "blue"):
                    if ch in L:
                        L[ch] = round(float(L[ch]) * 0.05, 6)
        pf = os.path.join(_td, "uncalibrated.json")
        json.dump(bad, open(pf, "w"), indent=1)
        # One round cannot recover a 20x deficit: the per-round gain is clipped at 3x.
        r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "measure_flare.py"),
                     "--params", pf, "--rays-only", "--rounds", "1"],
                    capture_output=True, text=True)
        saved = json.load(open(pf))
        moved = any(x["color"] != y["color"] for x, y in zip(saved["layers"], bad["layers"]))
        check("flare calibration that does not converge returns nonzero",
              r.returncode != 0 and "NOT converged" in r.stdout,
              "exit %d; %s; corrections were %ssaved"
              % (r.returncode,
                 "reported NOT converged" if "NOT converged" in r.stdout else "reported success",
                 "" if moved else "NOT "))

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

    # ---- the recurring visual failures ------------------------------------ #
    # Twelve structures, each compared with the reference by the same estimator
    # on the same cells, each stated as a ratio so nothing here encodes one
    # release's accidents.  Two of the twelve currently guard a structure that
    # is known to be too weak rather than correct -- the right-hand rays -- and
    # their bands say so; the check's job there is to stop it getting worse.
    #
    # Validated by breaking the artwork on purpose: deleting the vertical line
    # trips it at 0.11x, deleting all four rays trips all four ray checks at
    # 0.03-0.30x, deleting lines B and C trips both, deleting the cyan bloom
    # trips the colour and skirt checks, and the PREVIOUS release -- with the
    # flat-topped westward quadrilateral -- trips the west-shape check at 1.23x.
    import visual_regression as _VR
    vrows = _VR.report(_VR.np.asarray(Image.open(os.path.join(ROOT, "reference.png"))
                                      .convert("RGB")).astype(np.float64),
                       (real * 255.0).astype(np.float64))
    vbad = [(n, ratio) for n, ratio, lo, hi, ok, _rv, _cv, _m in vrows if not ok]
    vnm = [n for n, ratio, lo, hi, ok, _rv, _cv, _m in vrows if ratio is None]
    check("the reference's structures are all still represented",
          not vbad,
          "%d checks, %d not measurable%s; %s"
          % (len(vrows), len(vnm),
             (" (%s)" % ", ".join(vnm)) if vnm else "",
             ", ".join("%s %.2fx" % (n, r) for n, r in vbad) if vbad
             else "all within band"))

    # ---- every layer's colour is reachable from its own coefficients -------- #
    # `color` is what renders; `white`/`cyan`/`blue` are what the photometric fit
    # reads and writes.  When they disagree the layer is a trap: the artwork
    # looks one way and the next `fit_photometry` run silently changes it to the
    # other.  flare_ray_e shipped exactly like that -- stored [0, 37.4, 11.2],
    # i.e. B/G 0.30, where its own coefficients imply [0, 37.4, 39.8] and B/G
    # 1.064 -- because a measured hue outside the white/cyan/blue cone had been
    # written straight into `color`.  Out-of-cone is a decision, not an accident,
    # and it has to be made where the cone is defined.
    #
    # The comparison is on what the RENDERER sees, so a layer encoded above 255
    # (flare_spike is [256.9, 372.9, 455.0]) is not a violation: split_color
    # clamps it to white and the coefficients say white.
    import fit_photometry as _FP
    off_cone = []
    for L in params["layers"]:
        c = L.get("color")
        if c is None:
            continue
        want = np.clip(np.asarray(_FP.color_from_wc(
            [L.get("white", 0.0), L.get("cyan", 0.0), L.get("blue", 0.0)]), float) * 255.0, 0, 255)
        got = np.clip(np.asarray(c, float), 0, 255)
        d = float(np.abs(want - got).max())
        if d > 0.05:
            off_cone.append("%s (%.1f cv)" % (L["id"], d))
    check("every layer's colour is reachable from its white/cyan/blue",
          not off_cone,
          "%d layers; off-cone: %s" % (len(params["layers"]),
                                       ", ".join(off_cone) or "none"))

    # ---- render provenance cannot authenticate a raster it does not describe #
    # The three-step case the review asks for, run for real rather than
    # asserted: render a known SVG, replace the PNG underneath its sidecar, and
    # require that validation FAILS.  Before the fix it passed, because the
    # sidecar's `svg_sha256` was read without ever hashing the PNG -- so every
    # downstream report went on attributing its numbers to an SVG that had not
    # produced the raster being measured.
    import render as _R
    import tempfile as _tf
    with _tf.TemporaryDirectory() as _td:
        _svg = os.path.join(_td, "a.svg")
        open(_svg, "w").write(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8">'
            '<rect width="8" height="8" fill="#123"/></svg>')
        _png = os.path.join(_td, "a.png")
        _data = _R.render(_svg, 64, "resvg")
        open(_png, "wb").write(_data)
        _R.write_provenance(_png, _svg, _data, 64, "resvg")
        step1 = _R.read_provenance(_png, require=True) == _R.sha256_file(_svg)
        # step 2: different bytes, same filename, sidecar untouched
        open(_png, "wb").write(bytearray(b ^ 0x01 if i == 40 else b
                                         for i, b in enumerate(_data)))
        try:
            _R.read_provenance(_png, require=True)
            step2 = False
        except _R.ProvenanceError:
            step2 = True
        # step 3: a missing sidecar is an absence when optional and an error
        # when required -- the two are not the same and must not collapse
        _R.clear_provenance(_png)
        step3 = _R.read_provenance(_png, require=False) is None
        try:
            _R.read_provenance(_png, require=True)
            step4 = False
        except _R.ProvenanceError:
            step4 = True
    check("a render sidecar cannot authenticate a PNG it does not describe",
          step1 and step2 and step3 and step4,
          "valid render accepted: %s; replaced PNG rejected: %s; "
          "absent provenance optional: %s; absent provenance required-fails: %s"
          % (step1, step2, step3, step4))

    # ---- the vertical streak's own two numbers actually move the render ---- #
    # Reachability (check 4b) says a spec exists; this says the spec DOES
    # something.  A parameter can be emitted, bounded and searched and still be
    # inert if the builder ignores it, which would leave the same silence with
    # more machinery behind it.
    vl = next((L for L in params["layers"] if L.get("kind") == "vstreak"), None)
    if vl is not None:
        import copy as _copy
        base_img = obj.basis(params, vl["id"])
        moves = {}
        for key, delta in (("sigma_x", 1.4), ("south_gain", 0.5)):
            trial = _copy.deepcopy(params)
            tl = next(L for L in trial["layers"] if L["id"] == vl["id"])
            tl[key] = float(tl[key]) + delta
            moves[key] = float(np.abs(obj.basis(trial, vl["id"]) - base_img).max())
        check("the vertical streak's width and north/south balance change the render",
              all(v > 0.004 for v in moves.values()),
              "max basis delta " + ", ".join("%s %+.1f -> %.4f" % (k, d, moves[k])
                                             for k, d in (("sigma_x", 1.4),
                                                          ("south_gain", 0.5))))
        spaths = {sp["path"] for sp in O.layer_specs(params)}
        i_vl = [L["id"] for L in params["layers"]].index(vl["id"])
        check("the vertical streak's width and north/south balance are searched",
              all("layers/%d/%s" % (i_vl, k) in spaths
                  for k in ("sigma_x", "south_gain")),
              "specs present: %s" % sorted(q.rsplit("/", 1)[1] for q in spaths
                                           if q.startswith("layers/%d/" % i_vl)))

    print()
    if FAIL:
        print("%d check(s) failed: %s" % (len(FAIL), ", ".join(FAIL)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
