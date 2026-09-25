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
    # number -- 486 of the model's 627 numeric leaves are unbounded on purpose,
    # so a report of all of them reports nothing.  What CAN be pinned is the
    # inventory: every unbounded number today belongs to one of fourteen kinds,
    # each searched by a different mechanism or measured rather than fitted.  A
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
                            teal_ok=_FPf.teal_eligible(_pert))
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
                   teal_ok=_FP.teal_eligible(params))
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
    # Cyan and teal differ only in blue, so the fit walks that direction slowly
    # (12 / 40 / 120 iterations reach 0.020 / 0.049 / 0.088 of 0.109): what is
    # tested is that the amount LEAVES zero and the colour leaves the cone.
    _wfit = _FP.fit(_AT, _tgtT, _w0, np.ones(_tgtT.shape[:2], np.float32), iters=40, verbose=False,
                    free=[_iu], normal=_nfT, teal_ok=_okT)
    _want_t = float(_WCs[_iu, _FP.CONE])
    _got_t = float(_wfit[_iu, _FP.CONE])
    _cf = np.asarray(_FP.color_from_wc(_wfit[_iu]), float)
    _bg = float(_cf[2] / max(_cf[1], 1e-9))
    if not _okT[_iu] or _w0[_iu, _FP.CONE] != 0.0 or _got_t < 0.3 * _want_t or _bg > 0.95:
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
    check("an eligible layer recovers teal from zero; an ineligible one never gains it",
          not _teal_diag, "; ".join(_teal_diag) if _teal_diag else
          "flare_ray_ur from teal 0 -> %.4f (target %.4f), B/G %.2f off the cone; flare_ray_c "
          "against a teal target stays at 0; without eligibility no teal amount moves"
          % (_got_t, _want_t, _bg))

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
        # otherwise.
        _bd = os.path.join(_td3, "baseline")
        os.makedirs(_bd)
        for _f in ("reconstruction.svg", "manifest.json"):
            _sh2.copy(os.path.join(ROOT, "out", "baseline", _f), _bd)
        _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"),
                 os.path.join(_bd, "reconstruction.svg"), os.path.join(_bd, "render_1024.png")],
                check=True, capture_output=True)
        _fp_args = [os.path.join(ROOT, "out", "render_1024.png"), "--svg",
                    os.path.join(ROOT, "reconstruction.svg"), "--baseline", _bd,
                    "--labels", "this release", "--out", os.path.join(_td3, "sheet.png")]
        _r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py")] + _fp_args,
                     capture_output=True, text=True, cwd=ROOT)
        if _r.returncode != 0:
            _diag.append("flare_parts refused the shipped release: %s" % _r.stderr.strip()[:160])
        # ... and it says what it was drawn from, so a stale sheet is caught.
        import flare_parts as _FPT
        _sheet = os.path.join(_td3, "sheet.png")
        # (Only if it was drawn: a refusal above is already a failure, and
        # copying a sheet that does not exist would abort the whole suite.)
        if os.path.exists(_sheet):
            _fresh = _FPT.sheet_problems(_sheet, os.path.join(ROOT, "reconstruction.svg"), _bd,
                                         os.path.join(ROOT, "reference.png"))
            if _fresh:
                _diag.append("a sheet drawn just now reads as stale: %s" % _fresh[0])
            if not _FPT.sheet_problems(_sheet, os.path.join(_bd, "reconstruction.svg"), _bd):
                _diag.append("a sheet checked against a different SVG was not reported stale")
            _sh2.copy(_sheet, _sheet + ".t.png")
            _sh2.copy(_sheet + ".prov.json", _sheet + ".t.png.prov.json")
            open(_sheet + ".t.png", "ab").write(b"\0")
            if not _FPT.sheet_problems(_sheet + ".t.png", os.path.join(ROOT, "reconstruction.svg"), _bd):
                _diag.append("a sheet whose bytes changed was not caught")
        _man = json.load(open(os.path.join(_bd, "manifest.json")))
        _man["svg_sha256"] = "0" * 64
        json.dump(_man, open(os.path.join(_bd, "manifest.json"), "w"))
        _r = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py")] + _fp_args,
                     capture_output=True, text=True, cwd=ROOT)
        if _r.returncode != 2:
            _diag.append("flare_parts drew a sheet whose baseline manifest does not name its SVG")
    check("the diagnostics refuse inputs they cannot read",
          not _diag, "; ".join(_diag) if _diag else
          "ray_lines, visual_regression and flare_parts exit 2 on a 512-px image; no sample "
          "outside the canvas; the before/after sheet verifies its baseline and its release, and "
          "its provenance catches a stale or altered sheet")

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
        _bd4 = os.path.join(_td4, "baseline")
        os.makedirs(_bd4)
        for _f in ("reconstruction.svg", "manifest.json"):
            _sh4.copy(os.path.join(ROOT, "out", "baseline", _f), _bd4)
        _sp.run([sys.executable, os.path.join(ROOT, "tools", "render.py"),
                 os.path.join(_bd4, "reconstruction.svg"), os.path.join(_bd4, "render_1024.png")],
                check=True, capture_output=True)
        _sheet4 = os.path.join(_td4, "sheet.png")
        _r4 = _sp.run([sys.executable, os.path.join(ROOT, "tools", "flare_parts.py"), _rel,
                       "--svg", os.path.join(ROOT, "reconstruction.svg"), "--baseline", _bd4,
                       "--labels", "this release", "--out", _sheet4],
                      capture_output=True, text=True, cwd=ROOT)
        _p4 = lambda: _FPS.sheet_problems(_sheet4, os.path.join(ROOT, "reconstruction.svg"),  # noqa: E731
                                          _bd4, os.path.join(ROOT, "reference.png"))
        _keep = {q: open(q, "rb").read() for q in (_rel, _rel + ".prov.json")}

        def _restore():
            for q, b in _keep.items():
                open(q, "wb").write(b)
        if _r4.returncode != 0:
            _src_diag.append("the sheet was not drawn: %s" % _r4.stderr.strip()[:160])
        elif _p4():
            _src_diag.append("(1) a fresh sheet with untouched sources reads as stale: %s" % _p4()[0])
        else:
            # (2) another AUTHENTIC render, with its own valid sidecar, put in its place
            for _ext in ("", ".prov.json"):
                _sh4.copy(os.path.join(_bd4, "render_1024.png") + _ext, _rel + _ext)
            if not any("no longer there" in m for m in _p4()):
                _src_diag.append("(2) a source render replaced by another authentic render passed")
            _restore()
            # (3) same filename, different bytes, sidecar left alone
            open(_rel, "ab").write(b"\0")
            if not _p4():
                _src_diag.append("(3) a source render with changed bytes passed")
            _restore()
            # (4a) the render's provenance removed
            os.remove(_rel + ".prov.json")
            if not any("no provenance" in m for m in _p4()):
                _src_diag.append("(4a) a source render without provenance passed")
            _restore()
            # (4b) provenance naming a different SVG (the render itself unchanged)
            _pv = json.loads(_keep[_rel + ".prov.json"])
            _pv["svg_sha256"] = "0" * 64
            open(_rel + ".prov.json", "w").write(json.dumps(_pv))
            if not _p4():
                _src_diag.append("(4b) a source render whose provenance names another SVG passed")
            _restore()
            if _p4():
                _src_diag.append("restored sources still read as stale: %s" % _p4()[0])
    check("a before/after sheet re-verifies every source image it was drawn from",
          not _src_diag, "; ".join(_src_diag) if _src_diag else
          "valid sources pass; a source replaced by another authentic render, a source with "
          "changed bytes, a source without provenance and one whose provenance names another "
          "SVG each fail")

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
    sys.exit(main())
