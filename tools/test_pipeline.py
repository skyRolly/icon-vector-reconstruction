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
import math
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


def preflight(baseline_dir=None):
    """Setup artefacts the checks read that a clean checkout does not carry ([] if all present).

    The previous accepted release is committed as its SVG only; its 1024-px
    render is derived, git-ignored, and made by tools/setup_baseline.py (CI's
    "Baseline setup" step; publish.sh runs it too).  Until D66 CI ran this
    suite without it, and the published-sheet check then FAILED on a file that
    had never been generated -- a missing setup step reported as a broken
    release.  A missing or unverifiable setup artefact is now reported for what
    it is, before any check runs, with its own exit status (3; a regression is
    1), so the two cannot be confused.  The checks are setup_baseline.verify(),
    the very ones the setup step applies -- including that the render is the
    image the published sheet recorded, so a leftover render from another
    renderer version is a setup failure here too, not a stale-sheet FAIL.
    """
    import setup_baseline as _SB
    return _SB.verify(baseline_dir or _SB.BASELINE_DIR)


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
    # verify_searchable() audits `bounds` against emitted specs, so a numeric
    # field that carries no bound is invisible to it: it can stay frozen without
    # ever being reported.  That gap cannot be closed by flagging every unbounded
    # number -- most of the model's numeric leaves are unbounded on purpose (830
    # of 1131 in D72; the check prints the count), so a report of all of them
    # reports nothing.  What CAN be pinned is the inventory: every unbounded
    # number today belongs to one of nineteen kinds, each searched by a
    # different mechanism or measured rather than fitted.  A
    # new unbounded field in a NEW kind is the case worth catching, and this
    # fires on it.  `paint/x1..y2` is the one kind that is neither -- eight
    # canvas gradient extents, frozen, and measured at +-40 px they are worth at
    # most 0.0005 of MAE, which is why they are recorded (D55) and not searched.
    _KNOWN_UNBOUNDED = {
        "white": "photometric fit", "cyan": "photometric fit",
        "blue": "photometric fit", "color": "derived from the coefficients",
        # D64: the fourth primary, carried only by the TEAL_LAYERS of record
        "teal": "photometric fit",
        "profile": "tabulated from the reference",
        "profile_e": "tabulated from the reference",
        "profile_s": "tabulated from the reference",
        "paint/profile": "tabulated from the reference",
        "paint/stops": "tabulated from the reference",
        "paint/x1": "frozen canvas gradient extent (D55)",
        "paint/x2": "frozen canvas gradient extent (D55)",
        "paint/y1": "frozen canvas gradient extent (D55)",
        "paint/y2": "frozen canvas gradient extent (D55)",
        # D67: a radial layer's directional gap (build_svg Builder.gap_mask),
        # fitted to the core's reference residual and held, like the white
        # arms' shape
        "gap": "fitted to the reference and held (D67)",
        # D67: arc_core's width along the curve, measured at the tips and held
        "width_taper": "measured at the curve tips and held (D67)",
        # D68: how far the tip layer's stroke runs past the curves' ends,
        # read from the reference's tails and held
        "extend": "measured past the curve ends and held (D68)",
        # D71: arc_core's blur on the rows outside arc_core_edge's
        # full-strength span, read from the reference's core edges and held
        "end_blur": "measured at the curve ends and held (D71)",
        # D72: arc_core's red along the right curve, read from the reference's
        # core plateau and held (its colour is held with it)
        "red_shift": "measured along the right curve and held (D72)",
    }

    def _numeric_leaves(node, prefix):
        if isinstance(node, dict):
            for k, v in node.items():
                for q in _numeric_leaves(v, prefix + "/" + k):
                    yield q
        elif isinstance(node, list):
            for j, v in enumerate(node):
                for q in _numeric_leaves(v, prefix + "/" + str(j)):
                    yield q
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            yield prefix

    _spec_paths = {sp["path"] for sp in allspecs}
    _kinds, _n_unbounded, _n_total = {}, 0, 0
    for _i, _L in enumerate(params["layers"]):
        for _p in _numeric_leaves(_L, "layers/%d" % _i):
            if "/bounds/" in _p:
                continue
            _n_total += 1
            if _p in _spec_paths:
                continue
            _n_unbounded += 1
            _f = [x for x in _p.split("layers/%d/" % _i, 1)[-1].split("/")
                  if not x.isdigit()]
            _k = "/".join(_f[:2]) if _f[0] == "paint" else _f[0]
            _kinds[_k] = _kinds.get(_k, 0) + 1
    _novel = sorted(k for k in _kinds if k not in _KNOWN_UNBOUNDED)
    check("every number outside the search space is one of the kinds known to be",
          not _novel,
          "%d of %d numeric leaves carry no bound, in %d known kinds (%s); "
          "unaccounted: %s"
          % (_n_unbounded, _n_total, len(_kinds),
             ", ".join("%s %d" % (k, _kinds[k]) for k in sorted(_kinds)),
             ", ".join(_novel) or "none"))

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
    # a red-shifted layer's extra light, as the objective composites it (D72)
    EX = obj.shift_extra(params)
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
    Esub = FP.sub_terms(EX, 8)
    tsub = np.minimum(tgt, 254.4 / 255.0)[sub, sub]
    Wsub = FP.make_weight(tsub)
    WC = FP.params_wc(params)
    nfl = FP.normal_flags(params)
    worst = (0.0, None)
    # flare_ray_ur's R is exactly 0: a channel at its lower BOUND, not clipped
    # (amounts are non-negative, so it can only rise).  There only the
    # one-sided derivative exists, and fit() must use it (D66: it used to call
    # it zero, which froze any dark layer); it is compared with a forward
    # difference, everything else with a central one.
    for lid in ("arc_core", "arc_glow1", "frame_rim", "flare_ray_ur"):
        li = [k for k, L in enumerate(params["layers"]) if L["id"] == lid]
        if not li:
            continue
        li = li[0]
        for j in range(FP.NB):
            h = 1e-4
            wp, wm = WC.astype(np.float64).copy(), WC.astype(np.float64).copy()
            wp[li, j] += h
            _kr = WC[li].astype(np.float64) @ FP.BASIS.astype(np.float64)
            _bound = bool(np.any((_kr == 0.0) & (FP.BASIS[j] > 0)) or WC[li, j] == 0.0)
            if not _bound:
                wm[li, j] -= h
            def f(w):
                # float64 throughout: the central difference of a float32 sum
                # of 3e5 terms loses the signal to cancellation, which is what
                # made this check report 2.5% error on an exact derivative.
                M = FP.composite(Asub.astype(np.float64),
                                 FP.colors(w).astype(np.float64), nfl,
                                 extra={i: e.astype(np.float64) for i, e in Esub.items()})
                e = (M - tsub.astype(np.float64)) * Wsub.astype(np.float64)[..., None]
                return float((e * e).sum())
            num = (f(wp) - f(wm)) / (h if _bound else 2 * h)
            ana = FP.analytic_grad(Asub, tsub, WC, Wsub, nfl, li, j, extra=Esub)
            den = max(abs(num), 1e-9)
            rel = abs(ana - num) / den
            if rel > worst[0]:
                worst = (rel, "%s/%s" % (lid, FP.COMPONENTS[j]))
    check("the analytic gradient matches the objective, clipped and zero channels included",
          worst[0] < 0.02, "worst relative error %.4f at %s" % worst)

    # ---- 5b'. the fit is a PROJECTED solve (D66 review) ------------------- #
    # Once the derivative at a channel's lower bound was made exact (so a dark
    # layer can be fitted back), an amount AT its bound whose gradient points
    # out of the box kept pulling every LM step outside it; each clipped step
    # failed its line search and the documented fit stalled (30 iterations:
    # sse 13.67 against 13.40 before and 13.34 with the active set).  Two cyan
    # layers against a target with R = 0 everywhere: every white amount sits
    # at 0 with an outward gradient.  The fit must reach its floor quickly.
    _rng = np.random.default_rng(0)
    _As = np.stack([np.clip(_rng.random((16, 16)) * 1.2, 0, 1),
                    np.clip(_rng.random((16, 16)) * 1.2, 0, 1)]).astype(np.float32)
    _ts = FP.composite(_As, np.array([[0.0, 0.40, 0.55], [0.0, 0.25, 0.20]], np.float32),
                       [False, False]).astype(np.float32)
    _w0s = np.array([[0.0, 0.2, 0.0, 0.0], [0.0, 0.1, 0.0, 0.0]], np.float32)

    def _rms_after(k):
        _w = FP.fit(_As, _ts, _w0s, np.ones((16, 16), np.float32), iters=k, verbose=False,
                    normal=[False, False], teal_ok=np.array([False, False]))
        return float(np.sqrt(((FP.composite(_As, FP.colors(_w), [False, False]) - _ts) ** 2).mean()))
    _r6, _r40 = _rms_after(6), _rms_after(40)
    # ... and the UPPER bound is the same kind of edge: a channel exactly at 1
    # (a white layer clipped to its amount limit) was treated as clipped, so
    # its whole Jacobian was zero and it could never come back down.
    _A1 = np.ones((1, 8, 8), np.float32)
    _t1 = FP.composite(_A1, np.array([[0.5, 0.5, 0.5]], np.float32), [False]).astype(np.float32)
    _w1 = FP.fit(_A1, _t1, np.array([[1.0, 0.0, 0.0, 0.0]], np.float32), np.ones((8, 8), np.float32),
                 iters=20, verbose=False, normal=[False], teal_ok=np.array([False]))
    check("the photometric fit is a projected solve: amounts at a bound do not stall it",
          _r6 <= 1.01 * _r40 and abs(float(_w1[0, 0]) - 0.5) < 0.01,
          "rms after 6 iterations %.3e, after 40 %.3e (a stalled solve is still >5%% above its floor "
          "after 12); a white layer starting at the clip (1.0) against a 0.5 target reaches %.3f"
          % (_r6, _r40, float(_w1[0, 0])))

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
                  "flare_ray_d",
                  # removed in D61 and named in the record of their removal:
                  # the two straight-edged flank wedges that drew the false
                  # triangle west of the core (measure_flare.RETIRED_FLANKS)
                  "flare_flank_dl", "flare_flank_ul"}
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

    an = FP.composite(A, FP.colors(FP.params_wc(params)), FP.normal_flags(params), extra=EX)
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
            "  pip install -r requirements.txt" % exc)
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
        # The grid the OPTIMISER builds, which is what this check is about.
        # `1024 // st` is not it: Objective.evaluate decimates by point-sampling
        # with [::st, ::st], so at stride 3 it gets len(range(0, 1024, 3)) = 342
        # rows where 1024 // 3 is 341.  One row changes the count, and the 49
        # this check used to publish for stride 3 is really 45.
        n = len(range(0, 1024, st))
        shp = (n, n, 3)
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
    # 327.8/185 for the right-hand rays after both had been superseded.  And until
    # D62 it covered only the original four rays: the nine added in D61 had no
    # entry, so a rebuild restored four rays and left nine wherever the last
    # shape search had put them, and it rewrote flare_ray_b's measured narrow
    # bounds to generic wide ones on the way.  Every key of every ray is checked.
    import measure_flare as MFL
    import copy as _cp
    import contextlib as _clf, io as _iof
    import build_svg as _BS
    drift = ["%s/%s record %s vs shipped %s" % t for t in MFL.drift(params)]
    gprob = MFL.geometry_problems(params)
    # Perturb every key of the contract on every ray -- GEOMETRY_KEYS is every
    # key the builder reads for a ray, including the ones the record says must
    # be ABSENT (an offset or an onset a search added has to be removed again)
    # -- rebuild, and require the layer to come back EXACTLY, bounds included.
    gfail, gcount = [], 0
    for lid in MFL.RAY_GEOMETRY:
        orig = next(x for x in params["layers"] if x["id"] == lid)
        for k in MFL.GEOMETRY_KEYS:
            trial = _cp.deepcopy(params)
            L = next(x for x in trial["layers"] if x["id"] == lid)
            L[k] = float(L.get(k) or 0.0) + 0.37
            with _clf.redirect_stdout(_iof.StringIO()):
                MFL.apply_geometry(trial)
            L = next(x for x in trial["layers"] if x["id"] == lid)
            gcount += 1
            if L != orig:
                gfail.append("%s/%s not restored" % (lid, k))
    # The rays' positions are ABSOLUTE (D63).  The geometry stage of the
    # optimiser searches the flare centre +-30 px; until D63 every ray was an
    # offset from it, so moving the centre moved all of them off their measured
    # lines and --geometry, which wrote the same offsets back, could not undo it.
    # Moving the centre must now leave every ray's coverage exactly as it was,
    # and a rebuild must find nothing to repair.
    _moved = _cp.deepcopy(params)
    _moved["flare"]["cx"] = float(_moved["flare"]["cx"]) + 3.0
    _moved["flare"]["cy"] = float(_moved["flare"]["cy"]) - 3.0
    _dep = [x for x in _BS.flare_dependent_layers(_moved) if x in MFL.RAY_GEOMETRY]
    if _dep:
        gfail.append("rays still anchored to the flare centre: %s" % ", ".join(_dep))
    _rk = [lid for lid in MFL.RAY_GEOMETRY
           if MFL.basis_key(_moved, lid) != MFL.basis_key(params, lid)]
    if _rk:
        gfail.append("moving the flare centre moved %s" % ", ".join(_rk))
    if MFL.drift(_moved):
        gfail.append("--geometry would 'repair' rays after a flare-centre move: %s" % MFL.drift(_moved)[:2])
    # And the rebuild must not widen, narrow or otherwise touch any search
    # space: flare_ray_b's rotation window is +-3 deg around its measured line,
    # not the generic +-6 it was once rewritten to -- and so on for every ray.
    _t = _cp.deepcopy(params)
    with _clf.redirect_stdout(_iof.StringIO()):
        MFL.apply_geometry(_t)
    for _L0, _L1 in zip(params["layers"], _t["layers"]):
        if _L0.get("kind") == "ray" and _L0.get("bounds") != _L1.get("bounds"):
            gfail.append("%s's bounds were rewritten by --geometry" % _L0["id"])
    # A canonical value outside a layer's own search bounds is refused, since
    # the optimiser would clip it on its first trial.
    _t = _cp.deepcopy(params)
    next(x for x in _t["layers"] if x["id"] == "flare_ray_b")["bounds"]["len"] = [10.0, 20.0]
    try:
        with _clf.redirect_stdout(_iof.StringIO()):
            MFL.apply_geometry(_t)
        gfail.append("--geometry accepted a canonical len outside the layer's bounds")
    except SystemExit:
        pass
    # The flank template WAS the other half of --geometry's promise: it
    # re-inserted a deleted flank, so a stale entry shipped a different model --
    # and once the flanks were found to BE the false triangle west of the core
    # (D61), keeping the template would have re-drawn it on the next geometry
    # rebuild.  The guard is now that they stay gone: not in the params, and
    # --geometry refusing a params file that has one.
    fdrift = []
    for rid in MFL.RETIRED_FLANKS:
        if any(x["id"] == rid for x in params["layers"]):
            fdrift.append("%s is back in params.json" % rid)
    _probe = json.loads(json.dumps(params))
    _probe["layers"].append({"id": MFL.RETIRED_FLANKS[0], "kind": "ray"})
    try:
        with _clf.redirect_stdout(_iof.StringIO()):
            MFL.apply_geometry(_probe)
        fdrift.append("--geometry accepted a params file carrying %s" % MFL.RETIRED_FLANKS[0])
    except SystemExit:
        pass
    # A bound is only "reachable" if a spec targets THAT parameter.  Raw prefix
    # matching let a sibling stand in for it -- a blur_x spec satisfied an
    # unreachable blur bound, and profile_e satisfied profile -- so the guard
    # reported a clean search space while the parameter was frozen, which is the
    # one thing it exists to catch.
    _probe = {"layers": [{"id": "probe", "kind": "streak", "blur_x": 2.0,
                          "sigma_y": 3.0, "half_len": 100.0,
                          "bounds": {"blur": [1.0, 9.0], "blur_x": [0.0, 6.0]},
                          "color": [0, 0, 0], "white": 0.0, "cyan": 0.0, "blue": 0.0}],
              "flare": {"cx": 530.0, "cy": 513.0}, "tapers": {}, "geometry": {},
              "frame": {}, "canvas": 1024}
    _pun, _ = O.verify_searchable(_probe)
    # The inspection sheet must not change a feature's aspect ratio.  A centre
    # within `half` of an edge used to return a short crop that enlarge() then
    # squashed into a square: --cx 10 gave a 320x170 box shown at 450x450.
    import flare_view as _FV
    _blank = np.zeros((1024, 1024, 3), dtype=np.float64)
    _shapes = [_FV.crop(_blank, 10, 513, h).shape[:2] for _n, h, _z in _FV.CROPS]
    _square = all(sh == (2 * h, 2 * h) for sh, (_n, h, _z) in zip(_shapes, _FV.CROPS))
    # ... including a centre wholly off the canvas, which used to slice real
    # pixels off the FAR edge (numpy reads a negative endpoint from the other
    # side) and then raise ValueError writing them outside the panel.
    _far = []
    for _cx, _cy in ((-1000, 513), (2500, 513), (513, -1000), (513, 2500)):
        try:
            _far.append(_FV.crop(_blank, _cx, _cy, 160).shape[:2] == (320, 320))
        except Exception:                                      # noqa: BLE001
            _far.append(False)
    check("an off-centre inspection crop stays square instead of being stretched",
          _square and all(_far),
          "crops at cx=10 are %s for half-widths %s; wholly off-canvas centres "
          "return a padded square: %s"
          % (_shapes, [h for _n, h, _z in _FV.CROPS], all(_far)))

    # --require-provenance and the expectation flags are preconditions on the
    # raster, not decorations on the JSON.  Guarded by `if a.json` they passed a
    # Chromium render demanded to be resvg, and a render with no sidecar at all,
    # whenever the caller did not ask for JSON.
    #
    # The fixtures are BUILT here rather than read out of out/.  Pointing this
    # at the committed rasters made a check about compare.py's preconditions
    # depend on which artefacts happen to be on disk: out/render_512.png and its
    # two larger siblings are .gitignored, so a check that reached for one of
    # those would go red on a fresh clone with nothing wrong in the source it
    # exists to test, and a run of validate.py --no-chromium leaves the Chromium
    # raster describing an older SVG.  Whether the shipped artefacts are sound
    # is a separate question with its own check below, which can then say so in
    # those words instead of surfacing as a confusing failure here.
    import subprocess as _sp2
    import render as _R
    import shutil as _sh
    import tempfile as _tf0
    _prov_cases = []
    _d = _tf0.mkdtemp()
    try:
        _fsvg = os.path.join(_d, "fixture.svg")
        open(_fsvg, "w").write('<svg xmlns="http://www.w3.org/2000/svg" '
                               'viewBox="0 0 8 8"><rect width="8" height="8" '
                               'fill="#345"/></svg>')
        _fb = _R.render(_fsvg, 64, "resvg")
        _fref = os.path.join(_d, "ref.png")
        open(_fref, "wb").write(_fb)
        # The same authentic bytes twice, described honestly both times.  What
        # separates them is the RENDERER the sidecar records, which is exactly
        # the confusion --expect-renderer exists to catch: validate.py writes a
        # Chromium render of the same SVG into the same directory, and it hashes
        # just as well as the acceptance raster.
        _fres = os.path.join(_d, "resvg.png")
        open(_fres, "wb").write(_fb)
        _R.write_provenance(_fres, _fsvg, _fb, 64, "resvg")
        _fchr = os.path.join(_d, "chromium.png")
        open(_fchr, "wb").write(_fb)
        _R.write_provenance(_fchr, _fsvg, _fb, 64, "chromium")
        _fnone = os.path.join(_d, "bare.png")          # no sidecar at all
        open(_fnone, "wb").write(_fb)
        _froot = os.path.join(_d, "root.png")          # sidecar is `[]`
        open(_froot, "wb").write(_fb)
        open(_R.provenance_path(_froot), "w").write("[]")
        for _what, _png, _args, _want in (
                ("chromium render demanded to be resvg", _fchr,
                 ["--require-provenance", "--expect-renderer", "resvg"], 1),
                ("64-px render demanded to be 4096", _fres,
                 ["--require-provenance", "--expect-size", "4096"], 1),
                ("no sidecar, provenance required", _fnone,
                 ["--require-provenance"], 1),
                # Each expectation implies --require-provenance: it is a claim
                # about a field that exists only in a sidecar, so a render
                # without one cannot satisfy it.  These three exited 0.
                ("no sidecar, --expect-renderer alone", _fnone,
                 ["--expect-renderer", "resvg"], 1),
                ("no sidecar, --expect-size alone", _fnone,
                 ["--expect-size", "64"], 1),
                ("no sidecar, --expect-svg alone", _fnone,
                 ["--expect-svg", _fsvg], 1),
                # And a sidecar whose JSON root is not an object records no
                # fields at all; it used to raise AttributeError out of the
                # ProvenanceError contract.
                ("sidecar is the JSON array []", _froot,
                 ["--require-provenance"], 1),
                ("the render it says it is", _fres,
                 ["--require-provenance", "--expect-size", "64",
                  "--expect-renderer", "resvg"], 0)):
            _r = _sp2.run([sys.executable, os.path.join(ROOT, "tools", "compare.py"),
                           _fref, _png] + _args,
                          capture_output=True, text=True, cwd=ROOT)
            _prov_cases.append((_what, _r.returncode, _want))
    finally:
        _sh.rmtree(_d, ignore_errors=True)
    check("provenance expectations hold without --json",
          all(rc == want for _a, rc, want in _prov_cases),
          "; ".join("%s -> exit %d (want %d)" % t for t in _prov_cases))

    # And the shipped artefacts as artefacts, which is the question the check
    # above used to answer by accident.  Only these three rasters are tracked --
    # 512/2048/4096 are .gitignored and regenerated by validate.py -- so only
    # these three can be asserted to exist.  `expect_svg` is required of the two
    # resvg renders because publish.sh rebuilds both on every release; it is NOT
    # required of the Chromium one, because the cross-engine check is documented
    # as optional and a release made without a browser legitimately leaves that
    # raster describing the previous SVG.  out/validation.json is where whether
    # it ran is recorded.
    _shipped = []
    for _name, _size, _eng, _current in (
            ("render_256.png", 256, "resvg", True),
            ("render_1024.png", 1024, "resvg", True),
            ("render_1024_chromium.png", 1024, "chromium", False)):
        _p = os.path.join(ROOT, "out", _name)
        if not os.path.exists(_p):
            _shipped.append("%s is missing" % _name)
            continue
        try:
            _R.read_provenance(
                _p, require=True, expect_size=_size, expect_renderer=_eng,
                expect_svg=os.path.join(ROOT, "reconstruction.svg") if _current else None)
        except _R.ProvenanceError as exc:
            _shipped.append("%s: %s" % (_name, exc))
    check("every tracked render is authentic and named what it actually is",
          not _shipped,
          "; ".join(_shipped) if _shipped
          else "render_256, render_1024 (both current with reconstruction.svg) "
               "and render_1024_chromium each hash to their own sidecar")

    # A precondition that runs after the side effects it is meant to prevent is
    # not a precondition.  Both tools used to measure first and validate after,
    # so a rejected raster still left `compare`'s three visualisations and
    # `diagnose`'s three crops on disk -- indistinguishable from the output of a
    # run that had succeeded, and with a nonzero exit status that nothing
    # downstream was obliged to look at.
    _leak = []
    for _tool, _mk in (("compare.py",
                        lambda d: [os.path.join(ROOT, "reference.png"),
                                   os.path.join(d, "r.png"),
                                   "--out-prefix", os.path.join(d, "diff"),
                                   "--json", os.path.join(d, "m.json"),
                                   "--require-provenance"]),
                       ("diagnose.py",
                        lambda d: [os.path.join(d, "r.png"),
                                   "--reference", os.path.join(ROOT, "reference.png"),
                                   "--crops", d,
                                   "--json", os.path.join(d, "d.json"),
                                   "--require-provenance"])):
        _d = _tf0.mkdtemp()
        try:
            _sh.copyfile(os.path.join(ROOT, "out", "render_1024.png"),
                         os.path.join(_d, "r.png"))
            _r = _sp2.run([sys.executable, os.path.join(ROOT, "tools", _tool)] + _mk(_d),
                          capture_output=True, text=True, cwd=ROOT)
            _left = sorted(f for f in os.listdir(_d) if f != "r.png")
            if _r.returncode == 0:
                _leak.append("%s accepted a render with no sidecar" % _tool)
            elif _left:
                _leak.append("%s exited %d but left %s"
                             % (_tool, _r.returncode, ", ".join(_left)))
        finally:
            _sh.rmtree(_d, ignore_errors=True)
    # The inspection sheet is a two-column comparison by construction, so a
    # third path is not a wider comparison, it is a mistake.  images[0:2] drew
    # the first two and reported success: a wrong sheet that looks like a right
    # one, and the third file never even had to exist.
    _arity = []
    for _n, _want in ((1, 0), (2, 0), (3, 2), (4, 2)):
        _r = _sp2.run([sys.executable, os.path.join(ROOT, "tools", "flare_view.py")]
                      + [os.path.join(ROOT, "out", "render_1024.png")] * _n
                      + ["--out", os.path.join(_tf0.gettempdir(), "_fv_arity.png")],
                      capture_output=True, text=True, cwd=ROOT)
        _arity.append((_n, _r.returncode, _want))
    check("the inspection sheet rejects more images than it can draw",
          all(rc == w for _n, rc, w in _arity),
          "; ".join("%d image(s) -> exit %d (want %d)" % t for t in _arity))

    # A raster a --quick run did not write is stale only if the SVG moved since.
    # Reporting `rendered_sizes` and leaving the reader to infer the rest put the
    # problem back on the consumer; each carried raster is classified instead.
    import json as _js
    import validate as _V
    _cls = []
    _d = _tf0.mkdtemp()
    try:
        _svg2 = os.path.join(_d, "s.svg")
        open(_svg2, "w").write('<svg xmlns="http://www.w3.org/2000/svg" '
                               'viewBox="0 0 8 8"><rect width="8" height="8" '
                               'fill="#345"/></svg>')
        _dig = _V._sha256(_svg2)
        _p64 = os.path.join(_d, "render_64.png")
        _b = _R.render(_svg2, 64, "resvg")
        open(_p64, "wb").write(_b)
        _R.write_provenance(_p64, _svg2, _b, 64, "resvg")
        _cls.append(("same SVG", _V.carried_rasters(_d, [64], _dig)[0][1], "current"))
        _cls.append(("SVG moved on",
                     _V.carried_rasters(_d, [64], "0" * 64)[0][1], "stale"))
        _cls.append(("no raster",
                     _V.carried_rasters(_d, [512], _dig)[0][1], "absent"))

        # An authentic raster carried under the WRONG canonical name.  The
        # sidecar's digests both match -- it describes these bytes and this SVG
        # -- so hashing alone called it `current`, and a consumer told it may be
        # read beside the table got a raster of one resolution under the name of
        # another.  `render_%d.png` is a claim about size and engine, and the
        # sidecar has recorded both all along.
        _sh.copyfile(_p64, os.path.join(_d, "render_128.png"))
        _sh.copyfile(_p64 + ".prov.json",
                     os.path.join(_d, "render_128.png.prov.json"))
        _cls.append(("authentic, wrong name",
                     _V.carried_rasters(_d, [128], _dig)[0][1], "unverifiable"))
        _sh.copyfile(_p64, os.path.join(_d, "render_256.png"))
        _side = _js.load(open(_p64 + ".prov.json"))
        _js.dump(dict(_side, size=256, renderer="chromium"),
                 open(os.path.join(_d, "render_256.png.prov.json"), "w"))
        _cls.append(("authentic, wrong engine",
                     _V.carried_rasters(_d, [256], _dig)[0][1], "unverifiable"))

        # A sidecar is arbitrary JSON, and a digest field that is not a string
        # used to escape every check here: `png_sha256: 1` reached the mismatch
        # message, which slices it, and raised TypeError out of a classifier
        # whose entire job is to answer `unverifiable` instead of crashing.  A
        # list was quieter still -- it slices, and got formatted into the
        # evidence column as if it were a measurement.
        for _n, _bad in ((32, {"png_sha256": 1}), (16, {"png_sha256": ["x"]}),
                         (8, {"svg_sha256": ["nope"]}), (4, {"png_sha256": "abc"})):
            _sh.copyfile(_p64, os.path.join(_d, "render_%d.png" % _n))
            _js.dump(dict(_side, size=_n, **_bad),
                     open(os.path.join(_d, "render_%d.png.prov.json" % _n), "w"))
            try:
                _got = _V.carried_rasters(_d, [_n], _dig)[0][1]
            except Exception as exc:                           # noqa: BLE001
                _got = "raised %s" % type(exc).__name__
            _cls.append(("malformed %s=%r" % next(iter(_bad.items())),
                         _got, "unverifiable"))

        # A root that is not an object records no fields at all, so it never
        # reached the shape check above -- `.get` raised AttributeError first,
        # and this classifier, which catches only ProvenanceError, went down
        # with it and produced no report.
        for _n, _root in ((2, "[]"), (1024, "null"), (2048, '"x"'), (4096, "7")):
            _sh.copyfile(_p64, os.path.join(_d, "render_%d.png" % _n))
            open(os.path.join(_d, "render_%d.png.prov.json" % _n), "w").write(_root)
            try:
                _got = _V.carried_rasters(_d, [_n], _dig)[0][1]
            except Exception as exc:                           # noqa: BLE001
                _got = "raised %s" % type(exc).__name__
            _cls.append(("JSON root %s" % _root, _got, "unverifiable"))

        open(_p64, "ab").write(b"junk")
        _cls.append(("sidecar describes other bytes",
                     _V.carried_rasters(_d, [64], _dig)[0][1], "unverifiable"))
    finally:
        _sh.rmtree(_d, ignore_errors=True)
    check("a quick run says which carried rasters are current, not which it rendered",
          all(got == want for _w, got, want in _cls),
          "; ".join("%s -> %s (want %s)" % t for t in _cls))

    # --labels renames the two INPUTS, and four of the six panels in every view
    # name an input: the enhancement pair at the end of each row does too.  Only
    # the first two were substituted, so an A/B sheet labelled its plain panels
    # previous/candidate and the gamma, high-pass and chroma views of the same
    # two images reference/reconstruction.  And the substitution is one pass:
    # chained str.replace re-scanned its own output, so two names sharing a word
    # -- which is how most people spell an A/B pair -- corrupted each other.
    import flare_view as _FV
    _lab = []
    for _view in ("RGB", "LUM", "CHROMA"):
        _z = np.zeros((64, 64, 3))
        for _j, (_im, _l) in enumerate(_FV.build_row(_z, _z, _view, 64, (1.0, 1.0, 1.0))):
            _t = _FV.relabel(_l, ("previous", "candidate"))
            if "reference" in _t or "reconstruction" in _t:
                _lab.append("%s panel %d stayed %r" % (_view, _j, _t))
    _chain = _FV.relabel("reference", ("reconstruction_a", "reconstruction_b"))
    _ident = all(_FV.relabel(_l, ("reference", "reconstruction")) == _l
                 for _view in ("RGB", "LUM", "CHROMA")
                 for _im, _l in _FV.build_row(np.zeros((64, 64, 3)),
                                              np.zeros((64, 64, 3)), _view, 64,
                                              (1.0, 1.0, 1.0)))
    check("--labels renames every panel that names an input, in one pass",
          not _lab and _chain == "reconstruction_a" and _ident,
          "; ".join(_lab) if _lab
          else "18 panels renamed; overlapping names give %r; the default pair is "
               "a no-op: %s" % (_chain, _ident))

    check("a render rejected on provenance leaves no report artefacts behind",
          not _leak, "; ".join(_leak) if _leak
          else "compare and diagnose both refuse before writing anything")

    check("a bound is not counted reachable because a sibling name shares its prefix",
          [n for _i, n in _pun] == ["blur"],
          "a layer with bounds.blur but only blur_x emitted reports unreachable %s"
          % (_pun or "nothing"))

    check("the retired flank wedges stay retired",
          not fdrift,
          "; ".join(fdrift) if fdrift
          else "%s absent from params; --geometry refuses a file that has one"
          % " and ".join(MFL.RETIRED_FLANKS))

    check("the ray geometry preset matches the shipped params",
          not drift, "; ".join(drift) if drift else "all %d ray layers agree on all %d keys"
          % (len(MFL.RAY_GEOMETRY), len(MFL.GEOMETRY_KEYS)))

    check("every ray layer has geometry of record inside its own bounds",
          not gprob, "; ".join(gprob) if gprob else "%d ray layers, each with a contract; "
          "every canonical value lies inside the layer's search bounds" % len(MFL.RAY_GEOMETRY))

    check("--geometry restores every displaced ray and leaves its bounds alone",
          not gfail, "; ".join(gfail[:6]) if gfail else "%d perturbations of %d rays over all "
          "%d contract keys restored exactly; a 3 px flare-centre move moves no ray; no ray's "
          "bounds touched; an out-of-bounds canonical value refused"
          % (gcount, len(MFL.RAY_GEOMETRY), len(MFL.GEOMETRY_KEYS)))

    # ---- 6f2. every stored onset and tail is one the builder draws -------- #

    # The builder clamps a ray's onset to 0.95 x peak_at and its 0.42 stop to
    # 0.999 of its length.  D62's record held flare_ray_b at onset 0.4463,
    # peak_at 0.4011 -- an onset after its own peak -- which rendered as 0.381,
    # and nothing noticed: the table described a ray that was never drawn and
    # a search moving the onset above the clamp changed nothing.  So: the
    # record and the shipped layers have no clamped value; the builder writes
    # flare_ray_b's onset as stored; moving it inside its valid range changes
    # the render, while two values past the clamp render identically (the
    # failure itself); and a record holding the D62 values is refused.
    _onset = []
    _bg = MFL.RAY_GEOMETRY["flare_ray_b"]
    if _bg["onset"] > MFL.ONSET_CLAMP * _bg["peak_at"]:
        _onset.append("flare_ray_b's recorded onset is past the clamp")
    _clamped = [m for lid, g in MFL.RAY_GEOMETRY.items() for m in MFL.profile_problems(lid, g)]
    _clamped += [m for L in params["layers"] if L.get("kind") == "ray"
                 for m in MFL.profile_problems(L["id"], L)]
    _onset += _clamped
    import re as _re2
    _svg = _BS.build(params)
    _gm = _re2.search(r'<linearGradient id="g_flare_ray_b"[^>]*>(.*?)</linearGradient>', _svg)
    _offs = [float(v) for v in _re2.findall(r'offset="([0-9.]+)"', _gm.group(1))] if _gm else []
    if len(_offs) != 6 or abs(_offs[1] - _bg["onset"]) > 1e-4 or abs(_offs[3] - _bg["peak_at"]) > 1e-4:
        _onset.append("the builder did not draw flare_ray_b's stored onset/peak (stops %s)" % _offs)

    def _ray_cov(P, **kw):
        Q = _cp.deepcopy(P)
        Lb = next(x for x in Q["layers"] if x["id"] == "flare_ray_b")
        Lb.update(kw)
        return FP.render_array(_BS.build(Q, basis="flare_ray_b"))[..., 0].astype(np.float64)
    _c0 = _ray_cov(params)
    _inside = [float(np.abs(_ray_cov(params, onset=_bg["onset"] + d) - _c0).max()) for d in (-0.03, 0.03)]
    if min(_inside) < 0.01:
        _onset.append("moving the onset inside its valid range did not change the render (%s)" % _inside)
    _past = float(np.abs(_ray_cov(params, onset=0.95 * _bg["peak_at"] + 0.01)
                         - _ray_cov(params, onset=0.95 * _bg["peak_at"] + 0.05)).max())
    if _past != 0.0:
        _onset.append("two onsets past the clamp rendered differently (%g): the clamp is not where "
                      "the validator thinks it is" % _past)
    _saved = MFL.RAY_GEOMETRY["flare_ray_b"]
    try:
        MFL.RAY_GEOMETRY["flare_ray_b"] = dict(_saved, onset=0.4463, peak_at=0.4011)
        if not any("onset" in m for m in MFL.geometry_problems(params)):
            _onset.append("a record holding the D62 onset/peak is not reported")
        try:
            with _clf.redirect_stdout(_iof.StringIO()):
                MFL.apply_geometry(_cp.deepcopy(params))
            _onset.append("--geometry applied a record whose onset the builder would clamp")
        except SystemExit:
            pass
    finally:
        MFL.RAY_GEOMETRY["flare_ray_b"] = _saved
    # The same pair in the PARAMS, the other place it could live (a review
    # re-reported it against an older commit, D64): drift() must name it, and
    # --geometry must put back the reachable record so that what is emitted
    # and drawn is the record again, pixel for pixel.
    _dv = _cp.deepcopy(params)
    _Ld = next(x for x in _dv["layers"] if x["id"] == "flare_ray_b")
    _Ld.update(onset=0.4463, peak_at=0.4011)
    if not any(d[0] == "flare_ray_b" and d[1] == "profile" for d in MFL.drift(_dv)):
        _onset.append("the D62 onset/peak in the params is not reported by drift()")
    try:
        with _clf.redirect_stdout(_iof.StringIO()):
            MFL.apply_geometry(_dv)
    except SystemExit as _e:
        _onset.append("--geometry refused to repair the params: %s" % str(_e).splitlines()[0])
    _gm2 = _re2.search(r'<linearGradient id="g_flare_ray_b"[^>]*>(.*?)</linearGradient>', _BS.build(_dv))
    _offs2 = [float(v) for v in _re2.findall(r'offset="([0-9.]+)"', _gm2.group(1))] if _gm2 else []
    _rep = float(np.abs(_ray_cov(_dv) - _c0).max())
    if (MFL.drift(_dv) or len(_offs2) != 6 or abs(_offs2[1] - _bg["onset"]) > 1e-4
            or abs(_offs2[3] - _bg["peak_at"]) > 1e-4 or _rep != 0.0):
        _onset.append("--geometry did not repair the D62 onset/peak in the params (stops %s, "
                      "render delta %g)" % (_offs2, _rep))
    check("every stored onset and tail is one the builder draws",
          not _onset, "; ".join(_onset[:4]) if _onset else
          "no clamped onset or tail in the record or the shipped rays; flare_ray_b's onset %.4f is "
          "drawn as stored; +-0.03 inside its range moves the render by %.3f / %.3f, two values "
          "past the clamp render identically; the D62 record (onset after peak) is refused, and "
          "the same pair in the params is reported and repaired by --geometry to the shipped render"
          % (_bg["onset"], _inside[0], _inside[1]))

    # ---- 6g. flare calibration: profile-aware, segment-aware, verified ---- #

    # Until D62 the calibration scaled ONE layer per ray to a pooled chord-excess
    # peak.  A ray drawn as an inner and an outer segment was then scaled by the
    # peak of the pair, which moves the inner segment's part of the profile and
    # leaves the outer's where it was -- a calibration step that could destroy a
    # correctly fitted profile.  It now solves every layer that puts light on
    # every measured line jointly, band by band.  These checks use the shipped
    # layers, not a toy.
    import subprocess as _sp
    import tempfile as _tf
    _ref = np.asarray(Image.open(os.path.join(ROOT, "reference.png")).convert("RGB")).astype(np.float64)
    with _clf.redirect_stdout(_iof.StringIO()):
        _lines = MFL.Lines(_ref)
        _stack = MFL.Stack(params, _lines.box)

    def _amp(P, lid):
        L = next(x for x in P["layers"] if x["id"] == lid)
        return sum(float(L.get(c, 0.0)) for c in ("white", "cyan", "blue", "teal"))

    def _scaled(P, factors):
        Q = json.loads(json.dumps(P))
        for L in Q["layers"]:
            if L["id"] in factors:
                MFL.scale(L, factors[L["id"]])
        return Q

    cal = {}
    with _tf.TemporaryDirectory() as _td:
        # (a) the shipped parameters are calibrated: a verify-only pass asks no
        #     layer for a correction beyond TOL.
        p0 = os.path.join(_td, "shipped.json")
        json.dump(params, open(p0, "w"), indent=1)
        w0, _c0 = MFL.calibrate(p0, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
        cal["shipped"] = (w0 <= 1.0, "shipped worst %.2f of TOL" % w0)
        # The calibrated state every recovery below is measured against is the
        # CONVERGED solve of the shipped file, not the shipped file times the
        # one-step correction a verify pass reports: that step is a
        # linearisation and lands within TOL of the solution, not on it.
        pc = os.path.join(_td, "calibrated.json")
        json.dump(params, open(pc, "w"), indent=1)
        MFL.calibrate(pc, _ref, rounds=4, verbose=False, lines=_lines, stack=_stack)
        star = json.load(open(pc))
        _base_meas = _lines.measure(MFL.render_full(star))

        # (b) SEGMENTED: halve only the INNER lower-left segment.  Calibration
        #     must bring it back and must not drag the outer segment with it.
        p1 = os.path.join(_td, "inner_halved.json")
        json.dump(_scaled(star, {"flare_ray_b": 0.5}), open(p1, "w"), indent=1)
        w1, _c1 = MFL.calibrate(p1, _ref, rounds=4, verbose=False, lines=_lines, stack=_stack)
        s1 = json.load(open(p1))
        dev = {lid: abs(math.log(_amp(s1, lid) / _amp(star, lid))) for lid in MFL.CALIBRATED_LAYERS}
        m1 = _lines.measure(MFL.render_full(s1))
        dprof = float(np.abs(m1["lower-left"]["bands"][:, 1] - _base_meas["lower-left"]["bands"][:, 1]).max())
        cal["segmented"] = (w1 <= 1.0 and dev["flare_ray_b"] <= 0.04 and dev["flare_ray_b2"] <= 0.04
                            and max(dev.values()) <= 0.04 and dprof <= 1.0,
                            "inner restored to %.3f and outer held at %.3f of the calibrated state "
                            "(worst layer %.3f in ln), lower-left profile within %.2f cv"
                            % (math.exp(dev["flare_ray_b"]), math.exp(dev["flare_ray_b2"]),
                               max(dev.values()), dprof))

        # (c) JOINT: the lower-right's two segments pushed in opposite directions.
        p2 = os.path.join(_td, "lr_split.json")
        json.dump(_scaled(star, {"flare_ray_c_in": 0.5, "flare_ray_c": 1.6}), open(p2, "w"), indent=1)
        w2, _c2 = MFL.calibrate(p2, _ref, rounds=4, verbose=False, lines=_lines, stack=_stack)
        s2 = json.load(open(p2))
        d2 = [abs(math.log(_amp(s2, lid) / _amp(star, lid))) for lid in ("flare_ray_c_in", "flare_ray_c")]
        cal["joint"] = (w2 <= 1.0 and max(d2) <= 0.04,
                        "inner %.3f, tail %.3f of the calibrated state after 0.5x / 1.6x"
                        % tuple(math.exp(v) for v in d2))

        # (f) FLANK (D65 review): the lower-right ray is a narrow line inside a
        #     soft flank.  The flank used to sit outside every family, so a
        #     global fit could move it and calibration then re-balanced only
        #     the narrow segments around the wrong flank.  It is now in the
        #     family and read by the split templates: displaced alone (0.4x)
        #     or against the line (2.0x with the line 1.3x), all three segments
        #     and the combined profile -- narrow AND broad readings -- come back.
        _lr = ("flare_ray_c_in", "flare_ray_c", "flare_ray_c_fl")
        _fl_notes = []
        _fl_ok = "flare_ray_c_fl" in MFL.CALIBRATED_LAYERS and "split" in MFL.FAMILIES["lower-right"]
        if not _fl_ok:
            _fl_notes.append("flare_ray_c_fl is not calibrated with a split reading")
        _split0 = _base_meas["lower-right"]["split"]
        import fit_photometry as _FPf
        for _tag, _fac in (("flank 0.4x", {"flare_ray_c_fl": 0.4}),
                           ("flank 2.0x, line 1.3x", {"flare_ray_c_fl": 2.0, "flare_ray_c": 1.3})):
            _pp = os.path.join(_td, "lr_flank.json")
            _pert = _scaled(star, _fac)
            json.dump(_pert, open(_pp, "w"), indent=1)
            # The global fit runs first, as the documented cycle would: it may
            # move every other layer but must leave all three segments exactly
            # where the displacement put them -- it can neither move the flank
            # further nor "repair" it behind calibration's back.
            _gy0, _gy1, _gx0, _gx1 = _lines.box
            _gt = np.minimum(_ref[_gy0:_gy1, _gx0:_gx1] / 255.0, 254.4 / 255.0).astype(np.float32)[::4, ::4]
            _gW0 = _FPf.params_wc(_pert)
            _gW1 = _FPf.fit(_stack.A[:, ::4, ::4], _gt, _gW0, np.ones(_gt.shape[:2], np.float32), iters=2,
                            verbose=False, free=_FPf.held_free(_pert), normal=_FPf.normal_flags(_pert),
                            teal_ok=_FPf.teal_eligible(_pert), extra=_FPf.sub_terms(_stack.E, 4))
            _gi = [[L["id"] for L in _pert["layers"]].index(lid) for lid in _lr]
            _gmoved = float(np.abs(_gW1[_gi] - _gW0[_gi]).max())
            _gfree = float(np.abs(_gW1 - _gW0).max())
            if _gmoved != 0.0:
                _fl_ok = False
                _fl_notes.append("%s: the global fit moved a lower-right segment by %.3g" % (_tag, _gmoved))
            _wf, _cf2 = MFL.calibrate(_pp, _ref, rounds=6, verbose=False, lines=_lines, stack=_stack)
            _sf = json.load(open(_pp))
            _dl = [abs(math.log(_amp(_sf, lid) / _amp(star, lid))) for lid in _lr]
            _ms = _lines.measure(MFL.render_full(_sf))["lower-right"]["split"]
            _dsp = float(np.abs(_ms[..., 1] - _split0[..., 1]).max()) if len(_split0) else 99.0
            _ok = _wf <= 1.0 and max(_dl) <= 0.04 and _dsp <= 0.5
            _fl_ok = _fl_ok and _ok
            _fl_notes.append("%s: global fit moved the segments by %.3g (other layers up to %.3g), then "
                             "calibration -> inner/line/flank %s of the calibrated state, split G within "
                             "%.2f cv" % (_tag, _gmoved, _gfree, "/".join("%.3f" % math.exp(v) for v in _dl),
                                          _dsp))
        cal["flank"] = (_fl_ok, "; ".join(_fl_notes))

        # (g) DARK (D66 review): a calibrated ray whose light is entirely zero
        #     has a zero Jacobian column, which correction() read as "needs
        #     nothing" -- so a ray the reference plainly has could be zeroed and
        #     the calibration would still say converged.  It must now FAIL when
        #     the reference asks for the light, and must NOT fail for a dark
        #     layer the reference has no use for, or one no band can see; a ray
        #     whose teal is 0 but whose cyan is lit is not dark at all.
        _dk = []

        def _darken(P, lid):
            Q = json.loads(json.dumps(P))
            for L in Q["layers"]:
                if L["id"] == lid:
                    for c in ("white", "cyan", "blue", "teal"):
                        if c in L:
                            L[c] = 0.0
                    L["color"] = [0.0, 0.0, 0.0]
            return Q
        for _lid in ("flare_ray_ula", "flare_ray_c_fl"):      # alone in its family; in a joint one
            _pd = os.path.join(_td, "dark.json")
            json.dump(_darken(star, _lid), open(_pd, "w"), indent=1)
            _wd, _cd = MFL.calibrate(_pd, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
            if _wd <= 1.0 or not np.isinf(_cd[_lid]):
                _dk.append("%s at zero light verified as calibrated (worst %.2f)" % (_lid, _wd))
        _rd = _sp.run([sys.executable, os.path.join(ROOT, "tools", "measure_flare.py"), "--params",
                       _pd, "--rounds", "0"], capture_output=True, text=True)
        if _rd.returncode == 0 or "MISSING" not in _rd.stdout:
            _dk.append("measure_flare.py --rounds 0 on a zero-light ray exited %d%s"
                       % (_rd.returncode, "" if "MISSING" in _rd.stdout else " without saying MISSING"))
        # The DEFAULT path solves first -- and the solve pushed a dark ray's light
        # onto its lit neighbours (zero flare_ray_e and round 0 took flare_ray_ur
        # x2.09), after which the leftover no longer asked for the ray and the
        # calibration converged (D66 review).  A dark ray is now judged before
        # anything is solved, and the file is left exactly as it was.
        json.dump(_darken(star, "flare_ray_e"), open(_pd, "w"), indent=1)
        _before = open(_pd, "rb").read()
        _we, _ce = MFL.calibrate(_pd, _ref, rounds=8, verbose=False, lines=_lines, stack=_stack)
        if _we <= 1.0 or not np.isinf(_ce["flare_ray_e"]):
            _dk.append("flare_ray_e at zero light converged on the default (solving) path (worst %.2f)" % _we)
        if open(_pd, "rb").read() != _before:
            _dk.append("the solve ran and saved over a file with a missing ray")
        # ... and a file ALREADY absorbed that way (as the pre-fix code saved it:
        # flare_ray_e dark, flare_ray_ur x2.09) is still judged missing, because
        # the evidence is what the lit layers' re-scaling cannot supply.
        _ab = _darken(star, "flare_ray_e")
        for L in _ab["layers"]:
            if L["id"] == "flare_ray_ur":
                MFL.scale(L, 2.09)
        json.dump(_ab, open(_pd, "w"), indent=1)
        _wa, _ca = MFL.calibrate(_pd, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
        if _wa <= 1.0 or not np.isinf(_ca["flare_ray_e"]):
            _dk.append("an already-absorbed file (flare_ray_e dark, flare_ray_ur x2.09) verified as "
                       "calibrated (worst %.2f)" % _wa)
        # A ray scaled to next to nothing is as missing as one at exactly 0 --
        # 1e-4 of its light survives the file's rounding (amounts to 1e-6) as
        # non-zero amounts, which is the point: it is not exactly dark.  And a
        # LIT ray at 5% of its light is not dark at all: a scale recovers it.
        _fa = json.loads(json.dumps(star))
        for L in _fa["layers"]:
            if L["id"] == "flare_ray_ula":
                MFL.scale(L, 1e-4)
                _faint_sum = sum(float(L.get(c, 0.0)) for c in MFL.CHANNELS)
        json.dump(_fa, open(_pd, "w"), indent=1)
        _wf2, _cf3 = MFL.calibrate(_pd, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
        if not _faint_sum > 0.0:
            _dk.append("the faint-ray case rounded to exactly zero and tests nothing")
        if _wf2 <= 1.0 or not np.isinf(_cf3["flare_ray_ula"]):
            _dk.append("flare_ray_ula at 1e-4 of its light (amounts %.1e) verified as calibrated (worst %.2f)"
                       % (_faint_sum, _wf2))
        _lo = json.loads(json.dumps(star))
        for L in _lo["layers"]:
            if L["id"] == "flare_ray_ula":
                MFL.scale(L, 0.05)
        json.dump(_lo, open(_pd, "w"), indent=1)
        _wl, _cl = MFL.calibrate(_pd, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
        if np.isinf(_cl["flare_ray_ula"]) or _cl["flare_ray_ula"] < 5.0:
            _dk.append("flare_ray_ula at 5%% of its light was called dark, or not asked to scale up "
                       "(asks x%.3g)" % _cl["flare_ray_ula"])
        # A dark layer the reference has no use for, and one no band can see:
        # a zero-light copy of the upper-left A ray on its own line, and one
        # moved off the measured crop, both made members of its family.
        _q = json.loads(json.dumps(star))
        _ids = [L["id"] for L in _q["layers"]]
        _dup = _darken({"layers": [dict(_q["layers"][_ids.index("flare_ray_ula")], id="probe_dup")]},
                       "probe_dup")["layers"][0]
        _off = dict(_dup, id="probe_off", cx=40.0, cy=40.0)
        _q["layers"][_ids.index("flare_ray_ula") + 1:_ids.index("flare_ray_ula") + 1] = [_dup, _off]
        _fam0, _cl0 = MFL.FAMILIES["upper-left A"], MFL.CALIBRATED_LAYERS
        try:
            MFL.FAMILIES["upper-left A"] = dict(_fam0, layers=_fam0["layers"] + ("probe_dup", "probe_off"))
            MFL.CALIBRATED_LAYERS = tuple(dict.fromkeys(
                lid for f in MFL.FAMILIES.values() for lid in f["layers"]))
            _pq = os.path.join(_td, "dark_ok.json")
            json.dump(_q, open(_pq, "w"), indent=1)
            _sq = MFL.Stack(_q, _lines.box)
            _wq, _cq = MFL.calibrate(_pq, _ref, rounds=0, verbose=False, lines=_lines, stack=_sq)
            _rep = MFL.dark_report(_lines, _sq, _lines.measure(MFL.render_full(json.load(open(_pq)))))
        finally:
            MFL.FAMILIES["upper-left A"], MFL.CALIBRATED_LAYERS = _fam0, _cl0
        if _rep.get("probe_dup", ("?",))[0] != "not needed" or _rep.get("probe_off", ("?",))[0] != "unobservable":
            _dk.append("dark-layer verdicts %s (want probe_dup not needed, probe_off unobservable)" % _rep)
        if _wq > 1.0:
            _dk.append("a dark layer the reference has no use for failed the calibration (worst %.2f)" % _wq)
        # Teal at 0 is two different things.  flare_ray_lld keeps cyan light:
        # its colour is recoverable by the colour fit and calibration scales
        # it as usual.  flare_ray_ur carries ALL its light as teal, so at teal
        # 0 it is a dark ray -- and must fail as MISSING, because a scale
        # cannot give it teal back; the colour fit can (see the teal check).
        def _teal0(P, lid):
            Q = json.loads(json.dumps(P))
            for L in Q["layers"]:
                if L["id"] == lid:
                    L["teal"] = 0.0
                    L["color"] = [round(float(v) * 255.0, 2) for v in
                                  _FPf.color_from_wc([float(L.get(c, 0.0)) for c in MFL.CHANNELS])]
            return Q
        _pt = os.path.join(_td, "teal0.json")
        json.dump(_teal0(star, "flare_ray_lld"), open(_pt, "w"), indent=1)
        _wt, _ct = MFL.calibrate(_pt, _ref, rounds=4, verbose=False, lines=_lines, stack=_stack)
        if _wt > 1.0 or MFL.dark_report(_lines, _stack, _lines.measure(MFL.render_full(json.load(open(_pt))))):
            _dk.append("flare_ray_lld at teal 0 with lit cyan was treated as dark or did not calibrate "
                       "(worst %.2f)" % _wt)
        json.dump(_teal0(star, "flare_ray_ur"), open(_pt, "w"), indent=1)
        _wu, _cu = MFL.calibrate(_pt, _ref, rounds=0, verbose=False, lines=_lines, stack=_stack)
        if _wu <= 1.0 or not np.isinf(_cu["flare_ray_ur"]):
            _dk.append("flare_ray_ur at teal 0 -- no light left -- verified as calibrated (worst %.2f)" % _wu)
        cal["dark"] = (not _dk, "; ".join(_dk) if _dk else
                       "a zeroed upper-left A ray and a zeroed lower-right flank each fail verification "
                       "(the CLI exits 1 saying MISSING); a zeroed upper-right slab fails on the default "
                       "solving path too, with the file left untouched, and so does a file its neighbour "
                       "already absorbed (x2.09); a ray at 1e-4 of its light counts as dark and fails, "
                       "while one at 5%% is lit and simply asked to scale up; "
                       "a zero-light copy on the line is 'not needed' "
                       "(asks %.2f cv) and one off the crop 'unobservable', and neither fails; at teal 0, "
                       "flare_ray_lld (cyan still lit) calibrates (worst %.2f) while flare_ray_ur (all "
                       "its light was teal) fails as MISSING" % (_rep["probe_dup"][1], _wt))

        # (d) the SAVED file reproduces the calibrated result through the
        #     documented build and render commands, not the in-process path.
        svg1, png1 = os.path.join(_td, "r.svg"), os.path.join(_td, "r.png")
        _sp.run([sys.executable, os.path.join(ROOT, "src", "build_svg.py"), "--params", p1,
                 "--out", svg1], check=True, capture_output=True)
        _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), svg1, png1],
                check=True, capture_output=True)
        mcli = _lines.measure(np.asarray(Image.open(png1).convert("RGB")).astype(np.float64))
        dcli = max(float(np.abs(mcli[f]["bands"] - m1[f]["bands"]).max()) for f in mcli)
        # ... and so does the recalibrated FLANK file of (f), split readings included
        _sp.run([sys.executable, os.path.join(ROOT, "src", "build_svg.py"), "--params", _pp,
                 "--out", svg1], check=True, capture_output=True)
        _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), svg1, png1],
                check=True, capture_output=True)
        _mcf = _lines.measure(np.asarray(Image.open(png1).convert("RGB")).astype(np.float64))
        _mif = _lines.measure(MFL.render_full(json.load(open(_pp))))
        dcli = max(dcli, max(float(np.abs(_mcf[f]["bands"] - _mif[f]["bands"]).max()) for f in _mcf),
                   max(float(np.abs(_mcf[f]["split"] - _mif[f]["split"]).max()) if len(_mif[f]["split"])
                       else 0.0 for f in _mcf))
        cal["rebuild"] = (dcli <= 0.01, "rebuilt from the saved files (a segment and the flank "
                          "recalibrated), every band and split reading within %.3g cv" % dcli)

        # (e) a calibration that does not converge says so and exits nonzero,
        #     and still SAVES the corrections it computed: one round cannot
        #     recover a 20x deficit, because a round moves a layer at most 3x.
        bad = _scaled(params, {lid: 0.05 for lid in MFL.CALIBRATED_LAYERS})
        pf = os.path.join(_td, "uncalibrated.json")
        json.dump(bad, open(pf, "w"), indent=1)
        r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "measure_flare.py"),
                     "--params", pf, "--rounds", "1"], capture_output=True, text=True)
        saved = json.load(open(pf))
        moved = all(_amp(saved, lid) > 2.0 * _amp(bad, lid) for lid in MFL.CALIBRATED_LAYERS)
        cal["fails"] = (r.returncode != 0 and "NOT converged" in r.stdout and moved,
                        "exit %d; %s; corrections %ssaved"
                        % (r.returncode, "reported NOT converged" if "NOT converged" in r.stdout
                           else "reported success", "" if moved else "NOT "))

        # (f) a STALE stack: until D63 a supplied stack was reused whenever the
        #     layer names matched, so a caller that reshaped a ray and then
        #     calibrated was solved on the old ray's coverage.  Reshape one ray
        #     (names unchanged), calibrate with the old stack, and require that
        #     exactly that layer was re-rendered and that the result equals a
        #     fresh stack's; then change only a colour and require no re-render.
        _st = _cp.copy(_stack)
        _st.A, _st.keys = _stack.A.copy(), list(_stack.keys)
        _geo = json.loads(json.dumps(params))
        next(x for x in _geo["layers"] if x["id"] == "flare_ray_c")["len"] = 150.0
        pg = os.path.join(_td, "reshaped.json")
        json.dump(_geo, open(pg, "w"), indent=1)
        _r0 = _st.renders
        _ws, _cs = MFL.calibrate(pg, _ref, rounds=0, verbose=False, lines=_lines, stack=_st)
        _geo_renders = _st.renders - _r0
        _wf, _cf = MFL.calibrate(pg, _ref, rounds=0, verbose=False, lines=_lines, stack=None)
        _same = max(abs(_cs[k] - _cf[k]) for k in _cf)
        _col = _scaled(_geo, {"flare_ray_c": 1.3})
        pc2 = os.path.join(_td, "recoloured.json")
        json.dump(_col, open(pc2, "w"), indent=1)
        _r1 = _st.renders
        _wc2, _cc2 = MFL.calibrate(pc2, _ref, rounds=0, verbose=False, lines=_lines, stack=_st)
        _col_renders = _st.renders - _r1
        _wf2, _cf2 = MFL.calibrate(pc2, _ref, rounds=0, verbose=False, lines=_lines, stack=None)
        _same2 = max(abs(_cc2[k] - _cf2[k]) for k in _cf2)
        _wrongbox = not _st.matches(_geo, (0, 10, 0, 10))
        cal["stale"] = (_geo_renders == 1 and _same < 1e-9 and _col_renders == 0 and _same2 < 1e-9
                        and _wrongbox,
                        "a reshaped ray re-rendered %d layer(s) of the stale stack and matched a fresh "
                        "stack to %.1e; a colour-only change re-rendered %d and matched to %.1e; a "
                        "stack for another crop is not reused: %s"
                        % (_geo_renders, _same, _col_renders, _same2, _wrongbox))

    check("the shipped rays are calibrated to their measured profiles", *cal["shipped"])
    check("calibrating one segment does not drag the other", *cal["segmented"])
    check("a two-segment ray is calibrated jointly", *cal["joint"])
    check("the lower-right flank is held by the global fit and restored by calibration", *cal["flank"])
    check("a calibrated ray with no light cannot pass as calibrated", *cal["dark"])
    check("a calibrated file rebuilds to the calibrated profiles", *cal["rebuild"])
    check("flare calibration that does not converge returns nonzero", *cal["fails"])
    check("a calibration stack whose geometry is stale is refreshed, not reused", *cal["stale"])

    # ---- 6h. the global fits hold the calibrated rays ---------------------- #

    # optimize.py and fit_photometry.py fit every layer's colour to a
    # whole-image objective, and until D62 that included the rays: any run of
    # the documented full cycle rewrote the profile-calibrated amplitudes with
    # the objective D61 caught drawing a lower-left ray 2.5x the reference.
    # They now hold the rays -- shape out of the search, colour out of the fit
    # -- and prune_layers never offers a ray for removal.
    import fit_photometry as _FP
    import prune_layers as _PL
    _hs = [sp["path"] for sp in O.layer_specs(params, hold=tuple(MFL.RAY_GEOMETRY))
           if any(a in MFL.RAY_GEOMETRY for a in sp.get("affects", []) if isinstance(a, str))]
    _obj = O.Objective(os.path.join(ROOT, "reference.png"), held=MFL.CALIBRATED_LAYERS)
    _fi = _obj.free_indices(params, None)
    _hidx = [i for i, L in enumerate(params["layers"]) if L["id"] in MFL.CALIBRATED_LAYERS]
    _hf = _FP.held_free(params)
    _y0, _y1, _x0, _x1 = _lines.box
    _tgt = np.minimum(_ref[_y0:_y1, _x0:_x1] / 255.0, 254.4 / 255.0).astype(np.float32)[::4, ::4]
    _WC0 = _FP.params_wc(params)
    _WC1 = _FP.fit(_stack.A[:, ::4, ::4], _tgt, _WC0, np.ones(_tgt.shape[:2], np.float32), iters=2,
                   verbose=False, free=_hf, normal=_FP.normal_flags(params),
                   teal_ok=_FP.teal_eligible(params), extra=_FP.sub_terms(_stack.E, 4))
    _moved_free = float(np.abs(_WC1[_hf] - _WC0[_hf]).max())
    _moved_held = float(np.abs(_WC1[_hidx] - _WC0[_hidx]).max())
    _unprot = sorted(set(MFL.RAY_GEOMETRY) - _PL.protected("exterior"))
    check("the global fits never move a calibrated ray",
          not _hs and not (set(_fi) & set(_hidx)) and not (set(_hf) & set(_hidx))
          and _moved_held == 0.0 and _moved_free > 0.0 and not _unprot,
          "ray shape specs emitted when held: %d; held rays in the optimiser's free set: %d, "
          "in fit_photometry's: %d; a real fit moved the free layers by %.3g and the rays by %g; "
          "rays prune could remove: %s"
          % (len(_hs), len(set(_fi) & set(_hidx)), len(set(_hf) & set(_hidx)),
             _moved_free, _moved_held, ", ".join(_unprot) or "none"))

    # ---- the objective scores the parameters it is given (D67) ------------- #
    # The review case: Objective.K seeded the held rays' colour rows once and
    # kept them, and the fit never touches a held row, so an Objective that
    # scored parameters A and then B -- B differing only in a held ray's
    # colour -- scored B with A's colour.  Each state below is scored by one
    # REUSED objective and by a FRESH one (sharing only the basis cache, which
    # is keyed on each layer's markup and so is valid for any parameters);
    # the two must agree, and the reused objective's held rows must be the
    # state's own.  B changes one held ray and nothing movable; C changes
    # three held rays; D returns to A.  Fitted rows of movable layers are the
    # optimiser's own state (sweep carries them between accepted moves) and
    # must survive a held-row refresh.  A reordered stack must re-seed, since
    # a row count cannot tell it from the original.  On the old code B and C
    # score exactly as A, and the reordered stack scores 15% off.
    import copy as _cpk
    _heldK = MFL.CALIBRATED_LAYERS
    _idsK = [L["id"] for L in params["layers"]]
    _hK = [i for i, lid in enumerate(_idsK) if lid in _heldK]
    def _scaledK(ks):
        q = _cpk.deepcopy(params)
        byq = {L["id"]: L for L in q["layers"]}
        for lid, k in ks.items():
            MFL.scale(byq[lid], k)
        return q
    def _freshK(o):
        f = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1, held=_heldK)
        f.cache = o.cache
        return f
    _objK = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1, held=_heldK)
    _diagK, _sK = [], {}
    for _nm, _S in (("A", params), ("B", _scaledK({"flare_ray_c": 1.5})),
                    ("C", _scaledK({"flare_ray_ur": 0.5, "flare_ray_lld": 0.7, "flare_ray_c": 1.2})),
                    ("D", _cpk.deepcopy(params))):
        _reK, _, _Kre = _objK.evaluate(_S)
        _fr = _freshK(_objK).evaluate(_S)[0]
        _wcK = _FP.params_wc(_S)
        _sK[_nm] = _fr
        if _reK != _fr:                  # the same arithmetic: bitwise equal
            _diagK.append("%s scored %.9g reused against %.9g fresh" % (_nm, _reK, _fr))
        if not (np.array_equal(_objK.K[_hK], _wcK[_hK]) and np.array_equal(_Kre[_hK], _wcK[_hK])):
            _diagK.append("%s: held rows are not the state's colours" % _nm)
    if abs(_sK["A"] - _sK["B"]) <= 1e-4 * abs(_sK["A"]):
        _diagK.append("vacuous: the held-colour change moved the score by only %.2g"
                      % abs(_sK["A"] - _sK["B"]))
    _KfitK = _objK.evaluate(params)[2]
    _objK.K = _KfitK                     # a sweep's accepted colour state
    _objK.evaluate(_scaledK({"flare_ray_c": 1.5}))
    _movK = [i for i in range(len(_idsK)) if i not in _hK]
    if not np.array_equal(_objK.K[_movK], _KfitK[_movK]):
        _diagK.append("a held-row refresh discarded the movable layers' fitted colours")
    # the path sweep actually takes: a trial frees ONE family, and every other
    # movable layer is scored at the accepted state, not re-read from params
    _objK.K = _KfitK
    _famK = _objK.families(params, ["arc_glow2"])
    _, _, _Kfam = _objK.evaluate(_scaledK({"flare_ray_c": 1.5}), free=_famK)
    _outK = [i for i in _movK if i not in set(_famK)]
    if not (_outK and np.array_equal(_objK.K[_outK], _KfitK[_outK])
            and np.array_equal(_Kfam[_outK], _KfitK[_outK])):
        _diagK.append("a family-restricted trial did not score the other movable layers "
                      "at the accepted colours")
    _swK = _cpk.deepcopy(params)
    _i1, _i2 = _idsK.index("flare_ray_c"), _idsK.index("arc_glow2")
    _swK["layers"][_i1], _swK["layers"][_i2] = _swK["layers"][_i2], _swK["layers"][_i1]
    _reR, _frR = _objK.evaluate(_swK)[0], _freshK(_objK).evaluate(_swK)[0]
    if _reR != _frR:
        _diagK.append("a reordered stack scored %.9g reused against %.9g fresh" % (_reR, _frR))
    # a layer that LOSES the teal permission between two evaluations: with the
    # rays free (optimize.py --include-rays), a kept teal amount would be
    # locked in by the fit and scored although the parameters forbid it
    _objT = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1, held=())
    _objT.cache = _objK.cache
    _objT.evaluate(params)
    _noT = _cpk.deepcopy(params)
    for _L in _noT["layers"]:
        if _L["id"] == "flare_ray_ur":
            _L.pop("teal")
            _wcT = _FP.wc_from_color(_L["color"], teal=False)
            _L["white"], _L["cyan"], _L["blue"] = (round(float(v), 6) for v in _wcT[:3])
            _L["color"] = [round(float(v) * 255.0, 2) for v in _FP.color_from_wc(_wcT)]
    _reT, _, _KT = _objT.evaluate(_noT)
    _fT = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1, held=())
    _fT.cache = _objK.cache
    _frT = _fT.evaluate(_noT)[0]
    _iur = _idsK.index("flare_ray_ur")
    if _reT != _frT or _KT[_iur, 3] != 0.0:
        _diagK.append("a layer that lost teal eligibility scored %.9g reused against %.9g fresh "
                      "(its teal amount %.4g)" % (_reT, _frT, _KT[_iur, 3]))
    check("the optimiser's objective scores the held ray colours it is given",
          not _diagK, "; ".join(_diagK) if _diagK else
          "4 successive states (one held ray; three held rays; back again) score bitwise "
          "identically through a reused and a fresh Objective, held rows equal each state's "
          "colours, the held change moves the score by %.2g%%, fitted movable rows survive the "
          "refresh (also on a family-restricted trial, as sweep scores them), a reordered stack "
          "re-seeds, and a layer that loses teal eligibility is scored without teal"
          % (100 * abs(_sK["A"] - _sK["B"]) / abs(_sK["A"])))

    # ---- a caller's colour edit reaches the objective's movable rows (D69) - #
    # The review case: colours() refreshed the HELD rows from the parameters
    # (D67) but carried every movable row, so an objective that scored A and
    # then B -- B differing only in a movable layer's stored colour -- scored
    # B with A's colour.  Nothing is freed here (free=[]), so a reused and a
    # fresh Objective must agree bitwise on every state: arc_glow1 cyan ->
    # black by its colour alone (the review's example), back to cyan, two
    # layers at once, and back.  The carried state must still be carried: a
    # fit's movable rows, assigned to obj.K as sweep assigns them, ride
    # through a geometry-only successor -- scored as a fresh objective holding
    # the same rows, not as one seeded from the stored colours -- and an edit
    # of one layer re-reads that row alone.  On the old code every edited
    # state scores exactly as the state before it.
    def _freshM():
        f = O.Objective(os.path.join(ROOT, "reference.png"), stride=8, fit_iters=1, held=_heldK)
        f.cache = _objK.cache
        return f
    def _recolM(p, edits):
        q = _cpk.deepcopy(p)
        for L in q["layers"]:
            if L["id"] not in edits:
                continue
            if edits[L["id"]] == "black":        # the stored colour alone
                L["color"] = [0.0, 0.0, 0.0]
                continue
            wc = _FP.params_wc({"layers": [L]})[0] * edits[L["id"]]
            for n, v in zip(_FP.COMPONENTS, wc):
                if n in L:
                    L[n] = round(float(v), 6)
            L["color"] = [round(float(v) * 255.0, 2) for v in _FP.color_from_wc(wc)]
        return q
    _objM = _freshM()
    _diagM, _sM = [], {}
    for _nm, _S in (("A", params), ("B", _recolM(params, {"arc_glow1": "black"})), ("A again", params),
                    ("C", _recolM(params, {"arc_glow1": 0.0, "field_grad": 0.5})), ("A after C", params)):
        _reM = _objM.evaluate(_S, free=[])[0]
        _frM = _freshM().evaluate(_S, free=[])[0]
        _sM[_nm] = _frM
        if _reM != _frM:                  # the same arithmetic: bitwise equal
            _diagM.append("%s scored %.9g reused against %.9g fresh" % (_nm, _reM, _frM))
    _dB, _dC = (abs(_sM[k] - _sM["A"]) / abs(_sM["A"]) for k in ("B", "C"))
    if min(_dB, _dC) <= 1e-3:
        _diagM.append("vacuous: the colour edits moved the score by only %.2g / %.2g" % (_dB, _dC))
    _movM = [i for i, lid in enumerate(_idsK) if lid not in _heldK]
    _GM = _cpk.deepcopy(params)
    for _L in _GM["layers"]:
        if _L["id"] == "arc_glow2":
            _L["blur"] = float(_L["blur"]) + 0.5         # geometry only
    _objM.K = _KfitK                     # a fit's movable rows, as sweep assigns them
    _reG = _objM.evaluate(_GM, free=[])[0]
    _hM = _freshM()
    _hM.colours(_GM)
    _hM.K = _KfitK
    _hdG, _sdG = _hM.evaluate(_GM, free=[])[0], _freshM().evaluate(_GM, free=[])[0]
    if not (np.array_equal(_objM.K[_movM], _KfitK[_movM]) and _reG == _hdG):
        _diagM.append("a geometry-only successor did not keep the carried rows (%.9g against %.9g)"
                      % (_reG, _hdG))
    if _sdG == _reG:
        _diagM.append("vacuous: the carried rows score as the stored colours do")
    _BG = _recolM(_GM, {"arc_glow1": "black"})
    _objM.evaluate(_BG, free=[])
    _igM = _idsK.index("arc_glow1")
    _othM = [i for i in _movM if i != _igM]
    if not np.array_equal(_objM.K[_igM], _FP.params_wc(_BG)[_igM]):
        _diagM.append("an edit of arc_glow1's colour on the carried state was not read (row %s)"
                      % np.round(_objM.K[_igM], 4))
    if not np.array_equal(_objM.K[_othM], _KfitK[_othM]):
        _diagM.append("an edit of one layer's colour discarded the other carried rows")
    check("the optimiser's objective scores a movable colour its caller changed",
          not _diagM, "; ".join(_diagM) if _diagM else
          "5 successive states (arc_glow1 cyan -> black by its colour alone; back; two layers; back) "
          "score bitwise identically through a reused and a fresh Objective with nothing freed, and "
          "the edits move the score by %.1f%% / %.1f%%; a fit's movable rows ride through a "
          "geometry-only successor (%.9g, as a fresh objective holding them; %.9g seeded from the "
          "stored colours), and an edit of one layer re-reads that row alone (%d carried rows kept)"
          % (100 * _dB, 100 * _dC, _reG, _sdG, len(_othM)))

    # ---- a radial layer's directional gap only removes its own light (D67) - #
    # The halo carries a fitted gap north-east of the core (a blurred annular
    # sector of its own coverage removed by a luminance mask).  It must stay a
    # directional LAYER, never a darkening one.  On the shipped file, rendered
    # alone, the halo with its gap may never exceed the halo without it and
    # must be unchanged away from the sector.  The shipped sector lies where
    # the halo is faint (<= 7/255), so the mechanism is also checked with a
    # probe gap over the halo's bright part: depth 1 removes (all but) all of
    # it inside, depth 0.5 about half (resvg reads a luminance mask linearly).
    # A stack without gaps must emit no mask at all (once its curve-axis ends,
    # whose paint carries a mask of its own (D70), are put back on y, and its
    # end blur, whose two copies are cut by row masks (D71), is dropped).
    _gapL = [L for L in params["layers"] if L.get("gap")]
    _gd = []
    _yy, _xx = np.mgrid[0:1024, 0:1024] + 0.5
    def _halo(pp):
        return _FP.render_array(build_svg.build(pp, basis="flare_halo"), 1024)[..., 0].astype(np.float64)
    def _sector(g, pad_th, pad_r):
        rr = np.hypot(_xx - g["cx"], _yy - g["cy"])
        th = np.degrees(np.arctan2(-(_yy - g["cy"]), _xx - g["cx"]))
        return (th > g["th0"] + pad_th) & (th < g["th1"] - pad_th) & (rr > g["r0"] + pad_r) & (rr < g["r1"] - pad_r)
    if [L["id"] for L in _gapL] != ["flare_halo"]:
        _gd.append("layers with a gap: %s (expected flare_halo)" % [L["id"] for L in _gapL])
    else:
        _g = _gapL[0]["gap"]
        _pn = _cpk.deepcopy(params)
        for _Lg in _pn["layers"]:
            _Lg.pop("gap", None)
            _Lg.pop("taper_axis", None)
            _Lg.pop("end_blur", None)
        if "<mask" in build_svg.build(_pn):
            _gd.append("a stack without gaps still emits a mask")
        _cw, _cn = _halo(params), _halo(_pn)
        _added = float((_cw - _cn).max() * 255)
        _away = float(np.abs(_cw - _cn)[~_sector(_g, -12, -6 * _g["blur"])].max() * 255)
        _removed = float((_cn - _cw).max() * 255)
        if _added > 1.0:
            _gd.append("the gap ADDS light (up to %.1f cv)" % _added)
        if _away > 1.0:
            _gd.append("the halo changed away from its gap (up to %.1f cv)" % _away)
        if _removed < 3.0:
            _gd.append("the shipped gap removes nothing (max %.1f cv)" % _removed)
        _probe = {"cx": _g["cx"], "cy": _g["cy"], "th0": -20.0, "th1": 20.0, "r0": 4.0, "r1": 30.0, "blur": 1.0}
        _inP = _sector(_probe, 6, 3) & (_cn > 40 / 255.0)
        _left = {}
        for _dep in (1.0, 0.5):
            _pp = _cpk.deepcopy(_pn)
            for _Lg in _pp["layers"]:
                if _Lg["id"] == "flare_halo":
                    _Lg["gap"] = dict(_probe, depth=_dep)
            _left[_dep] = float(_halo(_pp)[_inP].sum() / _cn[_inP].sum())
        if not (_inP.sum() > 100 and _left[1.0] < 0.03 and 0.42 < _left[0.5] < 0.58):
            _gd.append("probe gap over the bright halo (%d px) leaves %.3f at depth 1 and %.3f at depth 0.5"
                       % (int(_inP.sum()), _left[1.0], _left[0.5]))
    check("a radial layer's gap removes only its own light, only in its sector",
          not _gd, "; ".join(_gd) if _gd else
          "shipped halo gap: never brighter (max %+.2f cv), removes up to %.0f cv, identical away from its "
          "sector (max %.2f cv); a probe gap over the bright halo (%d px) leaves %.1f%% at depth 1 and "
          "%.1f%% at depth 0.5; no mask without a gap"
          % (_added, _removed, _away, int(_inP.sum()), 100 * _left[1.0], 100 * _left[0.5]))

    # ---- an arc's convex taper acts only on its flare-facing side (D67) ---- #
    # arc_glow2 is split at each curve (1.5 px towards the flare, inside the
    # curve's bright core): its concave part keeps the layer's own taper, the
    # flare-facing part takes `convex_taper`.  Three things must hold:
    # - the split is a partition: with the convex taper set to the layer's own
    #   taper, the whole composite equals the unsplit build (the anti-aliased
    #   seam is screened out by the core);
    # - the convex taper changes the layer nowhere on the concave side, and
    #   does change it on the flare side;
    # - without a convex taper no split is emitted, and the optimiser counts
    #   the convex taper's user, or it would never search that taper.
    _cvL = [L["id"] for L in params["layers"] if L.get("convex_taper")]
    _cvd = []
    if _cvL != ["arc_glow2"]:
        _cvd.append("layers with a convex taper: %s (expected arc_glow2)" % _cvL)
    else:
        _pcn, _pci = _cpk.deepcopy(params), _cpk.deepcopy(params)
        for _Lc in _pcn["layers"]:
            _Lc.pop("convex_taper", None)
        for _Lc in _pci["layers"]:
            if _Lc.get("convex_taper"):
                _Lc["convex_taper"] = _Lc["taper"]
        _svn = build_svg.build(_pcn)
        if "url(#cv" in _svn or "url(#cc" in _svn:
            _cvd.append("a stack without a convex taper still emits a split")
        _cvI = float(np.abs(_FP.render_array(build_svg.build(_pci), 1024).astype(np.float64)
                            - _FP.render_array(_svn, 1024).astype(np.float64)).max() * 255)
        if _cvI > 1.01:
            _cvd.append("the identity split differs from the unsplit build by %.1f cv" % _cvI)
        _dS = regions.curve_frame((1024, 1024))[0]      # < 0 on the concave side
        _cvS = np.abs(_FP.render_array(build_svg.build(params, basis="arc_glow2"), 1024)[..., 0].astype(np.float64)
                      - _FP.render_array(build_svg.build(_pci, basis="arc_glow2"), 1024)[..., 0]) * 255
        _cvC, _cvF = float(_cvS[_dS < -1.0].max()), float(_cvS[_dS > 3.0].max())
        if _cvC > 0.5:
            _cvd.append("the convex taper changes the concave side (up to %.1f cv)" % _cvC)
        if _cvF < 3.0:
            _cvd.append("the convex taper changes nothing on the flare side (max %.1f cv)" % _cvF)
        _cvU = [sp["affects"] for sp in O.taper_specs(params) if sp["path"].startswith("tapers/glow2_cv/")]
        if not _cvU or any(u != ["arc_glow2"] for u in _cvU):
            _cvd.append("taper_specs does not search glow2_cv for arc_glow2 (%s)" % _cvU)
    check("an arc's convex taper acts only on its flare-facing side",
          not _cvd, "; ".join(_cvd) if _cvd else
          "arc_glow2 split at its curves: the identity split matches the unsplit composite (max %.2f cv); "
          "the shipped convex taper changes the layer by 0 cv on the concave side and up to %.0f cv on the "
          "flare side; no split without a convex taper; glow2_cv searched (%d specs)"
          % (_cvI, _cvF, len(_cvU)))

    # ---- a width-tapered arc narrows only where its table says (D67) ------- #
    # arc_core carries `width_taper`: its width runs 6.832 px over the curves'
    # middle and narrows toward the tips (D67; its tips and knees re-measured
    # in D71), where the reference's core is narrower.  A stroke's width is
    # constant, so such a layer is drawn as a filled outline
    # (build_svg.ribbon_path).  Checked:
    # - its coverage across the curve is the table's factor times the stroke's:
    #   the factor at the tips, 1 in the middle (coverage integrates the blur,
    #   so this reads the width itself);
    # - at factor 1 the outline follows the curve of record (half-level centre
    #   against the analytic cubics).  It follows it more closely than resvg's
    #   stroke, whose flattening chords sit up to 0.26 px on the concave side;
    # - a layer without the key is still a stroke.
    # All three are read without `end_blur` (D71): they are about the outline,
    # and the end rows' sharper blur moves a half-level centre by 0.02-0.03 px.
    # The bands come from the table itself, so a table that leaves one empty is
    # a failure of the check, reported by name (D72: a one-row table raised an
    # IndexError, and the detail's indexing was safe only by coincidence).
    def _width_taper_check(p):
        """(problems, detail) for `p`'s width-tapered arc"""
        wtd = []
        wtl = [L["id"] for L in p["layers"] if L.get("width_taper")]
        if wtl != ["arc_core"]:
            return ["layers with a width taper: %s (expected arc_core)" % wtl], ""
        pwt = _cpk.deepcopy(p)
        for Lw in pwt["layers"]:
            Lw.pop("end_blur", None)
        pws, pw1 = _cpk.deepcopy(pwt), _cpk.deepcopy(pwt)
        for Lw in pws["layers"]:
            Lw.pop("width_taper", None)
        for Lw in pw1["layers"]:
            if Lw.get("width_taper"):
                Lw["width_taper"] = [[y, 1.0] for y, _ in Lw["width_taper"]]
        svs = build_svg.build(pws, basis="arc_core")
        svt = build_svg.build(pwt, basis="arc_core")
        if 'stroke="none"' in svs or 'stroke-width' not in svs:
            wtd.append("an arc without a width taper is not drawn as a stroke")
        if 'stroke="none"' not in svt:
            wtd.append("the width-tapered arc is not drawn as a filled outline")
        ws, w1, wt = (_FP.render_array(sv, 1024)[..., 0].astype(np.float64)
                      for sv in (svs, build_svg.build(pw1, basis="arc_core"), svt))
        near = np.abs(regions.curve_frame((1024, 1024))[0]) < 12
        yyw = np.mgrid[0:1024, 0:1024][0] + 0.5
        rows = [(int(y), float(fa)) for y, fa in [L for L in p["layers"] if L["id"] == "arc_core"][0]["width_taper"]]
        # the bands read, each with the factor it must show: the north tip short
        # of the table's first row, the south tip past its last, and the longest
        # stretch between two rows at factor 1, 10 rows inside it
        flat = [(r0[0], r1[0]) for r0, r1 in zip(rows, rows[1:]) if r0[1] == 1.0 and r1[1] == 1.0]
        mid = max(flat, key=lambda ab: ab[1] - ab[0]) if flat else None
        bands = (("north tip", (100, rows[0][0] - 5), rows[0][1], 0.003),
                 ("south tip", (rows[-1][0] + 20, 930), rows[-1][1], 0.003),
                 ("middle", (mid[0] + 10, mid[1] - 10) if mid else None, 1.0, 0.002))
        cov = {}
        for nm, band, want, tol in bands:
            if band is None:
                wtd.append("the table has no two rows at factor 1, so the middle band is missing")
                continue
            y0, y1 = band
            if y1 < y0 + 10:
                wtd.append("the table leaves the %s band empty (y %d-%d)" % (nm, y0, y1))
                continue
            mw = near & (yyw >= y0) & (yyw < y1)
            cov[nm] = float(wt[mw].sum() / ws[mw].sum()) if ws[mw].sum() > 0 else float("nan")
            if not np.isfinite(cov[nm]) or abs(cov[nm] - want) > tol:
                wtd.append("coverage of the %s band (y %d-%d) is %.4f of the stroke's (expected %.4f)"
                           % (nm, y0, y1, cov[nm], want))

        def half_centre(row, lo, hi):
            seg = row[lo:hi]
            k = int(np.argmax(seg))
            h = seg[k] / 2
            i = k
            while i > 0 and seg[i] > h:
                i -= 1
            j = k
            while j < len(seg) - 1 and seg[j] > h:
                j += 1
            xl = i + (h - seg[i]) / (seg[i + 1] - seg[i])
            xr = j - 1 + (seg[j - 1] - h) / (seg[j - 1] - seg[j])
            return lo + (xl + xr) / 2 + 0.5

        def curve_x(side, yq):
            for seg in p["geometry"]["arc_" + side]["cubics"][side]:
                t = np.linspace(0, 1, 20001)
                u = 1 - t
                P = np.asarray(seg, float)
                x = u ** 3 * P[0, 0] + 3 * u * u * t * P[1, 0] + 3 * u * t * t * P[2, 0] + t ** 3 * P[3, 0]
                y = u ** 3 * P[0, 1] + 3 * u * u * t * P[1, 1] + 3 * u * t * t * P[2, 1] + t ** 3 * P[3, 1]
                if y.min() <= yq <= y.max():
                    o = np.argsort(y)
                    return float(np.interp(yq, y[o], x[o]))
            return None
        cerr = {}
        for sd, (lo, hi) in (("left", (150, 530)), ("right", (533, 900))):
            e1, es = [], []
            for y in range(110, 930, 10):
                xa = curve_x(sd, y + 0.5)
                if xa is None:
                    continue
                e1.append(abs(half_centre(w1[y], lo, hi) - xa))
                es.append(abs(half_centre(ws[y], lo, hi) - xa))
            cerr[sd] = (max(e1), max(es))
            if max(e1) > 0.15:
                wtd.append("the outline strays %.2f px from the %s curve of record" % (max(e1), sd))
        return wtd, ("arc_core's outline: coverage %s of the stroke's; at factor 1 its centre stays within %.2f / "
                     "%.2f px of the curve of record (left / right; resvg's stroke %.2f / %.2f); an arc without a "
                     "width taper is still a stroke"
                     % (", ".join("%s %.4f (table %.4f)" % (nm, cov[nm], want)
                                  for nm, _b, want, _t in bands if nm in cov),
                        cerr["left"][0], cerr["right"][0], cerr["left"][1], cerr["right"][1]))

    _wtd, _wtr = _width_taper_check(params)
    check("a width-tapered arc narrows only where its table says",
          not _wtd, "; ".join(_wtd) if _wtd else _wtr)

    # ---- ... and says so, not crashes, when a table empties a band (D72) --- #
    # Tables that leave one of the check's bands empty, each of which the
    # builder accepts: the check must return a failure that names the band.
    _wbd, _wbr = [], []
    for _tab, _nm in (([[170, 0.905]], "middle"),
                      ([[170, 0.905], [500, 1.0], [860, 0.888]], "middle"),
                      ([[100, 0.905], [240, 1.0], [790, 1.0], [860, 0.888]], "north tip"),
                      ([[170, 0.905], [240, 1.0], [790, 1.0], [915, 0.888]], "south tip")):
        _pbw = _cpk.deepcopy(params)
        [L for L in _pbw["layers"] if L["id"] == "arc_core"][0]["width_taper"] = _tab
        try:
            _prw, _ = _width_taper_check(_pbw)
        except Exception as _ew:
            # the defect this exists for: record it as this check's failure
            _wbd.append("table %s: the check raised %s: %s" % (_tab, type(_ew).__name__, _ew))
            continue
        _hit = [x for x in _prw if _nm in x]
        if not _hit:
            _wbd.append("table %s: no failure names the %s band (%s)" % (_tab, _nm, "; ".join(_prw) or "passed"))
        else:
            _wbr.append("%s -> %s" % (_tab, _hit[0]))
    check("the width-taper check reports a band its table empties as a failure",
          not _wbd, "; ".join(_wbd) if _wbd else "; ".join(_wbr))

    # ---- an extended arc runs past its ends only along its own curve (D68) - #
    # arc_core_tip carries `extend`: its stroke runs that many px of arc length
    # past both ends of each curve of record, along the end cubic's own
    # polynomial (build_svg.extended_cubics).  The cubics of record are not
    # changed.  Checked:
    # - each added cubic is its end cubic continued: every point of it lies on
    #   that cubic's polynomial evaluated past [0, 1], it meets the curve at the
    #   end point, and its arc length is `extend`;
    # - drawn without its table, the layer lies within a stroke's reach of the
    #   curve of record and those continuations, and it does reach past both
    #   ends of both curves;
    # - without the key it is the plain stroke on the cubics of record;
    # - `extend` refuses to combine with width_taper or convex_taper, and the
    #   optimiser counts the tip table's user.
    _exL = [L["id"] for L in params["layers"] if L.get("extend")]
    _exd, _exR, _exU = [], {}, []
    if _exL != ["arc_core_tip"]:
        _exd.append("layers with an extension: %s (expected arc_core_tip)" % _exL)
    elif not hasattr(build_svg, "extended_cubics"):
        # a builder without the option would draw the layer without its tail
        _exd.append("the builder cannot extend an arc (no build_svg.extended_cubics)")
    else:
        _Lx = [L for L in params["layers"] if L["id"] == "arc_core_tip"][0]
        _ext = float(_Lx["extend"])

        def _bez(P, t):
            u = 1 - t
            return (np.outer(u ** 3, P[0]) + np.outer(3 * u * u * t, P[1])
                    + np.outer(3 * u * t * t, P[2]) + np.outer(t ** 3, P[3]))

        def _arclen(P):
            q = _bez(P, np.linspace(0, 1, 4001))
            return float(np.hypot(*np.diff(q, axis=0).T).sum())

        _tt = np.linspace(0, 1, 201)
        _paths, _plain, _past = [], [], []
        for _sd in ("left", "right"):
            _cps = params["geometry"]["arc_" + _sd]["cubics"][_sd]
            _xc = build_svg.extended_cubics(_cps, _ext)
            if [[list(map(float, q)) for q in c] for c in _xc[1:-1]] != \
                    [[list(map(float, q)) for q in c] for c in _cps]:
                _exd.append("the %s curve's cubics of record are changed" % _sd)
            for _P, _Q, _fw in ((np.asarray(_cps[-1], float), np.asarray(_xc[-1], float), True),
                                (np.asarray(_cps[0], float), np.asarray(_xc[0], float), False)):
                # the added cubic is P on [1, 1 + tau] (or [-tau, 0]); its first
                # control leg is tau/3 of P's end tangent, which gives tau
                if _fw:
                    _tau = 3 * np.hypot(*(_Q[1] - _Q[0])) / np.hypot(*(3 * (_P[3] - _P[2])))
                    _on = _bez(_P, 1 + _tau * _tt)
                    _join = np.hypot(*(_Q[0] - _P[3]))
                else:
                    _tau = 3 * np.hypot(*(_Q[3] - _Q[2])) / np.hypot(*(3 * (_P[1] - _P[0])))
                    _on = _bez(_P, -_tau + _tau * _tt)
                    _join = np.hypot(*(_Q[3] - _P[0]))
                _off = float(np.hypot(*(_bez(_Q, _tt) - _on).T).max())
                _len = _arclen(_Q)
                if _join > 1e-9 or _off > 1e-6 or abs(_len - _ext) > 0.01:
                    _exd.append("a %s continuation leaves its cubic (join %.2g px, off the polynomial %.2g px, "
                                "length %.3f of %.1f)" % (_sd, _join, _off, _len, _ext))
                _exR[_sd + ("S" if _fw == (_P[3][1] > _P[0][1]) else "N")] = (_off, _len)
                _past.append(_bez(_Q, np.array([0.2, 0.5, 0.8])))
            _paths.append(np.concatenate([_bez(np.asarray(c, float), np.linspace(0, 1, 400)) for c in _xc]))
            _plain.append(np.concatenate([_bez(np.asarray(c, float), np.linspace(0, 1, 400)) for c in _cps]))

        def _reach(img, pts):
            yx = np.argwhere(img > 2.0)
            px = yx[:, ::-1] + 0.5
            out = 0.0
            for _k in range(0, len(px), 2000):
                d = np.sqrt(((px[_k:_k + 2000, None, :] - pts[None]) ** 2).sum(-1)).min(1)
                out = max(out, float(d.max()))
            return out

        # the probe draws the layer at a fixed stroke on the curve itself, so
        # the check reads the extension's geometry, not the fitted inset, width
        # or blur (all three are searchable within the layer's bounds)
        _probe = {"inset": 0.0, "width": 6.4, "blur": 0.6}
        _pU, _pP = _cpk.deepcopy(params), _cpk.deepcopy(params)
        for _q in (_pU, _pP):
            for _L in _q["layers"]:
                if _L["id"] == "arc_core_tip":
                    _L.pop("taper", None)
                    _L.pop("taper_axis", None)      # nothing to paint without the table (D70)
                    _L.update(_probe)
                    if _q is _pP:
                        _L.pop("extend", None)
        _svU, _svP = build_svg.build(_pU, basis="arc_core_tip"), build_svg.build(_pP, basis="arc_core_tip")
        _imU = _FP.render_array(_svU, 1024)[..., 0].astype(np.float64) * 255
        _imP = _FP.render_array(_svP, 1024)[..., 0].astype(np.float64) * 255
        # half the stroke, three blur sigmas and a pixel's half-diagonal
        _lim = _probe["width"] / 2 + 3 * _probe["blur"] + 0.75
        _rU, _rP = _reach(_imU, np.concatenate(_paths)), _reach(_imP, np.concatenate(_plain))
        if _rU > _lim:
            _exd.append("the extended layer lights a pixel %.2f px from its path (limit %.2f)" % (_rU, _lim))
        if _rP > _lim:
            _exd.append("without `extend` the layer lights a pixel %.2f px from the curve of record" % _rP)
        _pv = np.concatenate(_past)
        _atU = _imU[_pv[:, 1].astype(int), _pv[:, 0].astype(int)]
        _atP = _imP[_pv[:, 1].astype(int), _pv[:, 0].astype(int)]
        if _atU.min() < 200:
            _exd.append("the extension is not drawn past every end (%.0f cv at its weakest sample)" % _atU.min())
        if _atP.max() > 1:
            _exd.append("without `extend` the layer still reaches past an end (%.0f cv)" % _atP.max())
        for _sd in ("left", "right"):
            if ('d="%s"' % build_svg.bezier_arc_path(params["geometry"]["arc_" + _sd], _sd, 0.0)
                    not in _svP):
                _exd.append("without `extend` the %s stroke is not the curve of record's path" % _sd)
        for _extra, _nm in (({"width_taper": [[100.0, 1.0], [900.0, 1.0]]}, "width_taper"),
                            ({"convex_taper": _Lx["taper"]}, "convex_taper")):
            _pR = _cpk.deepcopy(params)
            [_L for _L in _pR["layers"] if _L["id"] == "arc_core_tip"][0].update(_extra)
            try:
                build_svg.build(_pR)
                _exd.append("`extend` with %s builds instead of refusing" % _nm)
            except AssertionError:
                pass
        # a length past the end cubic's own span is refused, not clamped
        try:
            build_svg.extended_cubics(params["geometry"]["arc_right"]["cubics"]["right"], 5000.0)
            _exd.append("an extension past the end cubic's span is clamped instead of refused")
        except ValueError:
            pass
        _exU = [sp["affects"] for sp in O.taper_specs(params) if sp["path"].startswith("tapers/%s/" % _Lx["taper"])]
        if not _exU or any(u != ["arc_core_tip"] for u in _exU):
            _exd.append("taper_specs does not search %s for arc_core_tip (%s)" % (_Lx["taper"], _exU))
    check("an extended arc runs past its ends only along its own curve",
          not _exd, "; ".join(_exd) if _exd else
          "arc_core_tip: four continuations on their end cubics' polynomials (max %.1g px off), each %.3f px "
          "long; lit pixels within %.2f px of the extended path (limit %.2f), %.0f-%.0f cv past every end; "
          "without the key: the plain stroke, within %.2f px of the curve of record, %.0f cv past the ends; "
          "refused with width_taper and convex_taper, and past the end cubic's span; %s searched (%d specs)"
          % (max(v[0] for v in _exR.values()), min(v[1] for v in _exR.values()), _rU, _lim,
             _atU.min(), _atU.max(), _rP, _atP.max(), _Lx["taper"], len(_exU)))

    # ---- a curve-axis fade follows each end's own curve (D70) ------------- #
    # `taper_axis: "curve"` paints a layer's table along the curve at an end
    # instead of along y (build_svg.curve_axis_stops): along y, the rows cross
    # the curves' oblique ends and tilt the fade across the stroke, toward the
    # lens at every end.  Checked on arc_core (a ribbon) and arc_core_tip (an
    # extended stroke), each drawn alone in white with all four ends on the
    # curve:
    # - across the stroke the light is centred on the layer's own path, within
    #   0.2 px, wherever the centre line carries 20 cv, inside the ends and on
    #   the tip layer's continuation past them; the same layer painted along y
    #   is off by more than 0.3 px somewhere, so the check is not vacuous;
    # - along the centre line it is the y-paint's fade (within 3 cv or 4%):
    #   only the cross-section turns;
    # - outside the ends' zones it is the y-paint render, pixel for pixel, and
    #   every path it draws is the plain layer's (the curve is not moved);
    #   each zone's edge is a multiple of 4 px, whole pixel rows at 1024;
    # - at 1000 px, a size whose pixel rows the zone edges cut, the rows at
    #   each zone edge are the y-paint's within 2 cv: the edge is no seam
    #   (a zone cut by a shape's anti-aliased edge left a line of 30-110 cv);
    # - its directions come from the curve: an end cubic turned 6 degrees
    #   turns that end's gradient with it, and the light follows the new path;
    #   a longer end handle moves that end's zone to the new curve's own
    #   half-turn row;
    # - the same holds with each layer inset to the end of its range (0.8 and
    #   2 px): the fade follows the path the layer draws;
    # - "y" everywhere builds the file without the key, byte for byte, in each
    #   spelling, and a file without "curve" carries none of its markup; an
    #   unknown axis, a value neither a string nor a dict, a ramp taper, a
    #   convex_taper layer, an untapered layer and a layer that is not an arc
    #   are refused.
    # Then the shipped file: outside the zones of the ends it paints along the
    # curve, its render is the render without the key.
    _cad, _car = [], []

    def _cag(cps, which, us):
        """points, unit tangents (outward past the end) and flare-side normals
        at arc lengths `us` from the end of the end cubic of `cps`"""
        c = np.asarray(cps[0] if which == "north" else cps[-1], float)
        te, sg = (0.0, -1.0) if which == "north" else (1.0, 1.0)
        ts = np.linspace(te - sg, te + sg * 0.6, 60001)[:, None]
        v = 1 - ts
        P = v ** 3 * c[0] + 3 * v * v * ts * c[1] + 3 * v * ts * ts * c[2] + ts ** 3 * c[3]
        D = (3 * v * v * (c[1] - c[0]) + 6 * v * ts * (c[2] - c[1]) + 3 * ts * ts * (c[3] - c[2])) * sg
        s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
        s -= s[int(np.argmin(np.abs(ts[:, 0] - te)))]
        k = np.searchsorted(s, us)
        d = D[k] / np.hypot(D[k][:, 0], D[k][:, 1])[:, None]
        nrm = np.stack([-d[:, 1], d[:, 0]], 1)
        return P[k], d, nrm

    def _caxs(img, p, d, nrm, ns):
        """cross-sections of `img` along `nrm` at offsets `ns`, averaged over
        +-2 px along the curve (bilinear, pixel centres at +0.5)"""
        out = []
        for i in range(len(p)):
            acc = 0.0
            for o in np.arange(-2.0, 2.01, 0.5):
                q = p[i] + o * d[i] + ns[:, None] * nrm[i]
                x, y = q[:, 0] - 0.5, q[:, 1] - 0.5
                x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
                fx, fy = x - x0, y - y0
                acc = acc + (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
                             + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
            out.append(acc / 9.0)
        return np.array(out)

    def _caren(q, lid):
        return _FP.render_array(build_svg.build(q, basis=lid), 1024)[..., 0].astype(np.float64) * 255

    def _cawith(lid, axis, base=None):
        q = _cpk.deepcopy(params if base is None else base)
        for _L in q["layers"]:
            if _L["id"] == lid:
                if axis is None:
                    _L.pop("taper_axis", None)
                else:
                    _L["taper_axis"] = axis
        return q

    _ns = np.arange(-6.0, 6.001, 0.25)
    _zmarg = 3
    for _lid, _ins in (("arc_core", None), ("arc_core_tip", None), ("arc_core", 0.8), ("arc_core_tip", 2.0)):
        _base = params
        if _ins is not None:
            _base = _cpk.deepcopy(params)
            [L for L in _base["layers"] if L["id"] == _lid][0]["inset"] = _ins
        _Lc = [L for L in _base["layers"] if L["id"] == _lid][0]
        _qC, _qY = _cawith(_lid, "curve", _base), _cawith(_lid, None, _base)
        _imC, _imY = _caren(_qC, _lid), _caren(_qY, _lid)
        _lab = _lid if _ins is None else "%s (inset %g)" % (_lid, _ins)
        _svC, _svY = build_svg.build(_qC, basis=_lid), build_svg.build(_qY, basis=_lid)
        # the curve is not moved: every path drawn is one the plain layer draws
        _dC = __import__("re").findall(r' d="([^"]+)"', _svC.split("</defs>")[1])
        _dY = __import__("re").findall(r' d="([^"]+)"', _svY.split("</defs>")[1])
        if not _dC or sorted(_dC) != sorted(_dY):
            _cad.append("%s: the paths drawn with the key are not the plain layer's" % _lab)
        _zr = np.zeros(1024, bool)
        _ext = float(_Lc.get("extend", 0.0))
        for _sd in ("left", "right"):
            _cps = build_svg.inset_cubics(_base["geometry"]["arc_" + _sd], _sd, _Lc.get("inset", 0.0))
            for _wh in ("north", "south"):
                _E, _T, _st, _yz = build_svg.curve_axis_stops(_base["tapers"][_Lc["taper"]], _sd, _cps, _wh,
                                                               _ext + 0.5 * float(_Lc["width"]) + 4.0)
                if _yz % 4:
                    _cad.append("%s %s%s: the zone edge y %.2f is not a multiple of 4 px"
                                % (_lab, _sd[0].upper(), _wh[0].upper(), _yz))
                if _wh == "north":
                    _zr[:int(_yz) + _zmarg] = True
                else:
                    _zr[int(_yz) - _zmarg:] = True
                _us = np.arange(-100.0, (_ext - 5.0 if _ext else 0.0) + 0.01, 2.5)
                _p, _d, _n = _cag(_cps, _wh, _us)
                _XC, _XY = _caxs(_imC, _p, _d, _n, _ns), _caxs(_imY, _p, _d, _n, _ns)
                _mid = len(_ns) // 2
                _cenC = (np.clip(_XC, 0, None) * _ns).sum(1) / np.maximum(np.clip(_XC, 0, None).sum(1), 1e-9)
                _cenY = (np.clip(_XY, 0, None) * _ns).sum(1) / np.maximum(np.clip(_XY, 0, None).sum(1), 1e-9)
                _lit = _XY[:, _mid] >= 20.0
                _tag = "%s %s%s" % (_lab, _sd[0].upper(), _wh[0].upper())
                if not _lit.any():
                    _cad.append("%s: no lit centre line to read" % _tag)
                    continue
                _mc, _my = np.abs(_cenC[_lit]).max(), np.abs(_cenY[_lit]).max()
                if _mc > 0.2:
                    _cad.append("%s: the curve paint is %.2f px off its path" % (_tag, _mc))
                if _my <= 0.3:
                    _cad.append("%s: the y-paint is only %.2f px off; the check is vacuous" % (_tag, _my))
                _dv = np.abs(_XC[_lit, _mid] - _XY[_lit, _mid])
                if (_dv > np.maximum(3.0, 0.04 * _XY[_lit, _mid])).any():
                    _cad.append("%s: the centre line's fade changes by %.1f cv" % (_tag, _dv.max()))
                _car.append("%s %.2f (y %.2f)" % (_tag, _mc, _my))
        # outside the zones it is the y-paint render: where a zone edge splits
        # one of the table's gradient segments, resvg may round a pixel of that
        # segment one level apart, and nowhere else
        _out = np.abs(_imC - _imY)[~_zr]
        _nlit = int((_imY > 2.0).sum())
        if _out.max() > 1.0 or (_out > 0).sum() > max(12, 0.002 * _nlit):
            _cad.append("%s: %d pixels change outside the ends' zones, by up to %.0f cv"
                        % (_lab, int((_out > 0).sum()), _out.max()))
        _car.append("%s outside the zones: %d of %d lit pixels one level apart" % (_lab, int((_out > 0).sum()), _nlit))
        # no seam at a size whose rows the zone edges cut: the device rows
        # within a row of each zone edge, the curve paint against the y-paint
        _N = 1000
        _s1 = _FP.render_array(_svC, _N)[..., 0].astype(np.float64) * 255
        _s0 = _FP.render_array(_svY, _N)[..., 0].astype(np.float64) * 255
        _uy = (np.arange(_N) + 0.5) * 1024.0 / _N
        _er = np.zeros(_N, bool)
        for _sd in ("left", "right"):
            _cps = build_svg.inset_cubics(_base["geometry"]["arc_" + _sd], _sd, _Lc.get("inset", 0.0))
            for _wh in ("north", "south"):
                _yz = build_svg.curve_axis_stops(_base["tapers"][_Lc["taper"]], _sd, _cps, _wh,
                                                 _ext + 0.5 * float(_Lc["width"]) + 4.0)[3]
                _er |= np.abs(_uy - _yz) < 1.5 * 1024.0 / _N
        _seam = float(np.abs(_s1 - _s0)[_er].max())
        if _seam > 2.0:
            _cad.append("%s at %d px: the zone edges' rows differ from the y-paint by %.0f cv (a seam)"
                        % (_lab, _N, _seam))
        _car.append("%s at %d px: zone-edge rows within %.0f cv of the y-paint" % (_lab, _N, _seam))
        # "y" everywhere is the file without the key, in every spelling
        if _ins is None:
            _fY = build_svg.build(_qY)
            for _spell in ("y", {"north": "y", "south": "y"}, {"south": "y"}, {}):
                if build_svg.build(_cawith(_lid, _spell)) != _fY:
                    _cad.append("%s: taper_axis %r does not build the file without the key" % (_lid, _spell))
    # and a file with no "curve" end carries none of the option's markup
    _qn = _cpk.deepcopy(params)
    for _L in _qn["layers"]:
        _L.pop("taper_axis", None)
    _fn = build_svg.build(_qn)
    if 'id="g2a"' in _fn or 'id="mg_' in _fn:
        _cad.append("a file without a curve-axis end still carries its mask or filter")

    # the directions come from the curve: turn the left curve's north end 6
    # degrees about its end point (first cubic's c1 rotated about c0)
    _qR = _cawith("arc_core", {"north": "curve"})
    _cR = _qR["geometry"]["arc_left"]["cubics"]["left"]
    _c0, _c1 = np.asarray(_cR[0][0], float), np.asarray(_cR[0][1], float)
    _rot = np.radians(6.0)
    _v = _c1 - _c0
    _cR[0][1] = list(_c0 + [_v[0] * np.cos(_rot) - _v[1] * np.sin(_rot), _v[0] * np.sin(_rot) + _v[1] * np.cos(_rot)])
    _svR = build_svg.build(_qR, basis="arc_core")
    _gm = __import__("re").search(r'<linearGradient id="g_arc_corel(n)" gradientUnits="userSpaceOnUse" '
                                   r'x1="([^"]+)" y1="([^"]+)" x2="([^"]+)" y2="([^"]+)"', _svR)
    if not _gm:
        _cad.append("the turned curve's north gradient is missing")
    else:
        _gv = np.array([float(_gm.group(4)) - float(_gm.group(2)), float(_gm.group(5)) - float(_gm.group(3))])
        _tn = (_c0 - np.asarray(_cR[0][1], float))
        _ang = np.degrees(np.arctan2(_gv[0] * _tn[1] - _gv[1] * _tn[0], _gv @ _tn))
        if abs(_ang) > 0.05:
            _cad.append("the turned end's gradient is %.2f deg off its new tangent" % _ang)
        _imR = _FP.render_array(_svR, 1024)[..., 0].astype(np.float64) * 255
        _p, _d, _n = _cag(_cR, "north", np.arange(-100.0, 0.01, 2.5))
        _XR = _caxs(_imR, _p, _d, _n, _ns)
        _cenR = (np.clip(_XR, 0, None) * _ns).sum(1) / np.maximum(np.clip(_XR, 0, None).sum(1), 1e-9)
        _litR = _XR[:, len(_ns) // 2] >= 20.0
        if not _litR.any() or np.abs(_cenR[_litR]).max() > 0.2:
            _cad.append("on the turned curve the light is %.2f px off the new path"
                        % (np.abs(_cenR[_litR]).max() if _litR.any() else float("nan")))
        _car.append("turned 6 deg: gradient %.3f deg off the new tangent, light %.2f px off"
                    % (abs(_ang), np.abs(_cenR[_litR]).max() if _litR.any() else float("nan")))
    # the zone comes from the curve as well: the right curve's north handle
    # made 1.4 times as long moves its half-turn, and the zone the mask draws
    # goes with it, to that half-turn's own row rounded outward to 4 px
    _qZ = _cawith("arc_core", {"north": "curve"})
    _cZ = _qZ["geometry"]["arc_right"]["cubics"]["right"]
    _z0 = np.asarray(_cZ[0][0], float)
    _cZ[0][1] = list(_z0 + 1.4 * (np.asarray(_cZ[0][1], float) - _z0))
    _cz = np.asarray(_cZ[0], float)
    _tt = np.linspace(0.0, 1.0, 200001)[:, None]
    _vv = 1 - _tt
    _Dz = 3 * _vv * _vv * (_cz[1] - _cz[0]) + 6 * _vv * _tt * (_cz[2] - _cz[1]) + 3 * _tt * _tt * (_cz[3] - _cz[2])
    _az = np.degrees(np.arctan2(np.abs(_Dz[:, 1]), np.abs(_Dz[:, 0])))
    _th = _tt[int(np.argmax(_az >= _az[0] + (90.0 - _az[0]) / 2.0)), 0]
    _yh = (1 - _th) ** 3 * _cz[0][1] + 3 * (1 - _th) ** 2 * _th * _cz[1][1] + 3 * (1 - _th) * _th ** 2 * _cz[2][1] \
        + _th ** 3 * _cz[3][1]
    _want = 4.0 * np.ceil(_yh / 4.0)
    _Lz = [L for L in params["layers"] if L["id"] == "arc_core"][0]
    _was = build_svg.curve_axis_stops(params["tapers"][_Lz["taper"]], "right",
                                      build_svg.inset_cubics(params["geometry"]["arc_right"], "right", 0.0),
                                      "north", 7.4)[3]
    _svZ = build_svg.build(_qZ, basis="arc_core")
    if _want == _was:
        _cad.append("the lengthened handle leaves the zone at y %.0f; the probe is vacuous" % _was)
    elif '<rect y="0" width="1024" height="%s" fill="url(#g_arc_corern)"/>' % build_svg.f(_want) not in _svZ:
        _cad.append("the right north zone does not follow the curve to y %.0f (its own half-turn)" % _want)
    _car.append("a 1.4x handle: zone %.0f -> %.0f, the new half-turn's" % (_was, _want))
    # refusals
    for _lid2, _extra, _nm in (("arc_core", {"taper_axis": "diagonal"}, "an unknown axis"),
                               ("arc_core", {"taper_axis": True}, "a value neither a string nor a dict"),
                               ("arc_core_wide", {"taper_axis": "curve"}, "a ramp taper"),
                               ("arc_glow2", {"taper_axis": "curve"}, "a convex_taper layer"),
                               ("arc_glow2b", {"taper_axis": "curve"}, "an untapered layer"),
                               ("flare_halo", {"taper_axis": "curve"}, "a layer that is not an arc")):
        _qX = _cpk.deepcopy(params)
        [L for L in _qX["layers"] if L["id"] == _lid2][0].update(_extra)
        try:
            build_svg.build(_qX)
            _cad.append("%s builds instead of refusing" % _nm)
        except AssertionError:
            pass
    # the shipped file: nothing outside the zones of its curve-painted ends
    _shipped = {L["id"]: L["taper_axis"] for L in params["layers"] if L.get("taper_axis")}
    _q0 = _cpk.deepcopy(params)
    for _L in _q0["layers"]:
        _L.pop("taper_axis", None)
    _zs = np.zeros(1024, bool)
    for _lid, _ax in _shipped.items():
        _Lc = [L for L in params["layers"] if L["id"] == _lid][0]
        _ax = {"north": _ax, "south": _ax} if isinstance(_ax, str) else _ax
        for _sd in ("left", "right"):
            _cps = build_svg.inset_cubics(params["geometry"]["arc_" + _sd], _sd, _Lc.get("inset", 0.0))
            for _wh in ("north", "south"):
                if _ax.get(_wh) == "curve":
                    _yz = build_svg.curve_axis_stops(params["tapers"][_Lc["taper"]], _sd, _cps, _wh,
                                                     float(_Lc.get("extend", 0.0)) + 0.5 * float(_Lc["width"]) + 4.0)[3]
                    if _wh == "north":
                        _zs[:int(_yz) + _zmarg] = True
                    else:
                        _zs[int(_yz) - _zmarg:] = True
    _im1 = _FP.render_array(build_svg.build(params), 1024)
    _im0 = _FP.render_array(build_svg.build(_q0), 1024)
    _dd = np.abs(_im1 - _im0).max(-1) * 255
    _nout, _nin = int((_dd > 0)[~_zs].sum()), int((_dd > 0).sum())
    if _dd[~_zs].max() > 1.0 or _nout > 12:
        _cad.append("the shipped file changes %d pixels outside its curve-painted ends' zones" % _nout)
    check("a curve-axis fade follows each end's own curve",
          not _cad, "; ".join(_cad) if _cad else
          "light off its own path (y-paint): %s; centre lines within 3 cv or 4%%; paths unchanged; %s; "
          "'y' everywhere is the file without the key; six misuses refused. Shipped: %s, %d pixels changed, "
          "%d outside the zones" % (", ".join(_car[:-2]), "; ".join(_car[-2:]), _shipped or "none", _nin, _nout))

    # ---- the curve-axis paint itself: no tilt, and y's again at the zone edge #
    # The emitted paint, evaluated as SVG defines it: Y along y, T and its
    # weight w along the end's tangent, (1 - w) Y + w T.  On arc_core's table,
    # at every end:
    # - along the curve up to a quarter-turn toward vertical, the paint changes
    #   across the stroke at most 0.03 times as fast as along it, at the 95th
    #   percentile (the y-paint: 1.9-2.2 times; the end's tangent alone:
    #   0.26-0.30);
    # - on the centre line it is the y-paint's value (within 0.002);
    # - at the zone's edge it is the y-paint within 0.0005 on and off the line.
    _cmd, _cmr, _edges = [], [], []
    _Lc = [L for L in params["layers"] if L["id"] == "arc_core"][0]
    _tab = params["tapers"][_Lc["taper"]]
    for _sd in ("left", "right"):
        _st = build_svg.taper_stops(_tab, _sd)
        _yo, _ya = np.array([o * 1024.0 for o, _ in _st]), np.array([a for _, a in _st])
        _cps = build_svg.inset_cubics(params["geometry"]["arc_" + _sd], _sd, 0.0)
        for _wh in ("north", "south"):
            _E, _T, _sts, _yz = build_svg.curve_axis_stops(_tab, _sd, _cps, _wh, 7.4)
            _E, _T = np.asarray(_E), np.asarray(_T)
            _ss = np.array([s for s, _, _ in _sts])
            _sa = np.array([a for _, a, _ in _sts])
            _sw = np.array([w for _, _, w in _sts])

            def _paint(X):
                s = (X - _E) @ _T
                w = np.interp(s, _ss, _sw)
                return (1 - w) * np.interp(X[..., 1], _yo, _ya) + w * np.interp(s, _ss, _sa)

            def _ypaint(X):
                return np.interp(X[..., 1], _yo, _ya)
            c = np.asarray(_cps[0] if _wh == "north" else _cps[-1], float)
            te = 0.0 if _wh == "north" else 1.0
            tt = np.linspace(te, 1.0 - te, 20001)[:, None]
            v = 1 - tt
            P = v ** 3 * c[0] + 3 * v * v * tt * c[1] + 3 * v * tt * tt * c[2] + tt ** 3 * c[3]
            D = 3 * v * v * (c[1] - c[0]) + 6 * v * tt * (c[2] - c[1]) + 3 * tt * tt * (c[3] - c[2])
            D /= np.hypot(D[:, 0], D[:, 1])[:, None]
            N = np.stack([-D[:, 1], D[:, 0]], 1)
            ang = np.degrees(np.arctan2(np.abs(D[:, 1]), np.abs(D[:, 0])))
            q = ang <= ang[0] + (90.0 - ang[0]) / 4.0
            h = 0.5
            across = (_paint(P + h * N) - _paint(P - h * N)) / (2 * h)
            along = (_paint(P + h * D) - _paint(P - h * D)) / (2 * h)
            acrossY = (_ypaint(P + h * N) - _ypaint(P - h * N)) / (2 * h)
            use = q & (np.abs(along) > 2e-3)
            _tag = "%s%s" % (_sd[0].upper(), _wh[0].upper())
            if use.sum() < 50:
                _cmd.append("%s: too little of the table's fade to read" % _tag)
                continue
            # 95th percentile: within half a pixel of a station the two paints
            # kink along different lines, a second-order effect of the table
            _r = np.percentile(np.abs(across[use] / along[use]), 95)
            _rY = np.percentile(np.abs(acrossY[use] / along[use]), 95)
            if _r > 0.03:
                _cmd.append("%s: the curve paint changes %.2f times as fast across the stroke as along it" % (_tag, _r))
            if _rY < 0.5:
                _cmd.append("%s: the y-paint is only %.2f; the reading is vacuous" % (_tag, _rY))
            _cl = np.abs(_paint(P[q]) - _ypaint(P[q])).max()
            if _cl > 0.002:
                _cmd.append("%s: the centre line departs from the y-paint by %.4f" % (_tag, _cl))
            _ed = np.abs(P[:, 1] - _yz) < 1.0
            _eo = np.concatenate([_paint(P[_ed] + k * N[_ed]) - _ypaint(P[_ed] + k * N[_ed]) for k in (-3, 0, 3)])
            _edges.append(np.abs(_eo).max() if _ed.any() else np.nan)
            if not _ed.any() or np.abs(_eo).max() > 0.0005:
                _cmd.append("%s: at the zone edge the paint is %.4f from the y-paint" % (_tag, np.abs(_eo).max() if _ed.any() else np.nan))
            _cmr.append("%s %.3f (y %.2f)" % (_tag, _r, _rY))
    check("the curve-axis paint has no tilt, and is the y-paint again at its zone's edge",
          not _cmd, "; ".join(_cmd) if _cmd else
          "arc_core's table, across/along (95th percentile) up to a quarter-turn: %s; the centre line within "
          "0.002 of the y-paint, the zone edges within %.1g" % (", ".join(_cmr), np.nanmax(_edges)))

    # ---- an end-blurred arc draws each row with one of its two blurs (D71) - #
    # arc_core carries `end_blur`: the rows outside arc_core_edge's
    # full-strength span (y < 300, y >= 704) are drawn with the reference's
    # sharper core blur, the rows between with the layer's own, which the
    # middle's composite edge (the core plus its cyan edge strokes) needs.
    # Each side is one group carrying the layer's blend: the end copy, then
    # the middle copy over an opaque black in a group masked to its rows after
    # its blur (hard gradient stops, read at pixel centres).
    # Checked:
    # - on the layer alone, at 1024, 2048 and 1000 px: every pixel row whose
    #   centre lies in an end zone is the layer drawn with the end blur
    #   everywhere, and every other row is the layer drawn with its own blur,
    #   to a level.  The mask selects whole rows, with no overlap and no gap,
    #   also where the cut falls inside a pixel (1000 px), where a shape's edge
    #   would be anti-aliased into both copies;
    # - at 872 px, where the south cut falls exactly on a pixel centre and the
    #   mask reads about half there: that row lies between the two renders, to
    #   a level (the copies mix linearly), and every other row is one of them.
    #   Two masked copies screened one after the other drew that row up to 45
    #   levels darker than either;
    # - on the whole composite at 1024 px, the same: the group is screened
    #   onto the canvas like the plain layer;
    # - the same on a translucent layer, `arc_lens_band` given a probe end blur
    #   (its opacity rides in each copy);
    # - the two blurs really differ there (the check is not vacuous);
    # - with the key each side is one row-masked group, without it one element
    #   and no row mask;
    # - rows that are not multiples of 4, that cross, that are missing or that
    #   are not numbers are refused, and so are an empty key and the key on a
    #   layer that is not an arc.
    _ebL = [L["id"] for L in params["layers"] if L.get("end_blur")]
    _ebd, _ebr = [], []

    def _eb_split(p_eb, lid, eb, own, size, composite):
        """For layer `lid` of `p_eb` carrying end blur `eb`: the most levels
        an end row is from the render with the end blur everywhere, any other
        row from the render with the own blur, a row whose centre lies exactly
        on a cut is outside the two, and the two renders differ on the end
        rows; and the tie rows"""
        qs = []
        for bl in (eb["blur"], own):
            q = _cpk.deepcopy(p_eb)
            for _L in q["layers"]:
                if _L["id"] == lid:
                    _L.pop("end_blur", None)
                    _L["blur"] = bl
            qs.append(q)
        b = None if composite else lid
        iB, iE, iO = (np.rint(_FP.render_array(build_svg.build(q, basis=b), size) * 255) for q in [p_eb] + qs)
        yc = (np.arange(size) + 0.5) * 1024.0 / size
        tie = (np.abs(yc - eb["north"]) < 1e-9) | (np.abs(yc - eb["south"]) < 1e-9)
        ends = ((yc < eb["north"]) | (yc >= eb["south"])) & ~tie
        mid = ~ends & ~tie
        out = np.maximum(np.minimum(iE, iO) - iB, iB - np.maximum(iE, iO))[tie]
        return (float(np.abs(iB[ends] - iE[ends]).max()), float(np.abs(iB[mid] - iO[mid]).max()),
                float(out.max()) if tie.any() else 0.0, float(np.abs(iE[ends] - iO[ends]).max()),
                np.nonzero(tie)[0])

    if _ebL != ["arc_core"]:
        _ebd.append("layers with an end blur: %s (expected arc_core)" % _ebL)
    else:
        _Leb = [L for L in params["layers"] if L["id"] == "arc_core"][0]
        _eb = _Leb["end_blur"]
        _qOb = _cpk.deepcopy(params)
        for _L in _qOb["layers"]:
            if _L["id"] == "arc_core":
                _L.pop("end_blur")
        _svEb = build_svg.build(params, basis="arc_core")
        _svOb = build_svg.build(_qOb, basis="arc_core")
        _rid = "rows_%d_%d" % (_eb["north"], _eb["south"])
        if _svEb.count('mask="url(#%s)"' % _rid) != 2 or _svEb.count('mask="url(#rows') != 2:
            _ebd.append("with the key, arc_core is not one row-masked group per side")
        if "url(#rows" in _svOb:
            _ebd.append("without the key, arc_core still carries a row mask")
        # the mask alone at 872 px: the tie row must read a middle value, or
        # the 872 px case cannot tell a mix of the copies from one copy
        _mk = [m for m in (__import__("re").search(r'<linearGradient id="%sg".*?</linearGradient>' % _rid, _svEb),
                           __import__("re").search(r'<mask id="%s".*?</mask>' % _rid, _svEb)) if m]
        _t872 = int(np.nonzero(np.abs((np.arange(872) + 0.5) * 1024.0 / 872 - _eb["south"]) < 1e-9)[0][0])
        _m872 = None
        if len(_mk) == 2:
            _m872 = float(np.rint(_FP.render_array(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">'
                '<defs>%s%s</defs><rect width="1024" height="1024" fill="#000000"/>'
                '<rect width="1024" height="1024" fill="#ffffff" mask="url(#%s)"/></svg>'
                % (_mk[0].group(0), _mk[1].group(0), _rid), 872)[_t872, 400, 0] * 255))
        if _m872 is None or not 32 <= _m872 <= 223:
            _ebd.append("at 872 px the row mask reads %s on the row whose centre is the south cut, so the case "
                        "cannot tell a mix of the copies from one copy" % _m872)
        _pLb = _cpk.deepcopy(params)
        _ebLb = {"blur": 1.0, "north": 200, "south": 800}
        for _L in _pLb["layers"]:
            if _L["id"] == "arc_lens_band":
                _L["end_blur"] = _ebLb
        for _tag, _pp, _lid, _e, _own, _size, _comp, _need in (
                ("arc_core alone, 1024 px", params, "arc_core", _eb, _Leb["blur"], 1024, False, 10),
                ("arc_core alone, 2048 px", params, "arc_core", _eb, _Leb["blur"], 2048, False, 10),
                ("arc_core alone, 1000 px", params, "arc_core", _eb, _Leb["blur"], 1000, False, 10),
                ("arc_core alone, 872 px", params, "arc_core", _eb, _Leb["blur"], 872, False, 10),
                ("the composite, 1024 px", params, "arc_core", _eb, _Leb["blur"], 1024, True, 10),
                ("the composite with a probe end blur on arc_lens_band, 1024 px", _pLb, "arc_lens_band",
                 _ebLb, [L for L in params["layers"] if L["id"] == "arc_lens_band"][0]["blur"], 1024, True, 3)):
            _dE, _dO, _dT, _diff, _tr = _eb_split(_pp, _lid, _e, _own, _size, _comp)
            _ebr.append("%s: end rows %g, others %g levels from the single-blur renders (which differ by up to %g "
                        "there)%s" % (_tag, _dE, _dO, _diff, "; the row on the cut (%s) %g outside the two"
                                      % (",".join(str(int(r)) for r in _tr), _dT) if len(_tr) else ""))
            if _dE > 1 or _dO > 1:
                _ebd.append("%s: the end rows are %g and the others %g levels from the layer drawn with one blur"
                            % (_tag, _dE, _dO))
            if _dT > 1:
                _ebd.append("%s: the row whose centre is on a cut is %g levels outside the two single-blur renders"
                            % (_tag, _dT))
            if _size == 872 and not len(_tr):
                _ebd.append("%s: no row's centre lies on a cut" % _tag)
            if _diff < _need:
                _ebd.append("%s: the two blurs differ by only %g levels, so the check cannot tell them apart"
                            % (_tag, _diff))
        _nonarc = [L["id"] for L in params["layers"] if L["kind"] != "arc"][0]
        for _lid, _bad in (("arc_core", {"blur": _eb["blur"], "north": _eb["north"] + 1, "south": _eb["south"]}),
                           ("arc_core", {"blur": _eb["blur"], "north": _eb["south"], "south": _eb["north"]}),
                           ("arc_core", {"blur": _eb["blur"], "north": _eb["north"]}),
                           ("arc_core", {}),
                           ("arc_core", {"blur": _eb["blur"], "north": str(_eb["north"]), "south": _eb["south"]}),
                           (_nonarc, _eb)):
            _qx = _cpk.deepcopy(params)
            [L for L in _qx["layers"] if L["id"] == _lid][0]["end_blur"] = _bad
            try:
                build_svg.build(_qx, basis=_lid)
                _ebd.append("end_blur %s was accepted on %s" % (_bad, _lid))
            except AssertionError:
                pass
    check("an end-blurred arc draws each row with one of its two blurs",
          not _ebd, "; ".join(_ebd) if _ebd else
          "arc_core, blur %g at y < %d and y >= %d, %g between. %s; at 872 px the mask reads %g on the cut's row; "
          "misplaced, crossing, missing or non-numeric rows, an empty key and the key on a non-arc layer are refused"
          % (_eb["blur"], _eb["north"], _eb["south"], _Leb["blur"], "; ".join(_ebr), _m872))

    # ---- a split arc's end blur keeps each half's screen, seam included (D72)
    # `end_blur` on an arc split by `convex_taper` (no shipped layer has both,
    # the builder allows it): each copy must composite its two halves as the
    # layer does without the key, each screened.  Drawn source-over inside the
    # copy, the halves darken the pixels their anti-aliased clips share on the
    # split, even with the end blur equal to the layer's own (Devin's review:
    # 7 levels on some 700 pixels).  The probe is arc_glow2 given arc_core's
    # colour, width and blur on the curve itself, so the split (1.5 px out)
    # runs through the bright stroke; alone, on black.  Checked at 1024, 1000,
    # 872 and 968 px:
    # - with the end blur equal to its own, the probe equals the probe without
    #   the key, to a level, on the seam and everywhere else;
    # - with a sharper end blur, every end row is the probe drawn with that blur
    #   and every other row the probe drawn with its own, to a level (a row on
    #   a cut lies between the two), and the two blurs really differ.
    def _split_probe(eb=None, blur=None):
        q = _cpk.deepcopy(params)
        L = [L for L in q["layers"] if L["id"] == "arc_glow2"][0]
        L.update(color=[216.24, 255.0, 255.0], width=6.832, blur=0.6137416122421083, inset=0.0)
        if blur is not None:
            L["blur"] = blur
        if eb is not None:
            L["end_blur"] = eb
        q["layers"] = [L]
        return q

    _spd, _spr = [], []
    _sp0 = _split_probe()
    if not _sp0["layers"][0].get("convex_taper"):
        _spd.append("arc_glow2 no longer carries a convex_taper, so the probe is not split")
    else:
        _svS = build_svg.build(_sp0)
        _cids = sorted(set(__import__("re").findall(r'clip-path="url\(#(c[cv][LR]_[^)]+)\)"', _svS)))
        _dfS = _svS.split("</defs>")[0] + "</defs>"
        _ebS = {"blur": 0.20421316015498364, "north": 300, "south": 704}
        for _S in (1024, 1000, 872, 968):
            _cv = [np.rint(_FP.render_array(_dfS + '<rect width="1024" height="1024" fill="#000"/><rect width="1024" '
                                            'height="1024" fill="#fff" clip-path="url(#%s)"/></svg>' % _c, _S)[..., 0] * 255)
                   for _c in _cids]
            # the seam: pixels lit by both halves' clips of one curve
            _seam = np.zeros(_cv[0].shape, bool)
            for _a in range(len(_cv)):
                for _b in range(_a + 1, len(_cv)):
                    if _cids[_a][2] == _cids[_b][2]:
                        _seam |= (_cv[_a] > 0) & (_cv[_b] > 0)
            _i0 = np.rint(_FP.render_array(_svS, _S) * 255)
            _iq = np.rint(_FP.render_array(build_svg.build(_split_probe(
                {"blur": _sp0["layers"][0]["blur"], "north": 300, "south": 704})), _S) * 255)
            _dq = np.abs(_iq - _i0).max(axis=2)
            if not _seam.any() or _i0[_seam].max() < 100:
                _spd.append("%d px: the probe's seam is not lit (%d pixels), so the check cannot see it" % (_S, _seam.sum()))
            if _dq.max() > 1:
                _spd.append("%d px: with the end blur equal to its own the split arc differs by %d levels (%d on the "
                            "seam's %d pixels)" % (_S, _dq.max(), _dq[_seam].max() if _seam.any() else 0, _seam.sum()))
            _iB = np.rint(_FP.render_array(build_svg.build(_split_probe(_ebS)), _S) * 255)
            _iE = np.rint(_FP.render_array(build_svg.build(_split_probe(blur=_ebS["blur"])), _S) * 255)
            _yc = (np.arange(_S) + 0.5) * 1024.0 / _S
            _tie = (np.abs(_yc - 300) < 1e-9) | (np.abs(_yc - 704) < 1e-9)
            _end = ((_yc < 300) | (_yc >= 704)) & ~_tie
            _midr = ~_end & ~_tie
            _dE, _dO = np.abs(_iB[_end] - _iE[_end]).max(), np.abs(_iB[_midr] - _i0[_midr]).max()
            _dT = float(np.maximum(np.minimum(_iE, _i0) - _iB, _iB - np.maximum(_iE, _i0))[_tie].max()) if _tie.any() else 0.0
            _dd = np.abs(_iE[_end] - _i0[_end]).max()
            if _dE > 1 or _dO > 1 or _dT > 1:
                _spd.append("%d px: with a sharper end blur the end rows are %d, the others %d and a row on a cut %g "
                            "levels from the single-blur renders" % (_S, _dE, _dO, _dT))
            if _dd < 10:
                _spd.append("%d px: the two blurs differ by only %d levels" % (_S, _dd))
            _spr.append("%d px: %d, seam %d px lit to %d; sharper: %d / %d (blurs differ by %d)"
                        % (_S, _dq.max(), _seam.sum(), _i0[_seam].max(), _dE, _dO, _dd))
    check("a split arc's end blur keeps each half's screen, seam included",
          not _spd, "; ".join(_spd) if _spd else
          "arc_glow2 given arc_core's stroke, split by its convex_taper; end blur equal to its own vs none, max "
          "levels: " + "; ".join(_spr))

    # ---- a red-shifted core changes only its red, where its table says (D72)
    # `red_shift` moves an arc layer's red along each curve (build_svg.
    # red_shade): its stops carry R + dR(y), with G, B and the opacity as they
    # were.  Drawn alone on black, a layer is its paint times its coverage, so
    # its G reads the coverage times the colour's G, and adding the key moves R
    # by G x dR(y) / G_colour.  Read on three probes: arc_core's own table (at
    # 1024 and 1000 px), an off-grid table on arc_core whose rows fall between
    # the taper's (so R is interpolated between rows and stops are added), and
    # arc_glow1, whose screen opacity is below 1 (the shift is premultiplied):
    # - G and B are the layer's own, and 3 rows from any shifted row nothing
    #   moves (to a level where stops are added: an added stop turns a rounding
    #   here and there within its taper segment); R moves by G x dR / G_colour
    #   to 2.5 levels at a pixel (each render rounds in every 8-bit buffer it
    #   passes through) and 0.3 on average; on the flat rows R moves by at
    #   least half of what the relation predicts at the brightest pixel;
    # - in the full composite only R changes, only on the table's side within 3
    #   rows of a shifted row, and only where arc_core draws;
    # - a table of zeros on the taper's own rows builds the same SVG, one whose
    #   rows fall between the taper's renders to a level (an added stop turns a
    #   rounding here and there);
    # - the white basis ignores the key;
    # - a malformed table, or the key where it cannot apply, is refused;
    # - the colour fit and the optimiser hold the layer's colour
    #   (fit_photometry.colour_held; optimize.main's own Objective is built
    #   with it held), and a real fit leaves its row alone.
    _rsd, _rsr = [], []
    _rsL = [L for L in params["layers"] if L.get("red_shift")]
    if [L["id"] for L in _rsL] != ["arc_core"]:
        _rsd.append("layers with a red shift: %s (expected arc_core)" % [L["id"] for L in _rsL])
    else:
        _rsA = _rsL[0]
        _rs0 = _cpk.deepcopy(params)
        for _Lr in _rs0["layers"]:
            _Lr.pop("red_shift", None)

        def _rs_with(rs, lid="arc_core", p=None):
            q = _cpk.deepcopy(params if p is None else p)
            [L for L in q["layers"] if L["id"] == lid][0]["red_shift"] = rs
            return q

        def _rs_alone(p, lid):
            q = _cpk.deepcopy(p)
            q["layers"] = [L for L in q["layers"] if L["id"] == lid]
            return q

        def _rs_map(L, yc, xc, pad=0.0):
            """L's table shift per pixel (with `pad`, the largest |shift| within
            that many rows)"""
            off = float(params["tapers"][L["taper"]].get("y_offset", 0.5))
            out = np.zeros((len(yc), len(xc)))
            for sd, xm in (("left", xc < 512), ("right", xc >= 512)):
                rows = L["red_shift"].get(sd)
                if rows:
                    ys, ds = [r[0] + off for r in rows], [r[1] for r in rows]
                    v = np.max([np.abs(np.interp(yc + e, ys, ds)) for e in np.linspace(-pad, pad, 13)], 0) if pad \
                        else np.interp(yc, ys, ds)
                    out[:, xm] = v[:, None]
            return out

        def _rs_probe(tag, lid, rs, S, gb_tol):
            """the layer drawn alone with `rs` against without; problems, summary"""
            q1 = _rs_alone(_rs_with(rs, lid, _rs0), lid)
            q0 = _rs_alone(_rs0, lid)
            L = q1["layers"][0]
            kG = float(L["color"][1])
            yc = (np.arange(S) + 0.5) * 1024.0 / S
            a1 = np.rint(_FP.render_array(build_svg.build(q1), S) * 255)
            a0 = np.rint(_FP.render_array(build_svg.build(q0), S) * 255)
            dm = _rs_map(L, yc, yc)
            far = _rs_map(L, yc, yc, pad=3.0) == 0
            e = (a1[..., 0] - a0[..., 0]) - a1[..., 1] * dm / kG
            eR, eM = float(np.abs(e).max()), float(np.abs(e[a1[..., 1] > 0].mean()))
            efar = float(np.abs(a1 - a0)[far].max())
            flat = (a1[..., 1] > 0) & (np.abs(dm) >= 0.999 * np.abs(dm).max())
            want = float((a1[..., 1] * np.abs(dm) / kG)[flat].max()) if flat.any() else 0.0
            mv = float(np.abs(a1[..., 0] - a0[..., 0])[flat].max()) if flat.any() else 0.0
            gb = float(np.abs(a1[..., 1:] - a0[..., 1:]).max())
            bad = []
            if gb > gb_tol or eR > 2.5 or eM > 0.3 or efar > gb_tol or want < 5 or mv < 0.5 * want:
                bad.append("%s, %d px: G/B move by %g; R moves %.2f levels from G x dR / G_colour at worst, %.2f on "
                           "average, and %g 3 rows from any shifted row; on its flat rows R moves by %g where %.1f is "
                           "predicted" % (tag, S, gb, eR, eM, efar, mv, want))
            return bad, a1, "%s %d px: R moves by G x dR / G to %.2f (%.2f on average), %g on the flat rows (%.1f " \
                "predicted), G/B %g" % (tag, S, eR, eM, mv, want, gb)
        for _tag, _lid, _rsv, _S, _gbt in (("arc_core's table", "arc_core", _rsA["red_shift"], 1024, 0),
                                           ("arc_core's table", "arc_core", _rsA["red_shift"], 1000, 0),
                                           ("an off-grid table", "arc_core", {"right": [[150, 0], [250, 18], [330, 0]]},
                                            1024, 1),
                                           ("arc_glow1 (opacity below 1)", "arc_glow1",
                                            {"left": [[300, 0], [400, 60], [600, 60], [700, 0]]}, 1024, 1)):
            _b, _a1, _sm = _rs_probe(_tag, _lid, _rsv, _S, _gbt)
            _rsd += _b
            _rsr.append(_sm)
            if _tag != "arc_core's table":
                continue
            _yc = (np.arange(_S) + 0.5) * 1024.0 / _S
            _f1 = np.rint(_FP.render_array(build_svg.build(params), _S) * 255)
            _f0 = np.rint(_FP.render_array(build_svg.build(_rs0), _S) * 255)
            _chg = np.abs(_f1 - _f0).max(axis=2) > 0
            _gbf = float(np.abs(_f1[..., 1:] - _f0[..., 1:]).max())
            _stray = int((_chg & ~((_rs_map(_rsA, _yc, _yc, pad=3.0) > 0) & (_a1[..., 1] > 0))).sum())
            if _gbf > 0 or _stray or not _chg.any():
                _rsd.append("%d px, composite: G/B move by %g; %d changed pixels outside the table's rows or arc_core's "
                            "light; %d changed in all" % (_S, _gbf, _stray, _chg.sum()))
            _rsr.append("composite %d px: %d px changed, G/B %g" % (_S, _chg.sum(), _gbf))
        # zero tables: on the taper's rows, and between them
        _zs = {"left": [[300, 0], [420, 0]], "right": [[300, 0], [420, 0]]}
        if build_svg.build(_rs_with(_zs)) != build_svg.build(_rs0):
            _rsd.append("a table of zeros on the taper's rows builds another SVG")
        _zb = np.abs(np.rint(_FP.render_array(build_svg.build(_rs_with({"right": [[150, 0], [330, 0]]})), 1024) * 255)
                     - np.rint(_FP.render_array(build_svg.build(_rs0), 1024) * 255)).max()
        if _zb > 1:
            _rsd.append("a table of zeros between the taper's rows moves the render by %g levels" % _zb)
        if build_svg.build(params, basis="arc_core") != build_svg.build(_rs0, basis="arc_core"):
            _rsd.append("the white basis takes the red shift")
        # refused: malformed tables, and the key where it cannot apply
        _bad = [("a list", []), ("empty", {}), ("a key other than a side", {"middle": [[100, 0], [200, 0]]}),
                ("one row", {"right": [[140, 0]]}), ("a string", {"right": [[140, 0], ["160", 5], [200, 0]]}),
                ("a bool", {"right": [[140, 0], [160, True], [200, 0]]}),
                ("a NaN", {"right": [[140, 0], [160, float("nan")], [200, 0]]}),
                ("a row of three", {"right": [[140, 0], [160, 5, 1], [200, 0]]}),
                ("rows out of order", {"right": [[160, 0], [140, 5], [200, 0]]}),
                ("a row at y 0", {"right": [[0, 0], [160, 5], [200, 0]]}),
                ("a row off the canvas", {"right": [[140, 0], [160, 5], [1030, 0]]}),
                ("a non-zero end row", {"right": [[140, 5], [160, 5], [200, 0]]}),
                ("a red past G and B", {"right": [[140, 0], [160, 40], [200, 0]]}),
                ("a red below 0", {"right": [[140, 0], [160, -220], [200, 0]]})]
        _okrs = {"right": [[140, 0], [160, 5], [200, 0]]}
        for _lid, _why, _mut in (("field_base", "a layer that is not an arc", None),
                                 ("arc_glow2", "a split arc (convex_taper)", None),
                                 ("arc_glow1", "an untapered arc", lambda L: L.pop("taper")),
                                 ("arc_glow1", "a normal-blended arc", lambda L: L.update(blend="normal")),
                                 ("arc_core", "a side the layer does not draw", lambda L: L.update(side="left"))):
            _q = _cpk.deepcopy(_rs0)
            _Lq = [L for L in _q["layers"] if L["id"] == _lid][0]
            _Lq["red_shift"] = _okrs
            if _mut:
                _mut(_Lq)
            _bad.append((_why, _q))
        _unrefused = []
        for _why, _rsv in _bad:
            _q = _rsv if isinstance(_rsv, dict) and "layers" in _rsv else _rs_with(_rsv)
            try:
                build_svg.build(_q)
                _unrefused.append(_why)
            except AssertionError as _e:
                if "red_shift" not in str(_e):
                    _unrefused.append("%s (refused for another reason: %s)" % (_why, _e))
            except Exception as _e:
                _unrefused.append("%s (raised %s)" % (_why, type(_e).__name__))
        if _unrefused:
            _rsd.append("not refused: " + ", ".join(_unrefused))
        # held: the colour fit, the optimiser (its main() builds its Objective
        # with the held set: stopped there), and a real fit's row
        _rci = [i for i, L in enumerate(params["layers"]) if L["id"] == "arc_core"][0]
        if not (_FP.colour_held(params) == ["arc_core"] and _rci not in _FP.held_free(params)
                and _rci not in _FP.held_free(params, rays=False)):
            _rsd.append("the colour fit may move arc_core's colour")
        if not np.array_equal(_WC1[_rci], _WC0[_rci]):
            _rsd.append("a real fit moved arc_core's colour row")

        class _RsStop(Exception):
            pass
        _rs_seen = {}

        class _RsObjective:
            def __init__(self, *a, **k):
                _rs_seen["held"] = set(k.get("held", ()))
                raise _RsStop()
        _rs_argv, _rs_obj = sys.argv, O.Objective
        for _mode in ([], ["--include-rays"]):
            _rs_seen.clear()
            sys.argv = ["optimize.py", "--params", os.path.join(ROOT, "src", "params.json")] + _mode
            O.Objective = _RsObjective
            try:
                O.main()
            except _RsStop:
                pass
            finally:
                sys.argv, O.Objective = _rs_argv, _rs_obj
            if "arc_core" not in _rs_seen.get("held", ()):
                _rsd.append("optimize.py %s builds its Objective without arc_core held (%s)"
                            % (" ".join(_mode) or "(default)", sorted(_rs_seen.get("held", ())) or "nothing"))
    check("a red-shifted core changes only its red, where its table says",
          not _rsd, "; ".join(_rsd) if _rsd else
          "arc_core, %s; " % _rsA["red_shift"] + "; ".join(_rsr) + "; a zero table on the taper's rows builds the "
          "same SVG, between them renders within %g; the basis ignores it; %d malformed tables and misplaced keys "
          "refused; its colour held by the colour fit (rays held or not), optimize.py's Objective (rays held or not) "
          "and a real fit" % (_zb, len(_bad)))

    # ---- the objective scores the red_shift the SVG draws (D72, stage 14) --- #
    # The review case: `red_shift` changed the SVG but not the photometric
    # model, whose basis is white and whose composite takes one colour per
    # layer.  Objective.evaluate scored the shipped table, no table and any
    # other table bit for bit alike; the analytic composite missed 9-17 levels
    # of R on the 2,516 pixels the table changes; and a colour fit given the
    # SVG's own render moved unrelated layers to supply that red
    # (arc_lens_band's R by 2.7).  The model now adds each red-shifted layer's
    # shift field to its term (fit_photometry.shift_terms).  With everything
    # else identical, six states: the shipped table ("on"), none ("off"), a
    # table of zeros on the taper's rows, a multi-row table that also goes
    # below 0, a table on both curves, and one inside the right curve's north
    # curve-axis zone (y 20-150).  Then:
    # - the render changes where a table does, and so does the score of a
    #   fresh Objective with nothing freed; a zero table scores as none;
    # - one Objective reused through all the states scores each bitwise as a
    #   fresh one (the bases are content-addressed and shared, as in D69's
    #   check; the shift fields are the state under test, and each fresh
    #   Objective renders its own);
    # - on the pixels a table changes, the analytic composite changes as the
    #   render does: to 3 levels at a pixel, 0.8 on average and 0.5 in the mean
    #   (the render's change is the difference of two 8-bit images, so +-0.5 is
    #   its floor; the model before stage 14 missed it by 10 on average), and it
    #   stays within 1.5 levels of the render on average; and over the rest of
    #   arc_core's light, where the render does not change, the model does not
    #   change either: 0.05 on average, 2.5 at a pixel (the render's own 8-bit
    #   layers drop up to about 2 levels of the shift at an edge pixel, which
    #   the finer field keeps).  A field drawn where a table draws nothing, on
    #   a side without rows say, adds its full red there and fails (the
    #   review's case); and drawn alone with the largest red a table may add
    #   (+38) over both curves' north tips, inside the curve-axis zone, the
    #   layer's change follows the render's to 1.7 levels at the 99th percentile
    #   and 0.5 on average (a field drawn without the zone's mask reads 2.2 and
    #   0.65 there);
    # - a colour fit to the SVG's own render over the right curve (stride 2,
    #   the same free set, arc_core held) lands on the same colours with the
    #   table as without it, to 0.25 levels: no layer makes up its red;
    # - the model's other users carry the term: measure_flare's stack follows a
    #   table through refresh (its image is the composite with the term), and
    #   prune_layers scores the composite with the term, not without it.
    _odiag, _orep = [], []
    _rsP = [L for L in params["layers"] if L["id"] == "arc_core"][0].get("red_shift")
    if not _rsP:
        _odiag.append("arc_core carries no red_shift, so there is nothing to test")
    else:
        def _rsState(rs):
            q = _cpk.deepcopy(params)
            Lq = [L for L in q["layers"] if L["id"] == "arc_core"][0]
            if rs is None:
                Lq.pop("red_shift", None)
            else:
                Lq["red_shift"] = rs
            return q
        _rsS = {"on": params, "off": _rsState(None),
                "zero": _rsState({"left": [[300, 0], [420, 0]], "right": [[300, 0], [420, 0]]}),
                "multi": _rsState({"right": [[140, 0], [160, 18], [300, 18], [320, 0], [400, 0], [440, -30],
                                             [480, -30], [520, 0], [840, 0], [860, 18], [900, 18], [920, 0]]}),
                "both": _rsState({"left": [[300, 0], [340, 12], [680, 12], [720, 0]],
                                  "right": [[140, 0], [160, 18], [300, 18], [320, 0]]}),
                "north": _rsState({"right": [[20, 0], [60, 15], [120, 15], [150, 0]]})}
        _oheld = O.held_layers(params)

        def _ofresh():
            f = O.Objective(os.path.join(ROOT, "reference.png"), stride=4, fit_iters=1, held=_oheld)
            f.cache = _objK.cache
            return f
        _ore = _ofresh()
        _osc = {}
        for _nm in ("on", "off", "multi", "both", "north", "zero", "on"):
            _r1 = _ore.evaluate(_rsS[_nm], free=[])[0]
            _f1 = _ofresh().evaluate(_rsS[_nm], free=[])[0]
            _osc[_nm] = _f1
            if _r1 != _f1:
                _odiag.append("%s scored %.10g reused against %.10g fresh" % (_nm, _r1, _f1))
        if build_svg.build(_rsS["on"]) == build_svg.build(_rsS["off"]):
            _odiag.append("the shipped table does not change the SVG")
        if _osc["on"] == _osc["off"]:
            _odiag.append("toggling the shipped table changes the SVG but not the score (%.10g)" % _osc["on"])
        if len({_osc[k] for k in ("on", "off", "multi", "both", "north")}) < 5:
            _odiag.append("two different tables score alike: %s" % {k: _osc[k] for k in ("on", "off", "multi", "both", "north")})
        if _osc["zero"] != _osc["off"]:
            _odiag.append("a zero table scores %.10g, no table %.10g" % (_osc["zero"], _osc["off"]))
        try:
            _oA = np.stack([_ore.basis(params, L["id"]) for L in params["layers"]])
            _onf, _oK = FP.normal_flags(params), FP.colors(FP.params_wc(params))
            _oreal, _oan, _oex = {}, {}, {}
            _ofoot = _oA[[L["id"] for L in params["layers"]].index("arc_core")] > 0
            for _nm in ("off", "on", "multi", "both", "north"):
                _oreal[_nm] = FP.render_array(build_svg.build(_rsS[_nm]), 1024) * 255
                _oex[_nm] = _ore.shift_extra(_rsS[_nm])
                _oan[_nm] = FP.composite(_oA, _oK, _onf, extra=_oex[_nm]) * 255
            for _nm in ("on", "multi", "both", "north"):
                _om = np.abs(_oreal[_nm] - _oreal["off"]).max(axis=2) > 0
                _osv = np.abs(_oan[_nm] - _oan["off"])[..., 0][_ofoot & ~_om]
                _ostill, _ostm = float(_osv.max()), float(_osv.mean())
                if _ostill > 2.5 or _ostm > 0.05:
                    _odiag.append("%s: where the render does not change, over arc_core's light, the model moves by "
                                  "up to %.2f levels (%.3f on average)" % (_nm, _ostill, _ostm))
                _dR = (_oreal[_nm] - _oreal["off"])[..., 0][_om]
                _dA = (_oan[_nm] - _oan["off"])[..., 0][_om]
                _e = np.abs(_dA - _dR)
                _gap = float(np.abs(_oan[_nm] - _oreal[_nm])[..., 0][_om].mean())
                if (_om.sum() < 150 or _e.max() > 3.0 or _e.mean() > 0.8 or abs(_dA.mean() - _dR.mean()) > 0.5
                        or _gap > 1.5):
                    _odiag.append("%s: on the %d px the table changes, the render's R moves by %+.2f on average "
                                  "and the composite's by %+.2f (%.2f apart at worst, %.2f on average); the "
                                  "composite is %.2f from the render there"
                                  % (_nm, _om.sum(), _dR.mean(), _dA.mean(), _e.max(), _e.mean(), _gap))
                _orep.append("%s %d px: render R %+.2f, composite %+.2f (worst %.2f apart), composite-render %.2f, "
                             "elsewhere %.2f at worst, %.4f on average" % (_nm, _om.sum(), _dR.mean(), _dA.mean(),
                                                                          _e.max(), _gap, _ostill, _ostm))
            # arc_core alone, the largest red a table may add, inside both
            # curves' north curve-axis zones
            _oci = [L["id"] for L in params["layers"]].index("arc_core")
            _otip = {s_: [[20, 0], [40, 38], [140, 38], [160, 0]] for s_ in ("left", "right")}

            def _oalone(q):
                r = _cpk.deepcopy(q)
                r["layers"] = [L for L in r["layers"] if L["id"] == "arc_core"]
                return r
            _qt1, _qt0 = _oalone(_rsState(_otip)), _oalone(_rsState(None))
            _ra1 = FP.render_array(build_svg.build(_qt1), 1024) * 255
            _ra0 = FP.render_array(build_svg.build(_qt0), 1024) * 255
            _Kc = FP.colors(FP.params_wc(_qt0))
            _ma1 = FP.composite(_oA[_oci][None], _Kc, [False], extra=FP.shift_terms(_qt1)) * 255
            _ma0 = FP.composite(_oA[_oci][None], _Kc, [False]) * 255
            _otm = np.abs(_ra1 - _ra0).max(axis=2) > 0
            _ote = np.abs((_ma1 - _ma0)[..., 0] - (_ra1 - _ra0)[..., 0])[_otm]
            _ot99 = float(np.percentile(_ote, 99)) if _otm.any() else float("nan")
            if _otm.sum() < 500 or not _ot99 <= 1.7 or _ote.mean() > 0.5:
                _odiag.append("arc_core alone with +38 over the north tips' curve-axis zones: the layer's change "
                              "follows the render's to %.2f at the 99th percentile, %.2f on average (%d px)"
                              % (_ot99, _ote.mean(), _otm.sum()))
            _orep.append("arc_core alone, +38 in the tips' curve-axis zones, %d px: p99 %.2f, mean %.2f"
                         % (_otm.sum(), _ot99, _ote.mean()))
            _oy0, _oy1, _ox0, _ox1 = 96, 960, 528, 800
            _ofree = FP.held_free(params)
            _ofit = {}
            for _nm in ("off", "on"):
                _ot = np.minimum(_oreal[_nm] / 255.0, 254.4 / 255.0)[_oy0:_oy1:2, _ox0:_ox1:2].astype(np.float32)
                _oe = FP.sub_terms({i: e[_oy0:_oy1, _ox0:_ox1] for i, e in _oex[_nm].items()}, 2)
                _ow = FP.fit(_oA[:, _oy0:_oy1:2, _ox0:_ox1:2], _ot, FP.params_wc(_rsS[_nm]),
                             np.ones(_ot.shape[:2], np.float32), iters=6, verbose=False, free=_ofree,
                             normal=_onf, teal_ok=FP.teal_eligible(params), extra=_oe)
                _ofit[_nm] = FP.colors(_ow) * 255.0
            _odK = np.abs(_ofit["on"] - _ofit["off"])[_ofree]
            _oworst = _ofree[int(np.argmax(_odK.max(axis=1)))]
            if _odK.max() > 0.25:
                _odiag.append("a colour fit to the render moves %s by %.2f levels to make up the table's red"
                              % (params["layers"][_oworst]["id"], _odK.max()))
            _orep.append("fits with and without the table agree to %.3f levels (%s)"
                         % (_odK.max(), params["layers"][_oworst]["id"]))
            # measure_flare's stack: the term follows a table through refresh,
            # and its image is the composite with it
            _ostk = []
            for _nm in ("off", "multi", "on"):
                _stack.refresh(_rsS[_nm])
                _owant = FP.shift_terms(_rsS[_nm], box=_stack.box)
                _okw = np.ones(len(_stack.idx))
                _oimg = _stack.image(_okw)
                _WCs = _stack.WC.copy()
                _oexp = FP.composite(_stack.A, FP.colors(_WCs).astype(np.float32), _stack.normal, extra=_owant) * 255.0
                if (sorted(_stack.E) != sorted(_owant)
                        or any(not np.array_equal(_stack.E[i], _owant[i]) for i in _owant)
                        or not np.array_equal(_oimg, _oexp)):
                    _ostk.append(_nm)
            if _ostk:
                _odiag.append("measure_flare's stack does not composite the table after refresh to %s" % _ostk)
            # prune_layers scores the composite with the term
            import prune_layers as _PLo
            _opc = {L["id"]: _oA[i] for i, L in enumerate(params["layers"])}
            _oref = np.minimum(np.asarray(_Image.open(os.path.join(ROOT, "reference.png")).convert("RGB"))
                               .astype(np.float32) / 255.0, 254.4 / 255.0)
            _opm = _PLo.evaluate(params, _oref, stride=8, iters=0, cache=_opc)[0]
            _ot8 = _oref[::8, ::8]
            _opw = float(np.abs(FP.composite(_oA[:, ::8, ::8], _oK, _onf,
                                             extra=FP.sub_terms(_oex["on"], 8)) - _ot8).mean() * 255)
            _opo = float(np.abs(FP.composite(_oA[:, ::8, ::8], _oK, _onf) - _ot8).mean() * 255)
            if _opm != _opw or _opw == _opo:
                _odiag.append("prune_layers scores %.6f; the composite with the term %.6f, without %.6f"
                              % (_opm, _opw, _opo))
            _orep.append("measure_flare's stack follows off -> multi -> on; prune_layers scores the composite "
                         "with the term (%.6f; %.6f without)" % (_opm, _opo))
        except Exception as _oe_:
            _odiag.append("the model cannot composite the shift: %s: %s" % (type(_oe_).__name__, _oe_))
    check("the objective scores the red_shift the SVG draws",
          not _odiag, "; ".join(_odiag) if _odiag else
          "fresh scores: on %.10g, off %.10g, multi %.10g, both %.10g, north %.10g, zero %.10g (= off); one "
          "reused Objective scores all seven states bitwise as fresh ones; %s"
          % (_osc["on"], _osc["off"], _osc["multi"], _osc["both"], _osc["north"], _osc["zero"],
             "; ".join(_orep)))

    # ---- the lens-side band stays beside the core's ends (D71) ------------ #
    # arc_lens_band is the reference's cyan band just outside the core's lens
    # edge, over the curves' outer thirds.  What was measured is where it may
    # draw, and in what colour:
    # - on the lens (concave) side of the curve: almost none of its light
    #   beyond the core's flare edge (4 px on the flare side);
    # - beside the core: all of it within 16 px of the curve;
    # - over the outer thirds only: nothing on the rows of the curves' middle,
    #   where the model's own lens-side glows already match the reference;
    # - cyan, as the reference's band reads (G/B 0.89-0.99), with almost no
    #   white (R at most a quarter of G).  The photometric fit frees every
    #   layer's colour but the rays', so a refit that gave it white or blue
    #   fails here.
    # The band's bounds (inset 4.75-5.75, width 1-5.5, blur 0.5-3.25) keep the
    # first two at every corner of the search box.  The taper search moves
    # every table's y_offset within +-14 px; beyond about +-10 the band's table
    # reaches the middle rows, and this check fails, as it should.
    _lbL = [L for L in params["layers"] if L["id"] == "arc_lens_band"]
    _lbd = []
    if len(_lbL) != 1:
        _lbd.append("there is no arc_lens_band layer")
    else:
        _iLb = _FP.render_array(build_svg.build(params, basis="arc_lens_band"), 1024)[..., 0].astype(np.float64)
        _dLb = regions.curve_frame((1024, 1024))[0]
        _tLb = _iLb.sum()
        _fl = float(_iLb[_dLb > 4].sum() / max(_tLb, 1e-9))
        _nr = float(_iLb[np.abs(_dLb) < 16].sum() / max(_tLb, 1e-9))
        _mid = float(_iLb[380:640].max() * 255)
        if _tLb <= 0:
            _lbd.append("the band draws nothing")
        if _fl > 0.01:
            _lbd.append("%.1f%% of its light is beyond the core's flare edge" % (100 * _fl))
        if _nr < 0.999:
            _lbd.append("only %.2f%% of its light is within 16 px of the curve" % (100 * _nr))
        if _mid > 0:
            _lbd.append("it draws %g levels on the rows of the curves' middle (y 380-640)" % _mid)
        _cLb = np.asarray(_lbL[0]["color"], float)
        _gb = _cLb[1] / max(_cLb[2], 1e-9)
        if not (_cLb[1] > 0 and 0.89 <= _gb <= 0.99 and _cLb[0] <= 0.25 * _cLb[1]):
            _lbd.append("its colour %s is not the band's (G/B 0.89-0.99, R at most a quarter of G)"
                        % _cLb.tolist())
    check("the lens-side band stays beside the core's ends",
          not _lbd, "; ".join(_lbd) if _lbd else
          "arc_lens_band: %.2f%% of its light beyond the core's flare edge, %.3f%% within 16 px of the curve, "
          "none on rows 380-640; colour G/B %.3f, R/G %.3f" % (100 * _fl, 100 * _nr, _gb, _cLb[0] / _cLb[1]))

    # ---- teal is a PERMISSION, not the current amount (D65) --------------- #
    # The review case: fit() locked the fourth primary on every layer whose
    # teal amount was 0, so an ELIGIBLE ray that had reached 0 could never use
    # it again and `--fit-rays` could not restore it.  On the real stack: the
    # upper-right narrow ray is eligible; zero its teal (keeping its best cone
    # colour) and fit it alone against the shipped composite, whose colour
    # needs teal -- it must come back.  The lower-right narrow ray is not
    # eligible; give the TARGET a teal version of it -- it must stay in the cone.
    _nfT = _FP.normal_flags(params)
    _AT = _stack.A[:, ::2, ::2]
    _okT = _FP.teal_eligible(params)
    _WCs = _FP.params_wc(params).astype(np.float64)
    _Kt = _FP.colors(_WCs).astype(np.float32)
    _tgtT = _FP.composite(_AT, _Kt, _nfT)
    _iu = [L["id"] for L in params["layers"]].index("flare_ray_ur")
    _ic = [L["id"] for L in params["layers"]].index("flare_ray_c")
    _teal_diag = []
    _w0 = _WCs.copy()
    _w0[_iu] = _FP.wc_from_color(np.asarray(params["layers"][_iu]["color"]), teal=False)
    # D65 read the slow approach here (12 / 40 / 120 iterations reached 0.020 /
    # 0.049 / 0.088 of 0.109) as cyan and teal being nearly collinear.  It was
    # the stall 5b' describes -- a bound amount pulling every step outside the
    # box -- and with the projected solve 40 iterations reach the target (D66).
    _wfit = _FP.fit(_AT, _tgtT, _w0, np.ones(_tgtT.shape[:2], np.float32), iters=40, verbose=False,
                    free=[_iu], normal=_nfT, teal_ok=_okT)
    _want_t = float(_WCs[_iu, _FP.CONE])
    _got_t = float(_wfit[_iu, _FP.CONE])
    _cf = np.asarray(_FP.color_from_wc(_wfit[_iu]), float)
    _bg = float(_cf[2] / max(_cf[1], 1e-9))
    if not _okT[_iu] or _w0[_iu, _FP.CONE] != 0.0 or _got_t < 0.9 * _want_t or _bg > 0.8:
        _teal_diag.append("flare_ray_ur (eligible) from teal 0 reached %.4f of the target's %.4f, "
                          "B/G %.2f" % (_got_t, _want_t, _bg))
    _wlock = _FP.fit(_AT, _tgtT, _w0, np.ones(_tgtT.shape[:2], np.float32), iters=40, verbose=False,
                     free=[_iu], normal=_nfT)
    if float(_wlock[_iu, _FP.CONE]) != 0.0:
        _teal_diag.append("with no eligibility given, fit() still moved a teal amount")
    _Kc = _Kt.copy()
    _Kc[_ic] = np.clip(np.asarray(_FP.color_from_wc([0.0, 0.0, 0.0, 0.15]), np.float32), 0, 1)
    _tgtC = _FP.composite(_AT, _Kc, _nfT)
    _wc = _FP.fit(_AT, _tgtC, _WCs, np.ones(_tgtC.shape[:2], np.float32), iters=40, verbose=False,
                  free=[_ic], normal=_nfT, teal_ok=_okT)
    if _okT[_ic] or float(_wc[_ic, _FP.CONE]) != 0.0:
        _teal_diag.append("flare_ray_c (not eligible) took teal %.4f" % float(_wc[_ic, _FP.CONE]))
    # ... and from NO LIGHT AT ALL (D66 review): fit() treated a channel at 0
    # as clipped, so every derivative of a dark layer was zero and it could
    # never be fitted back.  flare_ray_ur carries all its light as teal, so at
    # teal 0 it is dark; against a target that has it, it must come back.
    _wd = _WCs.copy()
    _wd[_iu] = 0.0
    _wdf = _FP.fit(_AT, _tgtT, _wd, np.ones(_tgtT.shape[:2], np.float32), iters=20, verbose=False,
                   free=[_iu], normal=_nfT, teal_ok=_okT)
    _dk_t = float(_wdf[_iu, _FP.CONE])
    _dk_c = np.asarray(_FP.color_from_wc(_wdf[_iu]), float) * 255.0
    _dk_w = np.asarray(_FP.color_from_wc(_WCs[_iu]), float) * 255.0
    if _dk_t < 0.9 * _want_t or np.abs(_dk_c - _dk_w).max() > 1.0:
        _teal_diag.append("flare_ray_ur from NO light reached teal %.4f, colour %s against %s"
                          % (_dk_t, np.round(_dk_c, 1), np.round(_dk_w, 1)))
    check("an eligible layer recovers teal from zero; an ineligible one never gains it",
          not _teal_diag, "; ".join(_teal_diag) if _teal_diag else
          "flare_ray_ur from teal 0 -> %.4f (target %.4f), B/G %.2f off the cone, and from no light "
          "at all -> teal %.4f, colour within %.1f cv of the target's; flare_ray_c against a teal "
          "target stays at 0; without eligibility no teal amount moves"
          % (_got_t, _want_t, _bg, _dk_t, float(np.abs(_dk_c - _dk_w).max())))

    # ---- the documented photometric fit runs on every valid layer schema (D66) #
    # fit_photometry.py's report read every component as L[c]; a cone layer has
    # no `teal` key -- absence means NOT ELIGIBLE -- so the documented command
    # (tools/optimize_all.sh: fit_photometry.py --iters 30 --stride 2) raised
    # KeyError after fitting and before saving.  Run the real CLI, both modes,
    # on a file holding every schema: cone layers without a teal key, the six
    # teal-eligible rays with one of them holding no light at all (all amounts
    # and its colour 0: zero-initialised, still eligible), a layer carrying
    # only a colour (no basis keys at all), and the normal-blended frame.
    _fp_diag = []
    _fp_src = json.loads(json.dumps(params))
    for L in _fp_src["layers"]:
        if L["id"] == "flare_ray_ur":            # eligible, zero-initialised: NO light at all
            for _c in ("white", "cyan", "blue", "teal"):
                L[_c] = 0.0
            L["color"] = [0.0, 0.0, 0.0]
        if L["id"] == "field_mid":
            for _c in ("white", "cyan", "blue"):
                L.pop(_c, None)                  # colour only
    _cone0 = {L["id"] for L in _fp_src["layers"] if "teal" not in L}
    _teal0 = {L["id"] for L in _fp_src["layers"] if "teal" in L}
    _held = set(MFL.CALIBRATED_LAYERS)
    with _tf.TemporaryDirectory() as _td6:
        for _mode in ([], ["--fit-rays"]):
            _pf = os.path.join(_td6, "fp.json")
            json.dump(_fp_src, open(_pf, "w"), indent=1)
            _r6 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "fit_photometry.py"), "--params",
                           _pf, "--iters", "1", "--stride", "8"] + _mode, capture_output=True, text=True)
            _tag = "fit_photometry %s" % (" ".join(_mode) or "(documented mode)")
            if _r6.returncode != 0 or "Traceback" in _r6.stderr:
                _fp_diag.append("%s exited %d: %s" % (_tag, _r6.returncode,
                                                      _r6.stderr.strip().splitlines()[-1:]))
                continue
            _got = {L["id"]: L for L in json.load(open(_pf))["layers"]}
            _was = {L["id"]: L for L in _fp_src["layers"]}
            _moved = [lid for lid in _got if lid not in _held and _got[lid].get("color") != _was[lid].get("color")]
            if not _moved:
                _fp_diag.append("%s saved no fitted colour" % _tag)
            if not _mode and any(_got[lid].get("color") != _was[lid].get("color") for lid in _held):
                _fp_diag.append("%s moved a calibrated ray" % _tag)
            # a red-shifted layer's colour is held in both modes (D72)
            _chl = _FP.colour_held(_fp_src)
            if not _chl or any(_got[lid].get(c) != _was[lid].get(c) for lid in _chl
                               for c in ("color", "white", "cyan", "blue")):
                _fp_diag.append("%s moved a red-shifted layer's colour (%s)" % (_tag, _chl or "none present"))
            if any("teal" in _got[lid] for lid in _cone0):
                _fp_diag.append("%s gave a cone layer a teal key" % _tag)
            if any("teal" not in _got[lid] for lid in _teal0):
                _fp_diag.append("%s dropped an eligible layer's teal key (zero-initialised: %s)"
                                % (_tag, "teal" in _got["flare_ray_ur"]))
            if not all(c in _got["field_mid"] for c in ("white", "cyan", "blue")):
                _fp_diag.append("%s did not store the colour-only layer's amounts" % _tag)
            if "teal=    ---" not in _r6.stdout:
                _fp_diag.append("%s reported an ineligible layer as if it held teal" % _tag)
    check("the documented photometric fit completes and saves on every layer schema",
          not _fp_diag, "; ".join(_fp_diag) if _fp_diag else
          "fit_photometry.py (documented mode and --fit-rays) exits 0 and saves, on cone layers "
          "without a teal key (reported ineligible, never given one), six eligible rays (one with "
          "no light at all, key kept), a colour-only layer and the normal-blended frame; calibrated "
          "rays held in the documented mode, a red-shifted layer's colour in both")

    # ---- pruning down to the calibrated rays completes and saves (D68) ---- #
    # The review case (prune_layers.py:42): once pruning has removed every
    # layer the colour fit may move, `held_free` is empty, and fit() stacked
    # zero Jacobian columns and raised -- the command exited before saving.
    # It takes a stack whose protected survivors are all CALIBRATED.  The
    # protected set is every ray of record, and three of those (the white arms
    # flare_ray_a_in, _s_in, _east_in) are not calibrated, so on the shipped
    # file they stay free and the set never empties; every file before the
    # arms (D63, D65) had that shape.  So: the shipped calibrated rays plus
    # two prunable layers, pruned by the real CLI with --keep "" and a
    # threshold nothing can exceed.  The fit's own contract is checked too: an
    # empty free set returns the colours given, and a non-empty one still
    # moves exactly its free rows.
    _pr_diag = []
    _rs = np.random.RandomState(7)
    _Apr = _rs.uniform(0.0, 1.0, (3, 12, 12)).astype(np.float32)
    _tpr = _rs.uniform(0.0, 1.0, (12, 12, 3)).astype(np.float32)
    _wpr0 = np.array([[0.2, 0.3, 0.1, 0.0], [0.1, 0.5, 0.2, 0.0], [0.4, 0.1, 0.3, 0.0]], np.float32)
    _wone = np.ones((12, 12), np.float32)
    for _it, _w0 in ((0, _wpr0), (6, _wpr0), (6, _wpr0.astype(np.float64)), (6, _wpr0.tolist())):
        try:
            _we = _FP.fit(_Apr, _tpr, _w0, _wone, iters=_it, verbose=False, free=[])
        except Exception as _e:
            _pr_diag.append("fit with nothing free (iters %d) raised %s: %s" % (_it, type(_e).__name__, _e))
            continue
        # returned as a fitted result is: a float32 copy, whatever it was given
        if (_we.dtype != np.float32 or _we.shape != _wpr0.shape or not np.array_equal(_we, _wpr0)
                or (isinstance(_w0, np.ndarray) and np.shares_memory(_we, _w0))):
            _pr_diag.append("fit with nothing free (iters %d, %s) did not return a float32 copy of the "
                            "colours given" % (_it, type(_w0).__name__ if not isinstance(_w0, np.ndarray)
                                               else _w0.dtype))
    _wn = _FP.fit(_Apr, _tpr, _wpr0, _wone, iters=6, verbose=False, free=[1])
    if not (np.array_equal(_wn[[0, 2]], _wpr0[[0, 2]]) and not np.array_equal(_wn[1], _wpr0[1])
            and _FP.weighted_sse(_FP.composite(_Apr, _FP.colors(_wn)) - _tpr, _wone)
            < _FP.weighted_sse(_FP.composite(_Apr, _FP.colors(_wpr0)) - _tpr, _wone)):
        _pr_diag.append("fit with one free layer no longer moves exactly that layer and lowers the error")
    _pr_src = json.loads(json.dumps(params))
    _pr_src["layers"] = [L for L in _pr_src["layers"]
                         if L["id"] in MFL.CALIBRATED_LAYERS or L["id"] in ("field_base", "flare_halo")]
    _pr_rays = sorted(L["id"] for L in _pr_src["layers"] if L["id"] in MFL.CALIBRATED_LAYERS)
    _pr_mae = float("nan")
    with _tf.TemporaryDirectory() as _td7:
        _pp = os.path.join(_td7, "prune.json")
        json.dump(_pr_src, open(_pp, "w"), indent=1)
        _r7 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "prune_layers.py"), "--params", _pp,
                       "--apply", "--max-cost", "1e9", "--keep", ""], capture_output=True, text=True)
        if _r7.returncode != 0 or "Traceback" in _r7.stderr:
            _pr_diag.append("prune_layers exited %d: %s"
                            % (_r7.returncode, _r7.stderr.strip().splitlines()[-1:]))
        else:
            _pr_saved = json.load(open(_pp))
            _pr_ids = sorted(L["id"] for L in _pr_saved["layers"])
            _was = {L["id"]: L for L in _pr_src["layers"]}
            _removed = [ln for ln in _r7.stdout.splitlines() if ln.startswith("removed ")]
            if _pr_ids != _pr_rays:
                _pr_diag.append("saved layers %s, expected exactly the calibrated rays" % _pr_ids)
            if len(_removed) != 2 or "wrote " not in _r7.stdout:
                _pr_diag.append("expected two removals and a save, got: %s" % _removed)
            if any(L != _was[L["id"]] for L in _pr_saved["layers"]):
                _pr_diag.append("a held ray's stored colour changed")
            _pr_img = _FP.render_array(build_svg.build(_pr_saved), 1024)
            _pr_mae, _ = _PL.evaluate(_pr_saved, np.minimum(_ref / 255.0, 254.4 / 255.0).astype(np.float32))
            _said = [float(ln.rsplit("mae", 1)[1]) for ln in _r7.stdout.splitlines() if ln.startswith("wrote ")]
            if not (np.isfinite(_pr_img).all() and _pr_img.max() > 0 and np.isfinite(_pr_mae)
                    and _said and abs(_said[0] - _pr_mae) < 1e-3):
                _pr_diag.append("the saved rays-only file does not render and score as reported "
                                "(scored %.4f, reported %s)" % (_pr_mae, _said))
        # The same class of failure one step further (found in review): with
        # NOTHING protected, removing the last layer left an empty stack that
        # basis_stack could not build.  The last layer is never offered.
        _pl = os.path.join(_td7, "prune_last.json")
        json.dump(dict(_pr_src, layers=[L for L in _pr_src["layers"] if L["id"] in ("field_base", "flare_halo")]),
                  open(_pl, "w"), indent=1)
        _r8 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "prune_layers.py"), "--params", _pl,
                       "--apply", "--max-cost", "1e9", "--keep", ""], capture_output=True, text=True)
        if _r8.returncode != 0 or "Traceback" in _r8.stderr:
            _pr_diag.append("pruning a stack with nothing protected exited %d: %s"
                            % (_r8.returncode, _r8.stderr.strip().splitlines()[-1:]))
        elif len(json.load(open(_pl))["layers"]) != 1:
            _pr_diag.append("pruning a stack with nothing protected did not stop at one layer")
    check("pruning down to the calibrated rays completes and saves",
          not _pr_diag, "; ".join(_pr_diag) if _pr_diag else
          "fit returns a float32 copy of the colours given when nothing is free (float32, float64 or "
          "list) and still moves exactly its free rows otherwise; prune_layers --keep '' on %d calibrated "
          "rays + 2 layers removes both, exits 0, saves exactly the rays with their colours untouched, "
          "and the saved file renders and scores %.4f as reported; with nothing protected it stops at "
          "the last layer" % (len(_pr_rays), _pr_mae))

    # The before/after sheet's probes (6i and D65's) run against two
    # baselines.  One is the pinned one, out/baseline/.  The other is this
    # release pinned as its own baseline, which is what a commit that only
    # re-pins the baseline looks like (out/baseline/manifest.json asks for
    # that once a release is accepted): until D71 two probes used the pinned
    # baseline as their "other" SVG and render, and so failed a sound sheet
    # whenever the two were the same release.  Each probe now makes its own
    # other input, and this keeps them honest whether or not they differ.
    def _sheet_baselines(td):
        import hashlib as _hl
        import shutil as _shb
        out = []
        for say, own in (("", False), ("with the release as its own baseline: ", True)):
            d = os.path.join(td, "baseline_own" if own else "baseline")
            os.makedirs(d)
            if own:
                _shb.copy(os.path.join(ROOT, "reconstruction.svg"), d)
                m = json.load(open(os.path.join(ROOT, "out", "baseline", "manifest.json")))
                m["svg"] = "reconstruction.svg"
                m["svg_sha256"] = _hl.sha256(open(os.path.join(d, "reconstruction.svg"), "rb").read()).hexdigest()
                json.dump(m, open(os.path.join(d, "manifest.json"), "w"))
            else:
                for f in ("reconstruction.svg", "manifest.json"):
                    _shb.copy(os.path.join(ROOT, "out", "baseline", f), d)
            _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"),
                     os.path.join(d, "reconstruction.svg"), os.path.join(d, "render_1024.png")],
                    check=True, capture_output=True)
            out.append((say, d))
        return out

    # ---- 6i. the diagnostics refuse inputs they cannot read ---------------- #

    # ray_lines sampled whatever it was given: a 512-px render came back as a
    # column of plausible numbers read off the wrong pixels, and past the image
    # off one replicated edge row.  The canvas is 1024 and everything that
    # places structures in canvas pixels now says so and exits 2.
    import ray_lines as _RL
    import shutil as _sh2
    _diag = []
    with _tf.TemporaryDirectory() as _td3:
        _small = os.path.join(_td3, "small.png")
        Image.open(os.path.join(ROOT, "out", "render_1024.png")).resize((512, 512)).save(_small)
        for _tool, _args in (("ray_lines.py", [_small]), ("visual_regression.py", [_small]),
                             ("flare_parts.py", [_small, "--out", os.path.join(_td3, "fp.png")])):
            _r = _sp.run([sys.executable, os.path.join(ROOT, "tools", _tool)] + _args,
                         capture_output=True, text=True, cwd=ROOT)
            if _r.returncode != 2 or "1024" not in _r.stderr:
                _diag.append("%s on a 512-px image: exit %d" % (_tool, _r.returncode))
        try:
            _RL.profile(np.zeros((512, 512, 3)), *_RL.LINES["lower-right"][:4])
            _diag.append("ray_lines.profile read a 512-px array")
        except ValueError:
            pass
        try:
            _RL._bilinear(np.zeros((1024, 1024)), np.array([1030.0]), np.array([5.0]))
            _diag.append("ray_lines sampled outside the image instead of refusing")
        except ValueError:
            pass
        # The before/after sheet is a publish artefact: built from a baseline
        # whose manifest names its SVG by digest and from renders whose
        # provenance matches the SVGs they are labelled as -- and refused
        # otherwise.  Each probe runs against the pinned baseline and against
        # the release pinned as its own baseline (_sheet_baselines): no probe
        # may lean on the two being different releases.
        import flare_parts as _FPT
        for _bsay, _bd in _sheet_baselines(_td3):
            _sheet = os.path.join(_bd, "sheet.png")
            _fp_args = [os.path.join(ROOT, "out", "render_1024.png"), "--svg",
                        os.path.join(ROOT, "reconstruction.svg"), "--baseline", _bd,
                        "--labels", "this release", "--out", _sheet]
            _r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py")] + _fp_args,
                         capture_output=True, text=True, cwd=ROOT)
            if _r.returncode != 0:
                _diag.append("%sflare_parts refused the shipped release: %s" % (_bsay, _r.stderr.strip()[:160]))
            # ... and it says what it was drawn from, so a stale sheet is caught.
            # (Only if it was drawn: a refusal above is already a failure, and
            # copying a sheet that does not exist would abort the whole suite.)
            if os.path.exists(_sheet):
                _fresh = _FPT.sheet_problems(_sheet, os.path.join(ROOT, "reconstruction.svg"), _bd,
                                             os.path.join(ROOT, "reference.png"))
                if _fresh:
                    _diag.append("%sa sheet drawn just now reads as stale: %s" % (_bsay, _fresh[0]))
                # The different SVG is made here: the release with a comment
                # appended, so its digest differs.  It used to be the
                # baseline's SVG, which on a commit that only re-pins the
                # baseline to this release IS this release -- the probe then
                # compared the release with itself and failed a sound sheet.
                _other = os.path.join(_bd, "other.svg")
                open(_other, "wb").write(open(os.path.join(ROOT, "reconstruction.svg"), "rb").read()
                                         + b"<!-- not the release -->\n")
                if not _FPT.sheet_problems(_sheet, _other, _bd):
                    _diag.append("%sa sheet checked against a different SVG was not reported stale" % _bsay)
                _sh2.copy(_sheet, _sheet + ".t.png")
                _sh2.copy(_sheet + ".prov.json", _sheet + ".t.png.prov.json")
                open(_sheet + ".t.png", "ab").write(b"\0")
                if not _FPT.sheet_problems(_sheet + ".t.png", os.path.join(ROOT, "reconstruction.svg"), _bd):
                    _diag.append("%sa sheet whose bytes changed was not caught" % _bsay)
            _man = json.load(open(os.path.join(_bd, "manifest.json")))
            _man["svg_sha256"] = "0" * 64
            json.dump(_man, open(os.path.join(_bd, "manifest.json"), "w"))
            _r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py")] + _fp_args,
                         capture_output=True, text=True, cwd=ROOT)
            if _r.returncode != 2:
                _diag.append("%sflare_parts drew a sheet whose baseline manifest does not name its SVG" % _bsay)
    check("the diagnostics refuse inputs they cannot read",
          not _diag, "; ".join(_diag) if _diag else
          "ray_lines, visual_regression and flare_parts exit 2 on a 512-px image; no sample "
          "outside the canvas; the before/after sheet verifies its baseline and its release, and "
          "its provenance catches a stale or altered sheet, with the pinned baseline and with the "
          "release as its own baseline")

    # ---- a sheet cannot vouch for a source image it no longer shows (D65) -- #
    # The review case: the sidecar recorded each column's image digest, but
    # sheet_problems compared only SVG digests, so replacing a source render
    # after the sheet was drawn left the sheet "verified" while it showed
    # pixels that were no longer there.  Run on COPIES of the sources, so the
    # repository's own renders are never touched.
    import flare_parts as _FPS
    import shutil as _sh4
    _src_diag = []
    with _tf.TemporaryDirectory() as _td4:
        _rel = os.path.join(_td4, "release.png")
        for _ext in ("", ".prov.json"):
            _sh4.copy(os.path.join(ROOT, "out", "render_1024.png") + _ext, _rel + _ext)
        # (2)'s other authentic render is made here too, by render.py so it has
        # its own sidecar: the release with a mark drawn on it, so its pixels
        # differ (a comment alone changes the SVG's digest and not one pixel).
        # It used to be the baseline's render, which on a commit that only
        # re-pins the baseline to this release IS this render, byte for byte.
        _osvg, _opng = os.path.join(_td4, "other.svg"), os.path.join(_td4, "other.png")
        _svg4 = open(os.path.join(ROOT, "reconstruction.svg"), "rb").read()
        _end4 = _svg4.rindex(b"</svg>")
        open(_osvg, "wb").write(_svg4[:_end4] + b'<rect width="16" height="16" fill="#f0f"/>\n'
                                + _svg4[_end4:])
        _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"), _osvg, _opng],
                check=True, capture_output=True)
        _keep = {q: open(q, "rb").read() for q in (_rel, _rel + ".prov.json")}

        def _restore():
            for q, b in _keep.items():
                open(q, "wb").write(b)
        for _bsay, _bd4 in _sheet_baselines(_td4):
            _sheet4 = os.path.join(_bd4, "sheet.png")
            _r4 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py"), _rel,
                           "--svg", os.path.join(ROOT, "reconstruction.svg"), "--baseline", _bd4,
                           "--labels", "this release", "--out", _sheet4],
                          capture_output=True, text=True, cwd=ROOT)
            _p4 = lambda: _FPS.sheet_problems(_sheet4, os.path.join(ROOT, "reconstruction.svg"),  # noqa: E731
                                              _bd4, os.path.join(ROOT, "reference.png"))
            if _r4.returncode != 0:
                _src_diag.append("%sthe sheet was not drawn: %s" % (_bsay, _r4.stderr.strip()[:160]))
            elif _p4():
                _src_diag.append("%s(1) a fresh sheet with untouched sources reads as stale: %s" % (_bsay, _p4()[0]))
            else:
                # (2) another AUTHENTIC render, with its own valid sidecar, put in its place
                for _ext in ("", ".prov.json"):
                    _sh4.copy(_opng + _ext, _rel + _ext)
                if not any("no longer there" in m for m in _p4()):
                    _src_diag.append("%s(2) a source render replaced by another authentic render passed" % _bsay)
                _restore()
                # (3) same filename, different bytes, sidecar left alone
                open(_rel, "ab").write(b"\0")
                if not _p4():
                    _src_diag.append("%s(3) a source render with changed bytes passed" % _bsay)
                _restore()
                # (4a) the render's provenance removed
                os.remove(_rel + ".prov.json")
                if not any("no provenance" in m for m in _p4()):
                    _src_diag.append("%s(4a) a source render without provenance passed" % _bsay)
                _restore()
                # (4b) provenance naming a different SVG (the render itself unchanged)
                _pv = json.loads(_keep[_rel + ".prov.json"])
                _pv["svg_sha256"] = "0" * 64
                open(_rel + ".prov.json", "w").write(json.dumps(_pv))
                if not _p4():
                    _src_diag.append("%s(4b) a source render whose provenance names another SVG passed" % _bsay)
                _restore()
                if _p4():
                    _src_diag.append("%srestored sources still read as stale: %s" % (_bsay, _p4()[0]))
    check("a before/after sheet re-verifies every source image it was drawn from",
          not _src_diag, "; ".join(_src_diag) if _src_diag else
          "valid sources pass; a source replaced by another authentic render, a source with "
          "changed bytes, a source without provenance and one whose provenance names another "
          "SVG each fail, with the pinned baseline and with the release as its own baseline")

    # ---- the baseline setup is a pinned, verified, reproducible step (D66) - #
    # A clean checkout carries the previous release's SVG, not its render;
    # tools/setup_baseline.py makes the render.  It must render only the pinned
    # SVG, reproduce the image the published sheet was drawn from, and refuse --
    # as a SETUP failure -- anything else; the gate's pre-flight must catch what
    # the setup would.  Run on a copy of the baseline and a stand-in sheet
    # record, so neither the real baseline nor the real sheet is touched.
    import setup_baseline as _SB
    import shutil as _sh5
    import render as _R5
    _sb_diag = []
    with _tf.TemporaryDirectory() as _td5:
        _bd5 = os.path.join(_td5, "baseline")
        os.makedirs(_bd5)
        for _f in ("reconstruction.svg", "manifest.json"):
            _sh5.copy(os.path.join(ROOT, "out", "baseline", _f), _bd5)
        _pin5 = json.load(open(os.path.join(_bd5, "manifest.json")))["svg_sha256"]
        _side5 = os.path.join(_td5, "sheet.png")

        def _sheet5(digest):
            json.dump({"columns": [{"svg": "somewhere/else/reconstruction.svg",   # matched by content
                                    "svg_sha256": _pin5, "image_sha256": digest}]},
                      open(_side5 + ".prov.json", "w"))

        def _pre5():
            return _SB.verify(_bd5, sheet_path=_side5)
        # The image this environment should make: the published sheet's record
        # for this baseline, when the sheet names it (after a new baseline is
        # installed the sheet names the old one, and publish.sh redraws it).
        _want5, _wnote5 = _SB.sheet_expectation(_pin5)
        _real5 = os.path.join(ROOT, "out", "baseline", _SB.RENDER_NAME)
        if _want5 is None and os.path.exists(_real5):
            _want5 = _R5.sha256_file(_real5)
        if not _want5:
            _sb_diag.append("no recorded or set-up baseline image to compare with (%s)" % _wnote5)
        else:
            _sheet5(_want5)
            if not any("absent" in m for m in _pre5()):
                _sb_diag.append("a baseline with no render passed the pre-flight: %s" % _pre5())
            try:
                _out5 = _SB.setup(_bd5, sheet_path=_side5, verbose=False)
                if _pre5():
                    _sb_diag.append("a freshly set-up baseline fails the pre-flight: %s" % _pre5())
                if _R5.sha256_file(_out5) != _want5:
                    _sb_diag.append("the setup render is not the image the sheet recorded")
                # a leftover render with valid provenance but other bytes (another
                # encoder or renderer version) is a SETUP failure, not a stale sheet
                _png5 = os.path.join(_bd5, _SB.RENDER_NAME)
                Image.open(_png5).save(_png5, compress_level=1)
                _R5.write_provenance(_png5, os.path.join(_bd5, "reconstruction.svg"),
                                     open(_png5, "rb").read(), _SB.SIZE, _SB.RENDERER)
                if not any("not the image the published sheet" in m for m in _pre5()):
                    _sb_diag.append("a re-encoded leftover render passed the pre-flight: %s" % _pre5())
            except _SB.SetupError as exc:
                _sb_diag.append("the pinned baseline did not set up: %s" % exc)
            # a render that is not the one the sheet recorded -> SETUP failure,
            # and no render left behind; --for-publish skips that comparison
            _sheet5("0" * 64)
            try:
                _SB.setup(_bd5, sheet_path=_side5, verbose=False)
                _sb_diag.append("a render differing from the sheet's record was accepted")
            except _SB.SetupError as exc:
                if "does not reproduce" not in str(exc):
                    _sb_diag.append("wrong reason for a differing render: %s" % exc)
                if not any("absent" in m for m in _pre5()):
                    _sb_diag.append("a render the sheet does not describe was left for the gate")
            try:
                _SB.setup(_bd5, sheet_path=_side5, compare_sheet=False, verbose=False)
            except _SB.SetupError as exc:
                _sb_diag.append("--for-publish still compared with the old sheet: %s" % exc)
            # ... but a publisher on another resvg-py than the pin is refused:
            # the sheet it drew could not be reproduced by CI
            _inst5 = _SB.installed_renderer
            try:
                _SB.installed_renderer = lambda: "0.0.0-not-the-pin"
                _SB.setup(_bd5, sheet_path=_side5, compare_sheet=False, verbose=False)
                _sb_diag.append("--for-publish accepted a renderer other than the pinned one")
            except _SB.SetupError as exc:
                if "pins" not in str(exc):
                    _sb_diag.append("wrong reason for an unpinned publisher: %s" % exc)
            finally:
                _SB.installed_renderer = _inst5
            _sheet5(_want5)
            # an SVG that is not the pinned one -> SETUP failure, nothing rendered from it
            _svg5 = os.path.join(_bd5, "reconstruction.svg")
            _orig5 = open(_svg5, "rb").read()
            open(_svg5, "ab").write(b"\n<!-- not the release -->\n")
            try:
                _SB.setup(_bd5, sheet_path=_side5, verbose=False)
                _sb_diag.append("an SVG that is not the pinned one was rendered as the baseline")
            except _SB.SetupError:
                if os.path.exists(os.path.join(_bd5, _SB.RENDER_NAME)):
                    _sb_diag.append("a render was left behind from an unpinned SVG")
            open(_svg5, "wb").write(_orig5)
        # the CLI says SETUP FAILURE and exits 3, not 1
        _r5 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "setup_baseline.py"),
                       "--baseline", os.path.join(_td5, "nowhere")], capture_output=True, text=True)
        if _r5.returncode != 3 or "SETUP FAILURE" not in _r5.stderr:
            _sb_diag.append("a missing baseline exits %d without saying SETUP FAILURE" % _r5.returncode)
        # a directory that is not a baseline (no manifest) is refused UNTOUCHED:
        # `--baseline out` must not delete the committed out/render_1024.png
        _nb5 = os.path.join(_td5, "not_a_baseline")
        os.makedirs(_nb5)
        open(os.path.join(_nb5, _SB.RENDER_NAME), "wb").write(b"keep me")
        _r5 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "setup_baseline.py"),
                       "--baseline", _nb5], capture_output=True, text=True)
        if _r5.returncode != 3 or open(os.path.join(_nb5, _SB.RENDER_NAME), "rb").read() != b"keep me":
            _sb_diag.append("setup on a directory without a manifest exited %d and%s left its render alone"
                            % (_r5.returncode, "" if os.path.exists(os.path.join(_nb5, _SB.RENDER_NAME))
                               else " did not"))
        # git is asked only about THIS checkout: an enclosing repository (a
        # source export inside another work tree) is not a clone of this one
        _outer5 = os.path.join(_td5, "outer")
        os.makedirs(os.path.join(_outer5, "export"))
        if _sp.run(["git", "init", "-q", _outer5], capture_output=True).returncode == 0:
            _ok5, _note5 = _SB.check_commit({"commit": "0" * 40, "svg": "reconstruction.svg"}, _pin5,
                                            os.path.join(_outer5, "export"))
            if not _ok5:
                _sb_diag.append("an enclosing repository was taken for this checkout: %s" % _note5)
        # a manifest naming a commit this (full) clone lacks fails verify() too
        _shallow5 = _sp.run(["git", "-C", ROOT, "rev-parse", "--is-shallow-repository"],
                            capture_output=True, text=True).stdout.strip() == "true"
        _man5 = json.load(open(os.path.join(_bd5, "manifest.json")))
        json.dump(dict(_man5, commit="0" * 40), open(os.path.join(_bd5, "manifest.json"), "w"))
        _v5 = _SB.verify(_bd5, sheet_path=_side5)
        if not _shallow5 and not any("does not have" in m for m in _v5):
            _sb_diag.append("verify() passed a manifest naming a commit this full clone lacks: %s" % _v5)
        json.dump(_man5, open(os.path.join(_bd5, "manifest.json"), "w"))
    check("the baseline setup renders only the pinned SVG and reproduces the sheet's baseline",
          not _sb_diag, "; ".join(_sb_diag) if _sb_diag else
          "no render -> pre-flight reports it absent; the pinned SVG sets up to the recorded baseline "
          "image byte for byte (sheet column found by content); a re-encoded leftover render, a "
          "differing render, an unpinned SVG and a missing baseline are each a SETUP failure (exit 3), "
          "nothing left behind; a directory without a manifest is refused untouched; an enclosing "
          "repository is not taken for this checkout, and a manifest naming a commit a full clone "
          "lacks fails verify(); --for-publish skips only the sheet comparison, and refuses a "
          "renderer other than the pinned one")

    # The published sheet is a release artefact (tools/publish.sh regenerates
    # it); a release whose sheet was drawn from anything but this SVG and the
    # documented baseline is not a release (D63).
    import flare_parts as _FPT2
    _pub = _FPT2.sheet_problems(os.path.join(ROOT, "out", "flare_parts.png"),
                                os.path.join(ROOT, "reconstruction.svg"),
                                os.path.join(ROOT, "out", "baseline"),
                                os.path.join(ROOT, "reference.png"))
    check("the published before/after sheet is this release's", not _pub,
          "; ".join(_pub) if _pub else "out/flare_parts.png was drawn from verified renders of "
          "reconstruction.svg and the documented baseline, and is byte-for-byte that sheet")

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
    # `ratio is None` alone no longer means "skipped": a structure the reference
    # has and the render does not also comes back None, and it is a FAILURE.
    # Only the ok ones are genuine skips, and a failing row may carry no ratio
    # to format.
    vnm = [n for n, ratio, lo, hi, ok, _rv, _cv, _m in vrows if ratio is None and ok]
    # A structure the reference HAS and the render does NOT must fail, not be
    # waved through as unmeasurable: two of these checks read None on the
    # candidate side precisely when the structure is gone, and both used to
    # report "NOT MEASURABLE" and pass.  An all-black candidate is the cleanest
    # statement of that -- every structure is absent by construction.
    _black = np.zeros((1024, 1024, 3), dtype=np.float64)
    _brows = _VR.report(_VR.np.asarray(Image.open(os.path.join(ROOT, "reference.png"))
                                       .convert("RGB")).astype(np.float64), _black)
    _bfail = sum(1 for _n, _r, _lo, _hi, _ok, _rv, _cv, _m in _brows if not _ok)
    _bnone_pass = [n for n, r, _lo, _hi, ok, _rv, _cv, _m in _brows if r is None and ok]
    check("a structure the render has lost cannot pass as unmeasurable",
          _bfail >= 10 and not _bnone_pass,
          "an all-black candidate fails %d of %d checks; skipped-as-unmeasurable: %s"
          % (_bfail, len(_brows), ", ".join(_bnone_pass) if _bnone_pass else "none"))

    check("the reference's structures are all still represented",
          not vbad,
          "%d checks, %d not measurable%s; %s"
          % (len(vrows), len(vnm),
             (" (%s)" % ", ".join(vnm)) if vnm else "",
             ", ".join("%s %s" % (n, "MISSING" if r is None else "%.2fx" % r)
                       for n, r in vbad) if vbad
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
    #
    # D64 added a fourth primary, TEAL, for six ray layers whose own lines are
    # greener than the cone.  It is a decision made where the cone is defined
    # (fit_photometry TEAL, measure_flare TEAL_LAYERS), so this also requires
    # that exactly those layers carry it and that no other layer's colour has
    # left the white/cyan/blue cone.
    import measure_flare as _MF2
    off_cone = []
    for L in params["layers"]:
        c = L.get("color")
        if c is None:
            continue
        want = np.clip(np.asarray(_FP.color_from_wc(
            [L.get(k, 0.0) for k in _FP.COMPONENTS]), float) * 255.0, 0, 255)
        got = np.clip(np.asarray(c, float), 0, 255)
        d = float(np.abs(want - got).max())
        if d > 0.05:
            off_cone.append("%s (%.1f cv)" % (L["id"], d))
        # A layer without a `teal` key is drawn from white/cyan/blue alone
        # (L.get("teal", 0.0) above), so passing the comparison above already
        # puts it inside the cone.  Re-decomposing the stored colour instead
        # would misfire on a colour clipped at 255 (arc_core's G).
    _teal = sorted(L["id"] for L in params["layers"] if "teal" in L)
    if _teal != sorted(_MF2.TEAL_LAYERS):
        off_cone.append("teal carried by %s, of record %s" % (_teal, sorted(_MF2.TEAL_LAYERS)))
    check("every layer's colour is reachable from its white/cyan/blue(/teal)",
          not off_cone,
          "%d layers, %d of them teal layers of record; off-cone: %s"
          % (len(params["layers"]), len(_teal), ", ".join(off_cone) or "none"))

    # ---- a horizontal line drawn as two colours is still ONE line ----------- #
    # Lines A and B each carry their white in a layer of its own (flare_streak_w,
    # and since D64 flare_spike_w) so white and cyan can follow different
    # longitudinal profiles.  That is only one line if both layers sit on the
    # same row and run the same length; a search that moved one of the pair
    # would draw two thin lines where the reference has one.  (Widths may
    # differ: line A's white is measured narrower than its cyan.)
    _byid = {L["id"]: L for L in params["layers"]}
    _pair_bad = []
    for _cy, _w in (("flare_streak", "flare_streak_w"), ("flare_spike", "flare_spike_w")):
        if _cy not in _byid or _w not in _byid:
            _pair_bad.append("%s/%s missing" % (_cy, _w))
            continue
        for _k in ("cy", "dy", "half_len"):
            if _byid[_cy].get(_k) != _byid[_w].get(_k):
                _pair_bad.append("%s %s %r != %s %r" % (_cy, _k, _byid[_cy].get(_k), _w, _byid[_w].get(_k)))
    check("each two-colour horizontal line is one line (same row and length)",
          not _pair_bad, "; ".join(_pair_bad) or "line A and line B pairs agree")

    # ---- render provenance cannot authenticate a raster it does not describe #
    # The three-step case the review asks for, run for real rather than
    # asserted: render a known SVG, replace the PNG underneath its sidecar, and
    # require that validation FAILS.  Before the fix it passed, because the
    # sidecar's `svg_sha256` was read without ever hashing the PNG -- so every
    # downstream report went on attributing its numbers to an SVG that had not
    # produced the raster being measured.
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
        # step 5: an AUTHENTIC raster can still be the wrong one.  validate.py
        # writes a Chromium render of this same SVG into the same directory with
        # a sidecar of its own, so "came from this SVG" does not mean "is the
        # 1024 resvg acceptance render" -- copying one over the other satisfies
        # every digest.  The size and renderer have been in the sidecar all
        # along; the acceptance callers now read them.
        open(_png, "wb").write(_data)
        _R.write_provenance(_png, _svg, _data, 64, "chromium")
        step5 = _R.read_provenance(_png, require=True) == _R.sha256_file(_svg)
        try:
            _R.read_provenance(_png, require=True, expect_renderer="resvg")
            step6 = False
        except _R.ProvenanceError:
            step6 = True
        try:
            _R.read_provenance(_png, require=True, expect_size=1024)
            step7 = False
        except _R.ProvenanceError:
            step7 = True
        # step 8: everything above authenticates the RASTER.  `svg_sha256` was
        # still a recorded claim about a file nobody re-read, so a render that
        # is authentic AND stale -- its SVG rebuilt since -- passed every check
        # here.  That is not hypothetical: three of this iteration's eight
        # verifiers measured a model four commits old.  `expect_svg` re-hashes
        # the SVG the caller believes it is measuring.
        step8 = _R.read_provenance(_png, require=True, expect_svg=_svg) \
            == _R.sha256_file(_svg)
        open(_svg, "a").write("<!-- the SVG moves on without the render -->")
        try:
            _R.read_provenance(_png, require=True, expect_svg=_svg)
            step9 = False
        except _R.ProvenanceError:
            step9 = True
        # and the raster alone is still accepted, because staleness is opt-in:
        # an ad-hoc render of a scratch SVG is legitimate
        step10 = _R.read_provenance(_png, require=True) is not None
        # step 11: an expectation is a REQUIREMENT.  `require` alone gated the
        # absent-sidecar return, so expect_size/renderer/svg WITHOUT
        # --require-provenance were silently not run on a render that had no
        # sidecar to run them against: compare.py exited 0 and published metrics
        # for unverified bytes, having been asked for proof of the opposite.
        _R.clear_provenance(_png)
        step11 = []
        for _kw in ({"expect_size": 64}, {"expect_renderer": "resvg"},
                    {"expect_svg": _svg}, {"expect_size": 64, "expect_svg": _svg}):
            try:
                _R.read_provenance(_png, **_kw)
                step11.append(False)
            except _R.ProvenanceError:
                step11.append(True)
        step11 = all(step11)
        # ... and with nothing asked of it, an absent sidecar is still an absence
        step12 = _R.read_provenance(_png) is None
        # step 13: parsing says the file is JSON, not that it is a sidecar.
        # Four roots parse and none of them records a field, and each used to
        # reach `.get` and raise AttributeError -- past the contract, and past
        # the callers, that the digest-shape check exists to protect.
        step13 = []
        for _root in ("[]", "null", '"x"', "3", "true"):
            open(_R.provenance_path(_png), "w").write(_root)
            try:
                _R.read_provenance(_png, require=True)
                step13.append(False)
            except _R.ProvenanceError:
                step13.append(True)
            except Exception:                                  # noqa: BLE001
                step13.append(False)
        step13 = all(step13)
    _steps = (step1, step2, step3, step4, step5, step6, step7, step8, step9,
              step10, step11, step12, step13)
    check("a render sidecar cannot authenticate a PNG it does not describe",
          all(_steps),
          "valid render accepted: %s; replaced PNG rejected: %s; "
          "absent provenance optional: %s; absent provenance required-fails: %s; "
          "authentic-but-wrong-engine accepted without the expectation: %s, "
          "rejected with it: %s; wrong size rejected: %s; "
          "matching SVG accepted: %s; authentic-but-stale SVG rejected: %s; "
          "staleness stays opt-in: %s; an expectation without a sidecar is an "
          "error: %s; asking nothing still is not: %s; a JSON root that is not "
          "an object is a ProvenanceError: %s" % _steps)

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
    _setup = preflight()
    if _setup:
        print("SETUP FAILURE: " + "; ".join(_setup))
        print("Run `python3 tools/setup_baseline.py` first (CI: the \"Baseline setup\" step). "
              "This is a setup failure, not an artwork regression: no check was run.")
        sys.exit(3)
    sys.exit(main())
