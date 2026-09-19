#!/usr/bin/env python3
"""Coordinate-descent optimisation of the reconstruction's parameters.

The loop is cheap because of the closed-form compositing model (see
src/build_svg.py): changing one layer's *shape* only invalidates that layer's
coverage field, so one 60 ms resvg render plus an analytic colour refit is a
full objective evaluation.

Objective = sum of squared errors against reference.png, weighted by
d(v^(1/2.2))/dv so that the large, very dark background counts the way the eye
counts it rather than the way linear sRGB counts it.  Colours are always
re-fitted for the trial geometry, so the search never penalises a good shape
for having stale amplitudes.

    python3 tools/optimize.py --spec shapes --sweeps 3
    python3 tools/optimize.py --spec geometry --sweeps 2
    python3 tools/optimize.py --spec all --sweeps 4 --stride 2
"""
from __future__ import annotations

import argparse
import copy
import json
import hashlib
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import build_svg  # noqa: E402
import fit_photometry as FP  # noqa: E402


# --------------------------------------------------------------------------- #
# parameter addressing
# --------------------------------------------------------------------------- #
def get_path(params, path):
    node = params
    for k in path.split("/"):
        if isinstance(node, list):
            node = node[int(k)]
        elif k.isdigit() and isinstance(node, dict) and k in node:
            node = node[k]
        else:
            node = node[k]
    return node


def set_path(params, path, value):
    keys = path.split("/")
    node = params
    for k in keys[:-1]:
        node = node[int(k)] if isinstance(node, list) else node[k]
    last = keys[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def layer_index(params, lid):
    for i, L in enumerate(params["layers"]):
        if L["id"] == lid:
            return i
    raise KeyError(lid)


def layer_specs(params, keys=("width", "blur", "inset", "r", "squash", "rot",
                              "half_len", "height", "len", "peak_at", "onset", "cx", "cy",
                              "sigma_y", "sigma_x", "blur_x", "blur_y", "spread", "dx", "dy",
                              "scale", "inner", "east_gain", "south_gain")):
    """One spec per tunable shape number on each layer.

    Per-layer `bounds` in params.json win over the global defaults.  They are
    what keeps the layer stack meaningful: without them the search happily
    swaps a "near" glow and a "wide" glow, or collapses the core stroke into
    the halo, which costs nothing numerically but destroys the artwork's
    editability.

    `keys` is the whole of what can be searched, so a name missing from it is a
    parameter that silently never moves however carefully its bounds were
    chosen.  That is not hypothetical: the vertical streak shipped with bounds
    on `sigma_x` and `south_gain` -- its transverse width and its north/south
    balance, the two numbers that decide what it looks like -- and neither name
    was here, so `--spec shapes` and `--spec all` both left them frozen at the
    values they were first guessed at.  `verify_searchable()` now fails the
    regression suite if any bounded parameter is unreachable, so the list
    cannot fall behind the model again.
    """
    out = []
    for i, L in enumerate(params["layers"]):
        b = L.get("bounds", {})
        for k in keys:
            if k not in L:
                continue
            # A parameter may be a scalar or, for anisotropic blur, a two-element
            # [x, y] list.  Each component is searched separately: the streak's
            # cross-section is set by its y blur alone, and collapsing the pair
            # to one scalar would make that unreachable.
            if isinstance(L[k], (int, float)):
                components = [("layers/%d/%s" % (i, k), float(L[k]))]
            elif isinstance(L[k], list) and all(isinstance(q, (int, float)) for q in L[k]):
                components = [("layers/%d/%s/%d" % (i, k, j), float(q)) for j, q in enumerate(L[k])]
            else:
                continue
            for j, (path, v) in enumerate(components):
                lo, hi, step = SHAPE_BOUNDS.get(k, (0.0, 2000.0, None))
                if k in ("cx", "cy"):
                    lo, hi, step = v - 40.0, v + 40.0, 1.5
                if k in b:
                    # `bounds` may give one [lo, hi] pair for the whole
                    # parameter, or one pair per component -- the streak's x
                    # and y blur need different ranges, since the x blur is
                    # deliberately zero.
                    bk = b[k]
                    if len(components) > 1 and isinstance(bk[0], (list, tuple)):
                        lo, hi = bk[min(j, len(bk) - 1)]
                    else:
                        lo, hi = bk
                st = step if step is not None else max(0.02, abs(v) * 0.12)
                out.append({"path": path, "lo": lo, "hi": hi,
                            "step": st, "affects": [L["id"]]})
        # `profile` and, where a primitive's two sides are fitted separately,
        # `profile_e`.  Both are searched; a side whose falloff is not its own
        # is simply absent from the layer and contributes no spec.
        for key, bname in (("profile", "profile"), ("profile_e", "profile_e")):
            pr = L.get(key)
            if not isinstance(pr, dict):
                continue
            pk = "sigma" if "sigma" in pr else ("scale" if "scale" in pr else "n")
            if pk in pr:
                lo, hi = b.get(bname, b.get("profile", (0.03, 4.0)))
                out.append({"path": "layers/%d/%s/%s" % (i, key, pk), "lo": lo, "hi": hi,
                            "step": max(0.01, abs(float(pr[pk])) * 0.12),
                            "affects": [L["id"]]})
        pt = L.get("paint")
        if isinstance(pt, dict) and pt.get("kind") == "radial":
            lo, hi = b.get("paint_r", (100.0, 1200.0))
            out.append({"path": "layers/%d/paint/r" % i, "lo": lo, "hi": hi,
                        "step": max(2.0, float(pt["r"]) * 0.08), "affects": [L["id"]]})
            # A named falloff law has one shape parameter to tune; an explicit
            # stop table (used where the falloff was measured directly) has no
            # single knob, so only its radius is searched.
            prof = pt.get("profile")
            if isinstance(prof, dict):
                pk = "sigma" if "sigma" in prof else "scale"
                lo, hi = b.get("paint_profile", (0.05, 2.0))
                out.append({"path": "layers/%d/paint/profile/%s" % (i, pk), "lo": lo, "hi": hi,
                            "step": max(0.01, float(prof[pk]) * 0.1), "affects": [L["id"]]})
            if "squash" in pt:
                lo, hi = b.get("paint_squash", (0.5, 2.2))
                out.append({"path": "layers/%d/paint/squash" % i, "lo": lo, "hi": hi,
                            "step": 0.02, "affects": [L["id"]]})
            # A radial paint's own centre.  These are nested one level deeper
            # than a layer's `cx`/`cy` and were reached by neither: the loop
            # above only sees top-level keys and the block here only emitted the
            # radius, the falloff and the squash.  So `exterior_corner` and
            # `frame_rim` -- the two layers whose paint is positioned rather
            # than concentric -- had frozen centres.  Same +-40 px window and
            # 1.5 px step as a top-level centre, for the same reason: a centre
            # is not a shape number and a wide search moves it into a different
            # layer's job.
            for k in ("cx", "cy"):
                if k in pt:
                    v = float(pt[k])
                    lo, hi = b.get("paint_" + k, (v - 40.0, v + 40.0))
                    out.append({"path": "layers/%d/paint/%s" % (i, k), "lo": lo, "hi": hi,
                                "step": 1.5, "affects": [L["id"]]})
    return out


def verify_searchable(params, specs=None):
    """Bounds that no spec can reach, and specs whose interval excludes their value.

    Two failure modes, both silent and both of which have shipped:

    * a parameter carries a carefully measured `bounds` entry in params.json
      and is simply absent from `layer_specs`' `keys`, so the search never
      touches it.  `flare_vline.sigma_x` and `flare_vline.south_gain` were in
      that state for a whole release -- the vertical streak's width and its
      north/south balance, frozen at their first guess while every report said
      the shapes had been optimised;

    * a bound is narrowed (or a value is edited) until the interval no longer
      contains the current value, which makes the first trial of that sweep an
      unconditional change.

    Returns (unreachable, invalid).  `unreachable` is a list of
    (layer_id, bound_name); `invalid` is a list of (path, value, lo, hi).
    A bound name maps to a spec path through BOUND_PATHS, so a new nested
    parameter has to be declared here as well as emitted -- which is the point:
    the two lists cannot drift apart without this failing.

    SCOPE, stated because it is easy to over-read: this audits `bounds` entries
    against emitted specs and nothing else.  A numeric field that carries no
    bound is invisible to it and can stay frozen without ever appearing here --
    `flare_wash_far`'s sigma_y was exactly that in reverse (a bound that WAS
    reachable and still wrong).  "No unreachable bounds" means the declared
    search space is fully covered, not that every number in the model is
    searched.

    That blind spot was then measured rather than left as a caveat.  470 of the
    artwork's 609 numeric leaves carry no bound, so flagging unbounded fields
    flags three quarters of the model and says nothing; what is checkable is the
    inventory.  Every one of those 470 falls into twelve kinds -- the
    white/cyan/blue coefficients and the `color` derived from them (fitted
    photometrically, not searched), four kinds of table measured off the
    reference, and `paint/x1..y2`, eight canvas gradient extents that really
    are frozen with no mechanism behind them.  Those eight move MAE by at most
    0.0005 at +-40 px, which is why they stay frozen; see D55.
    test_pipeline.py pins the inventory, so a new unbounded field in a NEW kind
    -- the case this function cannot see -- fails there instead of passing
    silently here.
    """
    if specs is None:
        specs = layer_specs(params)
    paths = {sp["path"] for sp in specs}
    unreachable = []
    for i, L in enumerate(params["layers"]):
        for name in L.get("bounds", {}):
            prefixes = BOUND_PATHS.get(name, ("layers/%d/%s" % (i, name),))
            if isinstance(prefixes, str):
                prefixes = (prefixes,)
            # Exact path, or a descendant separated by "/" -- NOT a raw prefix.
            # `startswith` matched sibling names that merely begin with the same
            # letters, so a `blur_x` spec satisfied an unreachable `blur` bound
            # and `profile_e` satisfied `profile`: the guard reported nothing
            # unreachable while the parameter was frozen, which is the exact
            # failure it exists to catch.  The descendant form is still needed,
            # because a named-law profile is searched at `.../profile/scale`.
            for pre in prefixes:
                root = pre % i if "%d" in pre else pre
                if any(q == root or q.startswith(root + "/") for q in paths):
                    hit = True
                    break
            else:
                hit = False
            if not hit:
                unreachable.append((L["id"], name))
    invalid = []
    for sp in specs:
        v = float(get_path(params, sp["path"]))
        if not (sp["lo"] <= v <= sp["hi"]):
            invalid.append((sp["path"], v, sp["lo"], sp["hi"]))
    return unreachable, invalid


#: bound name in params.json -> the spec path prefix(es) that would search it.
#: `%d` is the layer index.  A plain shape number needs no entry; only the
#: nested ones, whose bound name and path spelling differ, do.
BOUND_PATHS = {
    "paint_r": ("layers/%d/paint/r",),
    "paint_squash": ("layers/%d/paint/squash",),
    "paint_profile": ("layers/%d/paint/profile",),
    "paint_cx": ("layers/%d/paint/cx",),
    "paint_cy": ("layers/%d/paint/cy",),
    "profile": ("layers/%d/profile", "layers/%d/paint/profile"),
    "profile_e": ("layers/%d/profile_e",),
}


SHAPE_BOUNDS = {
    #: The streak's east/west brightness ratio; see the `streak` kind in
    #: src/build_svg.py for the measurement that makes it a parameter.
    "east_gain": (0.05, 2.5, 0.04),
    "onset": (0.0, 0.7, 0.02),
    "dx": (-40.0, 40.0, 0.5),
    "dy": (-40.0, 40.0, 0.5),
    "scale": (10.0, 400.0, 4.0),
    "inner": (0.0, 120.0, 2.0),
    "spread": (1.0, 8.0, 0.2),
    "sigma_y": (0.8, 24.0, 0.15),
    #: The vertical streak's transverse width -- the same quantity as `sigma_y`
    #: with the axes exchanged, so it gets the same range and step.
    "sigma_x": (0.8, 24.0, 0.15),
    #: The vertical streak's south/north brightness ratio, the counterpart of
    #: `east_gain` on a horizontal one.
    "south_gain": (0.05, 2.5, 0.04),
    "blur_x": (0.0, 6.0, 0.2),
    "blur_y": (0.0, 6.0, 0.2),
    "half_len": (30.0, 500.0, None),
    "height": (2.0, 200.0, None),
    "len": (30.0, 400.0, None),
    "peak_at": (0.05, 0.8, 0.03),
    "width": (0.2, 900.0, None),
    #: `blur` is QUANTISED by the acceptance renderer, and the step below can be
    #: smaller than the quantum.  Measured on the upper-left ray: every value
    #: from 3.91 to 4.60 renders BIT-IDENTICALLY and the first change is at 4.75.
    #: The default step here is max(0.02, 0.12*v), which is 0.54 at v = 4.5 --
    #: comparable to that plateau -- so a fraction of the blur trials are no-ops
    #: rather than rejections, and a fitted blur is not meaningful to three
    #: figures.  This is a property of the renderer, not of the search, so it is
    #: recorded rather than corrected: widening the step would trade one kind of
    #: blindness for another.
    "blur": (0.0, 400.0, None),
    "inset": (-40.0, 320.0, 2.0),
    "r": (4.0, 1400.0, None),
    "squash": (0.004, 12.0, None),
    "rot": (-90.0, 90.0, 2.0),
}


def taper_specs(params):
    out = []
    for name, t in params["tapers"].items():
        users = [L["id"] for L in params["layers"] if L.get("taper") == name]
        if not users:
            continue
        for k, (lo, hi, st) in (("y0", (20, 500, 6)), ("y1", (60, 520, 10)),
                                ("y2", (500, 980, 10)), ("y3", (520, 1010, 6)),
                                ("p0", (0.2, 4.0, 0.08)), ("p1", (0.2, 4.0, 0.08)),
                                ("gamma", (0.3, 3.0, 0.06)), ("scale", (0.35, 1.0, 0.04)),
                                ("y_offset", (-14.0, 14.0, 1.0))):
            if k in t:
                out.append({"path": "tapers/%s/%s" % (name, k), "lo": lo, "hi": hi,
                            "step": st, "affects": users})
    return out


def geometry_specs(params):
    """Global geometry.

    The arc control points are deliberately NOT in here: they were fitted to
    the sub-pixel ridge at 0.09 px RMS, which is better than a search against a
    noisy raster objective can do, and letting them drift would trade a
    measured quantity for a metric.  What is searched is the geometry the
    photometry is genuinely ambiguous about: where the central light sits, the
    frame box and stroke width, and how far past the curve the glow clip
    reaches.
    """
    out = []
    for k, st in (("cx", 1.0), ("cy", 1.0)):
        v = float(params["flare"][k])
        # Ask the builder which layers actually read the global flare centre
        # instead of restating the rule here; the two had drifted apart, and
        # the streak layers were being scored at a stale position.
        out.append({"path": "flare/%s" % k, "lo": v - 30, "hi": v + 30, "step": st,
                    "affects": build_svg.flare_dependent_layers(params)})
    # The frame's four centre-lines are NOT searched either: they are fitted to
    # 371-461 cross-sections per edge with a standard deviation of 0.02-0.04 px,
    # which is far better than this objective can resolve -- and a raster
    # objective will happily trade 0.3 px of a measured edge position against a
    # photometric error somewhere else.  Only the corner shape is searched.
    # `corner_r_blend` is NOT searched.  The corner fit measures the blend's
    # lateral offset r_blend * (1 - cos(blend_deg)) = 2.52 px, and the radius and
    # the turn angle are strongly correlated inside that product: searching both
    # lets the radius wander hundreds of px for no change in the rendered
    # outline (it drifted 639.06 -> 619.06 for a 0.08 px change in the offset,
    # and then the documented value was simply wrong).  The angle alone spans
    # the identifiable direction.
    for k, st, span in (("corner_r_main", 1.0, 8.0), ("corner_blend_deg", 0.15, 2.5)):
        v = float(params["frame"][k])
        out.append({"path": "frame/%s" % k, "lo": v - span, "hi": v + span,
                    "step": st, "affects": "all"})
    v = float(params["geometry"].get("lens_grow", 1.5))
    out.append({"path": "geometry/lens_grow", "lo": -2.0, "hi": 12.0, "step": 0.6,
                "affects": [L["id"] for L in params["layers"] if L.get("clip") == "lens"]})
    for side in ("left", "right"):
        for k, st in (("rx", 1.0), ("ry", 1.0)):
            v = float(params["geometry"]["lens_ellipse"][side][k])
            out.append({"path": "geometry/lens_ellipse/%s/%s" % (side, k),
                        "lo": v - 8, "hi": v + 8, "step": st,
                        "affects": [L["id"] for L in params["layers"] if L.get("clip") == "lens"]})
    return out


def field_specs(params):
    """Centres of the background gradient fields.

    Two things this must get right, both of which it previously did not:

    * the bounds are built around the *current* value, not a fixed window.  The
      interior field gradient is centred at (890, 741) -- deliberately outside
      the canvas, because the field is brightest at the inner top-left corner
      and darkest at the bottom-right -- and a hard [200, 820] window put it
      out of bounds, so every trial was rejected and the parameter was frozen.
    * a radial gradient's centre may live in the layer itself (`cx`) or inside
      its paint (`paint/cx`), which is how a `canvas` layer stores it.  Only
      the first was looked for, so the exterior field's centre never moved.
    """
    out = []
    span, step = 260.0, 6.0
    for i, L in enumerate(params["layers"]):
        if L["kind"] not in ("field_radial", "canvas", "radial", "frame_corner_glow"):
            continue
        holders = []
        if "cx" in L and isinstance(L["cx"], (int, float)):
            holders.append("")
        pt = L.get("paint")
        if isinstance(pt, dict) and pt.get("kind") == "radial" and "cx" in pt:
            holders.append("paint/")
        for h in holders:
            for k in ("cx", "cy"):
                path = "layers/%d/%s%s" % (i, h, k)
                v = float(get_path(params, path))
                lo, hi = L.get("bounds", {}).get(h.replace("/", "_") + k, (v - span, v + span))
                out.append({"path": path, "lo": lo, "hi": hi, "step": step,
                            "affects": [L["id"]]})
    return out


# --------------------------------------------------------------------------- #
# objective
# --------------------------------------------------------------------------- #
class Objective:
    def __init__(self, reference, stride=2, fit_iters=3, size=1024):
        ref = np.asarray(Image.open(reference).convert("RGB")).astype(np.float32) / 255.0
        self.size = size
        self.target_full = np.minimum(ref, 254.4 / 255.0)
        self.stride = stride
        self.fit_iters = fit_iters
        self.cache = {}
        self.K = None
        self.n_render = 0

    def basis(self, params, lid):
        """Layer `lid`'s coverage field, cached on the CONTENT of its markup.

        The cache key is a hash of the SVG this layer would actually render
        from the current parameters, so a stale entry is impossible by
        construction: if a parameter change alters the markup at all -- whether
        it is the layer's own field, a global one it falls back to, or a shared
        def it references -- the key changes and the layer is re-rendered.

        Keying on the layer id alone (with a hand-maintained list of which
        parameters invalidate which layers) is what let the optimiser score
        stale streak artwork while the blooms moved: the list and the builder
        had drifted apart.  Building the markup costs well under a millisecond
        against ~300 ms to rasterise it, so this is nearly free.

        Two entries per layer are kept, which is what an accept/reject cycle
        needs: a rejected trial restores the previous markup and finds it still
        cached.
        """
        svg = build_svg.build(params, basis=lid)
        key = hashlib.sha1(svg.encode("utf-8")).hexdigest()
        slots = self.cache.setdefault(lid, {})
        if key not in slots:
            if len(slots) >= 2:
                slots.pop(next(iter(slots)))
            slots[key] = FP.render_array(svg, self.size)[..., 0]
            self.n_render += 1
        return slots[key]

    def invalidate(self, affects):
        """Kept for the caller's benefit only -- correctness no longer needs it.

        Content-addressed caching (see `basis`) makes invalidation a memory
        hint rather than a correctness requirement, so this only drops slots
        that are certainly dead.
        """
        if affects == "all":
            self.cache.clear()

    def families(self, params, affects):
        """Layer indices worth re-fitting when `affects` changed.

        Re-fitting every layer for every trial move dominates the runtime, and
        holding all other layers fixed under-credits good moves (the glow
        layers trade amplitude with each other).  Re-fitting the changed
        layer's family -- the layers sharing its id prefix, i.e. the ones that
        actually overlap it -- is the useful middle ground.
        """
        if affects == "all":
            return None
        fams = {lid.split("_")[0] for lid in affects}
        return [i for i, L in enumerate(params["layers"]) if L["id"].split("_")[0] in fams] or None

    def evaluate(self, params, fit_iters=None, stride=None, full=False, free=None):
        A = np.stack([self.basis(params, L["id"]) for L in params["layers"]])
        st = 1 if full else (stride or self.stride)
        tgt = self.target_full[::st, ::st]
        Asub = A[:, ::st, ::st]
        W = FP.make_weight(tgt)
        if self.K is None or self.K.shape[0] != A.shape[0]:
            self.K = FP.params_wc(params)
        nf = FP.normal_flags(params)
        K = FP.fit(Asub, tgt, self.K, W, iters=fit_iters or self.fit_iters, verbose=False,
                   free=free, normal=nf)
        out = FP.composite(Asub, FP.colors(K), nf)
        sse = FP.weighted_sse(out - tgt, W) / (Asub.shape[1] * Asub.shape[2])
        mae = float(np.abs(out - tgt).mean() * 255)
        return sse, mae, K


def merge_specs(specs):
    """Collapse specs that search the SAME path, keeping the widest useful search.

    `layer_specs` and `field_specs` both emit a radial layer's `cx`/`cy`: the
    first with a +-40 px window at step 1.5, the second with +-260 at step 6.
    In an `all` sweep that searched eight paths twice over -- `field_mid`,
    `field_grad`, `corner_in` and `corner_in_top`, in both coordinates -- and
    the two passes could undo each other, because the second re-entered with a
    coarse step from wherever the first had left the value.

    They are not redundant in intent: one relocates, the other refines. So they
    are merged rather than one being dropped -- the union of the two windows
    with the finer step. That is only sufficient because the sweep's step
    schedule now actually refines downward (it did not before, see `sweep`), so
    a single spec starting coarse reaches the fine step by itself.
    """
    by_path = {}
    order = []
    for sp in specs:
        k = sp["path"]
        if k not in by_path:
            by_path[k] = dict(sp)
            order.append(k)
            continue
        cur = by_path[k]
        cur["lo"] = min(cur["lo"], sp["lo"])
        cur["hi"] = max(cur["hi"], sp["hi"])
        cur["step"] = min(cur["step"], sp["step"])
        if cur["affects"] != sp["affects"] and "all" in (cur["affects"], sp["affects"]):
            cur["affects"] = "all"
        elif cur["affects"] != sp["affects"]:
            cur["affects"] = sorted(set(cur["affects"]) | set(sp["affects"]))
    return [by_path[k] for k in order]


def sweep(obj, params, specs, log=print, accept_tol=2e-7):
    """One pass over `specs`, accepting a move only when the geometry is better.

    The baseline a trial is compared against must have been scored with the
    *same* colour freedom the trial gets, or the comparison is not between two
    geometries -- it is between two geometries plus an unmatched colour refit,
    and the refit's improvement gets attributed to the geometry.

    `evaluate(free=family)` re-fits that family's colours inside the trial.
    `best_sse`, though, is whatever the last accepted move left behind, and that
    move re-fitted a *different* family.  So an `arc_*` move would be accepted
    with the arc colours refit, and the next `flare_*` trial would be scored
    with a fresh flare refit against a baseline whose flare colours were still
    those of the pre-move geometry: the trial is handed a colour advantage the
    baseline never gets, and a flare geometry that is actually worse can win.

    The fix is to re-score the current, unchanged geometry under exactly the
    freedom the next family's trials will receive, whenever that freedom
    changes.  It costs a colour fit and no renders -- the basis is cached and
    the geometry has not moved -- and it makes every acceptance a comparison of
    two geometries under equivalent inner optimisation.
    """
    best_sse, best_mae, K = obj.evaluate(params)
    obj.K = K
    log("  start sse=%.6g mae=%.4f" % (best_sse, best_mae))
    improved = 0
    rebased = 0
    last_free = object()          # a sentinel no family signature can equal
    for sp in specs:
        free = obj.families(params, sp["affects"])
        sig = "all" if free is None else tuple(free)
        if sig != last_free:
            best_sse, best_mae, Kb = obj.evaluate(params, free=free)
            obj.K = Kb
            last_free = sig
            rebased += 1
        v0 = float(get_path(params, sp["path"]))
        # A search interval that does not contain the starting value silently
        # freezes the parameter: every proposal lands outside and is rejected
        # without ever being evaluated.  Widen instead, and say so.
        if not (sp["lo"] <= v0 <= sp["hi"]):
            log("  note: %s = %.4g lies outside [%.4g, %.4g]; widening to include it"
                % (sp["path"], v0, sp["lo"], sp["hi"]))
            pad = max(abs(v0) * 0.15, sp["step"] * 8, 1e-6)
            sp = dict(sp, lo=min(sp["lo"], v0 - pad), hi=max(sp["hi"], v0 + pad))
        step = sp["step"]
        tries = 0
        # Terminate on attempts and on the minimum step, NOT on "the last pass
        # moved".  The old `while moved` exited the moment a pass failed, so
        # the `step /= 2.2` below was dead code and the search never retried at
        # a smaller step: a parameter whose optimum sat between v0 and v0+step
        # -- v0 +- 1.0 both worse, v0 + 0.45 better -- was left where it
        # started, and 0.45 was never evaluated.  That is exactly the
        # resolution fine flare geometry needs.
        min_step = sp["step"] / 8.0
        while tries < 12 and step >= min_step:
            moved = False
            tries += 1
            for sgn in (+1, -1):
                v = v0 + sgn * step
                if not (sp["lo"] <= v <= sp["hi"]):
                    continue
                set_path(params, sp["path"], v)
                obj.invalidate(sp["affects"])
                sse, mae, Kt = obj.evaluate(params, free=free)
                if sse < best_sse - accept_tol:
                    best_sse, best_mae, v0, moved = sse, mae, v, True
                    obj.K = Kt
                    improved += 1
                    break
                set_path(params, sp["path"], v0)
                obj.invalidate(sp["affects"])
            if moved:
                step *= 1.6
            else:
                step /= 2.2
        set_path(params, sp["path"], v0)
        obj.invalidate(sp["affects"])
    log("  end   sse=%.6g mae=%.4f  (%d accepted moves, %d renders, %d colour re-baselines)"
        % (best_sse, best_mae, improved, obj.n_render, rebased))
    return best_sse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--spec", default="shapes",
                    choices=["shapes", "tapers", "geometry", "field", "all"])
    ap.add_argument("--sweeps", type=int, default=2)
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--fit-iters", type=int, default=3)
    ap.add_argument("--only", default=None,
                    help="restrict to specs touching layers whose id starts with this")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    params = json.load(open(a.params))
    obj = Objective(a.reference, stride=a.stride, fit_iters=a.fit_iters)
    builders = {"shapes": layer_specs, "tapers": taper_specs,
                "geometry": geometry_specs, "field": field_specs}
    if a.spec == "all":
        specs = merge_specs(sum((builders[k](params)
                                 for k in ("shapes", "tapers", "field", "geometry")), []))
    else:
        specs = builders[a.spec](params)
    if a.only:
        pre = tuple(x.strip() for x in a.only.split(","))
        specs = [sp for sp in specs
                 if sp["affects"] == "all"
                 or any(str(lid).startswith(pre) for lid in sp["affects"])]
    print("optimising %d parameters (%s%s), stride=%d"
          % (len(specs), a.spec, (" only " + a.only) if a.only else "", a.stride))
    t0 = time.time()
    for s in range(a.sweeps):
        print("sweep %d/%d" % (s + 1, a.sweeps))
        sweep(obj, params, specs)
    # final full-resolution colour fit
    sse, mae, K = obj.evaluate(params, fit_iters=12, full=True)
    FP.store_wc(params, K)
    print("final: sse=%.6g mae=%.4f  (%.1fs, %d renders)" % (sse, mae, time.time() - t0, obj.n_render))
    json.dump(params, open(a.out or a.params, "w"), indent=1)
    print("wrote", a.out or a.params)


if __name__ == "__main__":
    main()
