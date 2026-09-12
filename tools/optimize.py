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
                              "half_len", "height", "len", "peak_at", "cx", "cy")):
    """One spec per tunable shape number on each layer.

    Per-layer `bounds` in params.json win over the global defaults.  They are
    what keeps the layer stack meaningful: without them the search happily
    swaps a "near" glow and a "wide" glow, or collapses the core stroke into
    the halo, which costs nothing numerically but destroys the artwork's
    editability.
    """
    out = []
    for i, L in enumerate(params["layers"]):
        b = L.get("bounds", {})
        for k in keys:
            if k in L and isinstance(L[k], (int, float)):
                lo, hi, step = SHAPE_BOUNDS.get(k, (0.0, 2000.0, None))
                v = float(L[k])
                if k in ("cx", "cy"):
                    lo, hi, step = v - 40.0, v + 40.0, 1.5
                if k in b:
                    lo, hi = b[k]
                st = step if step is not None else max(0.02, abs(v) * 0.12)
                out.append({"path": "layers/%d/%s" % (i, k), "lo": lo, "hi": hi,
                            "step": st, "affects": [L["id"]]})
        if isinstance(L.get("profile"), dict):
            pk = "sigma" if "sigma" in L["profile"] else ("scale" if "scale" in L["profile"] else "n")
            if pk in L["profile"]:
                lo, hi = b.get("profile", (0.03, 4.0))
                out.append({"path": "layers/%d/profile/%s" % (i, pk), "lo": lo, "hi": hi,
                            "step": max(0.01, abs(float(L["profile"][pk])) * 0.12),
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
    return out


SHAPE_BOUNDS = {
    "half_len": (30.0, 500.0, None),
    "height": (2.0, 200.0, None),
    "len": (30.0, 400.0, None),
    "peak_at": (0.05, 0.8, 0.03),
    "width": (0.2, 900.0, None),
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
        out.append({"path": "flare/%s" % k, "lo": v - 30, "hi": v + 30, "step": st,
                    "affects": [L["id"] for L in params["layers"]
                                if L["kind"] in ("radial", "arc_lens")]})
    # The frame's four centre-lines are NOT searched either: they are fitted to
    # 371-461 cross-sections per edge with a standard deviation of 0.02-0.04 px,
    # which is far better than this objective can resolve -- and a raster
    # objective will happily trade 0.3 px of a measured edge position against a
    # photometric error somewhere else.  Only the corner shape is searched.
    for k, st, span in (("corner_r_main", 1.0, 8.0), ("corner_r_blend", 20.0, 300.0),
                        ("corner_blend_deg", 0.15, 2.5)):
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
    out = []
    for i, L in enumerate(params["layers"]):
        if L["kind"] in ("field_radial", "canvas") and "cx" in L:
            for k, st in (("cx", 6.0), ("cy", 6.0)):
                out.append({"path": "layers/%d/%s" % (i, k), "lo": 200, "hi": 820,
                            "step": st, "affects": [L["id"]]})
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
        if lid not in self.cache:
            self.cache[lid] = FP.render_array(build_svg.build(params, basis=lid), self.size)[..., 0]
            self.n_render += 1
        return self.cache[lid]

    def invalidate(self, affects):
        if affects == "all":
            self.cache.clear()
        else:
            for lid in affects:
                self.cache.pop(lid, None)

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
        sse = float((((out - tgt) * W[..., None]) ** 2).sum()) / (Asub.shape[1] * Asub.shape[2])
        mae = float(np.abs(out - tgt).mean() * 255)
        return sse, mae, K


def sweep(obj, params, specs, log=print, accept_tol=2e-7):
    best_sse, best_mae, K = obj.evaluate(params)
    obj.K = K
    log("  start sse=%.6g mae=%.4f" % (best_sse, best_mae))
    improved = 0
    for sp in specs:
        v0 = float(get_path(params, sp["path"]))
        step = sp["step"]
        moved = True
        tries = 0
        while moved and tries < 6:
            moved = False
            tries += 1
            for sgn in (+1, -1):
                v = v0 + sgn * step
                if not (sp["lo"] <= v <= sp["hi"]):
                    continue
                set_path(params, sp["path"], v)
                obj.invalidate(sp["affects"])
                sse, mae, Kt = obj.evaluate(params, free=obj.families(params, sp["affects"]))
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
                if step < sp["step"] / 8.0:
                    break
        set_path(params, sp["path"], v0)
        obj.invalidate(sp["affects"])
    log("  end   sse=%.6g mae=%.4f  (%d accepted moves, %d renders)"
        % (best_sse, best_mae, improved, obj.n_render))
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
        specs = sum((builders[k](params) for k in ("shapes", "tapers", "field", "geometry")), [])
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
