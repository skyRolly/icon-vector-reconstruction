#!/usr/bin/env python3
"""Fit every layer's light amount analytically against reference.png.

Two measured facts make this cheap and well-posed:

1.  The reconstruction composites with `screen` over black, so the render is
    a closed form in the layer coverages (see src/build_svg.py):

        out = 1 - prod_i (1 - A_i * k_i)

    `A_i` is layer i's coverage field -- anti-aliasing x blur x gradient alpha
    -- which depends only on that layer's *shape*.  Render each layer once in
    white and every layer's colour can be fitted without re-rendering.

2.  All of the light in the reference lies in a narrow non-negative colour
    cone.  A PCA of the interior pixels' colour directions gives eigenvalues
    0.981 / 0.012 / 0.007, so it is nearly two-dimensional -- but "nearly" is
    not "is", and the third dimension is where the whole dark background lives.
    Each layer therefore carries three non-negative amounts, of

        WHITE(1, 1, 1)   CYAN(0, 0.94, 1)   BLUE(0, 0, 1)

    (see the comment above BASIS for the measurements, and docs/METHOD.md
    section 6).  The point of the cone rather than free RGB is that its
    non-negative span is exactly R <= G <= B, the family the reference uses
    everywhere, so a shape error cannot be hidden by inventing a green or
    magenta glow -- which is what free-RGB fitting did.

        d out_ch / d a_i,j = A_i * BASIS_j,ch * (1 - out_ch) / (1 - A_i k_i,ch)

Geometry (positions, widths, blur radii, taper shape) changes `A_i` and is
handled by tools/optimize.py.

Usage:
    python3 tools/fit_photometry.py                 # updates src/params.json
    python3 tools/fit_photometry.py --no-write --iters 10
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_svg  # noqa: E402
import regions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Measured colour basis.  See docs/METHOD.md section 6: a PCA of 300 000
# interior pixels' colour directions gives eigenvalues 0.981 / 0.012 / 0.007,
# so the light is essentially white + one cyan emission; a third, pure-blue
# component is needed only for the very dark background (the dim interior sits
# at G/B ~ 0.66 and the exterior at ~0.3, both bluer than the cyan).  With all
# three, an exact non-negative fit of every interior pixel has a mean error of
# 0.012/255 -- i.e. the basis is exact -- against 1.85/255 for white+cyan.
#
# The cone spanned by these three with non-negative amounts is exactly
# R <= G <= B, which is the family the reference actually uses.  That is the
# point of fitting in this basis rather than in free RGB: a shape error can no
# longer be hidden by inventing a green or magenta glow layer, which is what
# free-RGB fitting did.
WHITE = np.array([1.0, 1.0, 1.0], np.float32)
CYAN = np.array([0.0, 0.94, 1.0], np.float32)
BLUE = np.array([0.0, 0.0, 1.0], np.float32)
BASIS = np.stack([WHITE, CYAN, BLUE])    # (3, 3)
NB = BASIS.shape[0]
COMPONENTS = ("white", "cyan", "blue")


def render_array(svg_text: str, size: int = 1024) -> np.ndarray:
    import resvg_py

    out = resvg_py.svg_to_bytes(svg_string=svg_text, width=size, height=size)
    b = bytes(out) if not isinstance(out, (bytes, bytearray)) else out
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).astype(np.float32) / 255.0


def basis_stack(params, size=1024, cache=None):
    out, names = [], []
    for L in params["layers"]:
        if cache is not None and L["id"] in cache:
            out.append(cache[L["id"]])
        else:
            a = render_array(build_svg.build(params, basis=L["id"]), size)[..., 0]
            if cache is not None:
                cache[L["id"]] = a
            out.append(a)
        names.append(L["id"])
    return np.stack(out), names


def wc_from_color(color):
    """Exact non-negative basis amounts for an sRGB 0..255 colour.

    Three basis vectors, so the active-set enumeration is only seven cases.
    """
    import itertools

    k = np.asarray(color, np.float64) / 255.0
    B = BASIS.T.astype(np.float64)
    best = None
    for r in range(1, NB + 1):
        for comb in itertools.combinations(range(NB), r):
            sol, *_ = np.linalg.lstsq(B[:, comb], k, rcond=None)
            if (sol < -1e-9).any():
                continue
            full = np.zeros(NB)
            full[list(comb)] = sol
            e = float(np.abs(B @ full - k).sum())
            if best is None or e < best[0]:
                best = (e, full)
    if best is None:
        return np.clip(np.linalg.lstsq(B, k, rcond=None)[0], 0.0, None)
    return best[1]


def color_from_wc(wc):
    return np.clip(np.asarray(wc, np.float64) @ BASIS.astype(np.float64), 0.0, 1.0)


def colors(WC):
    """(n,2) white/cyan amounts -> (n,3) premultiplied colours in 0..1."""
    return np.clip(WC @ BASIS, 0.0, 1.0)


def composite(A, K, normal=None):
    """Composite the layer stack exactly as the renderer does.

    Each layer is an affine step on the accumulated colour:

        screen:  out <- out * (1 - A*C) + A*C
        normal:  out <- out * (1 - A)   + A*C

    `normal` is a boolean per layer (default: all screen).  The frame rim is
    composited `normal` because it is an opaque stroke -- screening it over the
    interior field would brighten it by several code values.
    """
    n, H, W = A.shape
    out = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        a = A[i][..., None]
        b = a * K[i][None, None, :]
        m = (1.0 - a) if (normal is not None and normal[i]) else (1.0 - b)
        out = out * m + b
    return out


def weighted_sse(residual, weight):
    """The objective, in one place: sum over pixels and channels of (r*w)^2.

    `fit`, `optimize.Objective.evaluate` and the regression check all go
    through this, so a weight convention can no longer mean one thing in the
    optimiser and another in the test that is supposed to police it.
    """
    r = np.asarray(residual, np.float32)
    w = np.asarray(weight, np.float32)
    if r.ndim == w.ndim + 1:
        w = w[..., None]
    return float(((r * w) ** 2).sum())


def analytic_grad(A, target, WC, weight, normal, layer, comp):
    """d(weighted_sse)/d(WC[layer, comp]) the way `fit` computes it.

    Exported so the regression check differentiates the production Jacobian
    rather than a re-derivation of it.
    """
    n = A.shape[0]
    Af = A.reshape(n, -1).astype(np.float32)
    Tf = target.reshape(-1, 3).astype(np.float32)
    Wf = np.asarray(weight, np.float32).reshape(-1)
    B = BASIS.astype(np.float32)
    isnorm = [bool(normal[i]) if normal is not None else False for i in range(n)]
    Kraw = np.asarray(WC, np.float64) @ B
    K = np.clip(Kraw, 0.0, 1.0).astype(np.float32)
    live = ((Kraw > 0.0) & (Kraw < 1.0)).astype(np.float32)
    P = Af.shape[1]
    out = np.zeros((P, 3), np.float32)
    before = np.empty((n, P, 3), np.float32)
    ms = np.empty((n, P, 3), np.float32)
    for i in range(n):
        before[i] = out
        a = Af[i][:, None]
        b = a * K[i][None, :]
        ms[i] = (1.0 - a) if isnorm[i] else (1.0 - b)
        out = out * ms[i] + b
    suf = np.empty((n, P, 3), np.float32)
    acc = np.ones((P, 3), np.float32)
    for i in range(n - 1, -1, -1):
        suf[i] = acc
        acc = acc * ms[i]
    g = Af[layer][:, None] * suf[layer]
    if not isnorm[layer]:
        g = g * (1.0 - before[layer])
    col = g * (B[comp] * live[layer])[None, :] * Wf[:, None]
    r = (out - Tf) * Wf[:, None]
    return float(2.0 * (col * r).sum())


def fit(A, target, WC0, weight, iters=14, lam=0.1, verbose=True, hi=1.0, free=None,
        normal=None):
    """Levenberg-Marquardt on the per-layer basis amounts.

    The composite is affine in the accumulated colour at every layer (see
    `composite`), so both the value and the exact derivative with respect to any
    layer's colour come from one forward pass:

        out = sum_j b_j * prod_{k>j} m_k
        d out / d C_j = A_j * prod_{k>j} m_k * (1 - out_before_j)   (screen)
        d out / d C_j = A_j * prod_{k>j} m_k                        (normal)

    The layer bases are deliberately overlapping (a glow is the sum of several
    blurred strokes), so J^T J is strongly ill-conditioned and undamped
    Gauss-Newton overshoots in every trial step; adaptive LM damping converges
    reliably from any start.
    """
    n = A.shape[0]
    idx = list(range(n)) if free is None else list(free)
    isnorm = [bool(normal[i]) if normal is not None else False for i in range(n)]
    WC = np.array(WC0, np.float64).copy()
    Af = A.reshape(n, -1).astype(np.float32)
    Tf = target.reshape(-1, 3).astype(np.float32)
    Wf = weight.reshape(-1).astype(np.float32)
    B = BASIS.astype(np.float32)

    def forward(WC):
        Kraw = WC @ B
        K = np.clip(Kraw, 0.0, 1.0).astype(np.float32)
        # Where a channel's colour is clipped, that channel contributes no
        # derivative: d K_ch / d a_j is zero there, not BASIS[j, ch].  Ignoring
        # the clip made the analytic gradient of a saturated layer 1.6x too
        # large (measured on arc_core, whose unclipped blue channel is 1.0014),
        # which LM's line search absorbs but which is still a wrong Jacobian.
        live = ((Kraw > 0.0) & (Kraw < 1.0)).astype(np.float32)
        P = Af.shape[1]
        before = np.empty((n, P, 3), np.float32)
        out = np.zeros((P, 3), np.float32)
        ms = np.empty((n, P, 3), np.float32)
        for i in range(n):
            before[i] = out
            a = Af[i][:, None]
            b = a * K[i][None, :]
            ms[i] = (1.0 - a) if isnorm[i] else (1.0 - b)
            out = out * ms[i] + b
        # suffix products of m
        suf = np.empty((n, P, 3), np.float32)
        acc = np.ones((P, 3), np.float32)
        for i in range(n - 1, -1, -1):
            suf[i] = acc
            acc = acc * ms[i]
        return out, before, suf, live

    def sse(WC):
        out, _, _, _ = forward(WC)
        return weighted_sse(out - Tf, Wf)

    cur = sse(WC)
    for it in range(iters):
        out, before, suf, live = forward(WC)
        r = ((out - Tf) * Wf[:, None]).reshape(-1)
        cols = []
        for i in idx:
            g = Af[i][:, None] * suf[i]
            if not isnorm[i]:
                g = g * (1.0 - before[i])
            for bi in range(NB):
                cols.append((g * (B[bi] * live[i])[None, :] * Wf[:, None]).reshape(-1))
        J = np.stack(cols, 1)
        G = J.T @ J
        g2 = J.T @ r
        m = len(idx)
        diag = np.trace(G) / (NB * m)
        accepted = False
        for _ in range(9):
            Gd = G + (lam * diag + 1e-12) * np.eye(NB * m)
            try:
                d = -np.linalg.solve(Gd, g2)
            except np.linalg.LinAlgError:
                d = -np.linalg.lstsq(Gd, g2, rcond=None)[0]
            for step in (1.0, 0.4, 0.15, 0.05):
                cand = WC.copy()
                cand[idx] = np.clip(WC[idx] + step * d.reshape(m, NB), 0.0, hi)
                e = sse(cand)
                if e < cur - 1e-12:
                    WC, cur, accepted = cand, e, True
                    lam = max(lam / 3.0, 1e-6)
                    break
            if accepted:
                break
            lam *= 6.0
        if verbose:
            out, _, _, _ = forward(WC)
            print("  iter %d  mae=%.4f  weighted_sse=%.6g  lam=%.3g"
                  % (it, float(np.abs(out - Tf).mean() * 255), cur, lam))
        if not accepted:
            break
    return WC.astype(np.float32)


#: Regions a whole-image objective cannot police, and how much to lift them.
#: The gamma weight below is ~5x smaller on a bright centre pixel than on the
#: dark background, and the centre is only 5% of the canvas, so without this
#: the fit will trade a visibly wrong flare for a fraction of a code value
#: spread over the background -- which is exactly what it did.
EMPHASIS = {
    #: All three `weight`s are **objective** weights -- multipliers on squared
    #: error -- and `make_weight` applies their square roots to residuals.
    "flare": {"centre": regions.FLARE_CORE, "radius": 130.0, "weight": 5.0},
    #: The two lobes, full interior height.  The old boxes stopped at y=200 and
    #: y=850, which left the four interior corners -- where the reconstruction
    #: was 30% too dark over 67 000 px -- with no emphasis at all.
    "lobes": {"boxes": [(100, 55, 460, 985), (568, 55, 930, 985)], "weight": 1.6},
    #: The glow's cross-section, cell by cell: every (signed distance x
    #: along-curve band) cell gets the same influence, shaped by its own mean
    #: brightness.  Without it the fit sees the glow's shape only through
    #: absolute code values, so a 19% deficit 45 px inside the curves (2.2
    #: counts) is worth less than a 2% error on the frame -- and the asymmetry
    #: between the two sides of each curve, which is what the eye reads as the
    #: shape of the light, goes unfitted.  Cells rather than distance-only
    #: bins: pooling along the curve hid the tips completely, and the fit then
    #: drained them to 20-30% below the reference.  The set also carries the
    #: four interior corners, which lie past the curve ends and so have no
    #: profile cell of their own.
    #: `floor` sets where the shaping sits between equal *relative* error in
    #: every bin (floor 0, Weber's law) and equal *absolute* error (large
    #: floor).  Weber's law fails near black -- a 15% error on the 7.5-count
    #: outermost bin is about one code value, and invisible, while 15% on the
    #: 42-count innermost bin is six -- so the floor is a visibility threshold,
    #: 1.53 code values (0.006, about the quantisation scale -- chosen by
    #: measurement, see docs/DECISIONS.md D20).  Measured with the production
    #: formula over the 222 cells, a uniform 1% relative error then costs
    #: 4.57x more in the worst cell than the best, against 51.23x with the
    #: display curve alone and no cell shaping.
    #: `exponent` is how hard the shaping leans on the dim cells; see
    #: `profile_multiplier`.  1.0 is equal relative error per cell.
    "profile": {"weight": 2.2, "floor": 0.006, "exponent": 1.0},
    #: The flare's own cells - radius x sector, plus the streak comb.  A bigger
    #: floor than the profile's: the flare spans 15 to 255 code values, and
    #: pure relative equalisation there would make the clipped core worth a
    #: two-hundredth of a 15-count cell, when the core is a stated priority.
    #: 0.08 (20 counts) equalises the dim structure and still weighs the core.
    "flare_cells": {"weight": 3.0, "floor": 0.08},
}

#: Caches keyed by image shape (and, for the profile term, by a cheap
#: fingerprint of the target).  `Objective.evaluate` rebuilds the weight on
#: every trial evaluation, and the distance fields and per-bin means behind it
#: cost more than the fit step they feed.
_PROFILE_BINS = {}
_PROFILE_CACHE = {}
_MASK_CACHE = {}


def region_masks(shape):
    key = tuple(shape[:2])
    if key not in _MASK_CACHE:
        _MASK_CACHE[key] = _region_masks(shape)
    return _MASK_CACHE[key]


def _region_masks(shape):
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    sx, sy = w / 1024.0, h / 1024.0
    fl = EMPHASIS["flare"]
    out = {"flare": np.hypot(xx - fl["centre"][0] * sx, yy - fl["centre"][1] * sy)
           < fl["radius"] * sx}
    lob = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in EMPHASIS["lobes"]["boxes"]:
        lob[int(y0 * sy):int(y1 * sy), int(x0 * sx):int(x1 * sx)] = True
    out["lobes"] = lob & ~out["flare"]
    return out


def profile_multiplier(target):
    """Per-pixel *residual* multiplier that equalises the weight cells.

    Two steps, and conflating them is a bug this code has already had.

    The objective coefficient wanted for a cell of `n` pixels at mean
    luminance `L` is `1 / (n * (L + floor)^2)`: the objective is a weighted sum
    of squares, so a cell with relative error `r` contributes
    `(coefficient) * n * (r*L)^2`, and equalising that across cells needs
    `1/L^2`, not `1/L`.

    But `fit()` multiplies *residuals* by what `make_weight` returns and
    squares the product, so what must be returned is the square root of that
    coefficient, `1 / (sqrt(n) * (L + floor))`.  Returning the coefficient
    itself squares it again: the cost of a 1% relative error then goes as
    `1/(n^2 (L+floor)^4)` and varied 183x across the cells instead of 2.3x,
    which is not a tuning detail -- it silently made the darkest cells worth
    two orders of magnitude more than the brightest.

    How hard the shaping leans on the dim cells is the `exponent` p: the
    coefficient is `1 / (n * (L + floor)^(2p))`, so p = 1 equalises relative
    error across cells (Weber) and larger p pushes past it, buying accuracy in
    the dim far lobe at the cost of the bright cells and of the rest of the
    image.  It is a parameter and not a constant because measurement, not
    principle, picks it: p = 1 is the defensible default, and the value shipped
    is whichever one measurably reconstructs the reference best (see
    docs/DECISIONS.md).  The exponent exists at all because the squared-weight
    bug above was silently applying p = 2 together with 1/n^2, and when it was
    corrected to p = 1 the lobe interior got *worse* -- so the strength of the
    shaping had been doing real work by accident and now has to be chosen on
    purpose.

    Normalised to mean 1 over the covered pixels, so the region's overall share
    is unchanged by the shaping and is then lifted by
    `EMPHASIS["profile"]["weight"]` (an objective weight; see `make_weight`).
    """
    shape = tuple(target.shape[:2])
    lum = target.mean(2)
    fl_floor = EMPHASIS["flare_cells"]["floor"]
    fl_w = math.sqrt(EMPHASIS["flare_cells"]["weight"] / EMPHASIS["profile"]["weight"])
    fl = EMPHASIS["profile"]["floor"]
    pp = float(EMPHASIS["profile"].get("exponent", 1.0))
    fl_p = float(EMPHASIS["flare_cells"].get("exponent", 1.0))
    # The shaping parameters belong in the cache key: without them, changing the
    # floor or the exponent inside one process silently returns the multiplier
    # built for the previous setting.
    key = (shape, float(lum.sum()), fl, fl_floor, fl_w, pp, fl_p)
    if key in _PROFILE_CACHE:
        return _PROFILE_CACHE[key]
    if shape not in _PROFILE_BINS:
        _PROFILE_BINS[shape] = regions.weight_cells(shape)
    bins = _PROFILE_BINS[shape]
    m = np.zeros(shape, np.float32)
    cov = np.zeros(shape, bool)
    for cell in bins:
        mask = cell[-1]
        n = int(mask.sum())
        if not n:
            continue
        isflare = isinstance(cell[0], str)
        f0 = fl_floor if isflare else fl
        k = fl_w if isflare else 1.0
        # sqrt of the objective coefficient 1/(n*(L+floor)^(2p)); see the docstring
        pw = fl_p if isflare else pp
        m[mask] = k / (math.sqrt(n) * (float(lum[mask].mean()) + f0) ** pw)
        cov |= mask
    if cov.any():
        m[cov] /= m[cov].mean()
    _PROFILE_CACHE[key] = (m, cov)
    return m, cov


def make_weight(target, mode="gamma", floor=0.02, emphasis=True):
    """Per-pixel **residual multiplier** for the fit.

    This returns the factor that multiplies a residual, not an objective
    coefficient: `fit()` forms `(out - target) * w` and squares it, so the
    objective coefficient is `w**2`.  Everything below is expressed in that
    convention, and `EMPHASIS`'s numbers are objective weights, applied here as
    their square roots.

    Why a residual multiplier is the right convention: the `gamma` term is the
    derivative of the display curve, `d(L^(1/2.2))/dL = L^(1/2.2-1)/2.2`, so
    `residual * L^(1/2.2-1)` *is* the error in perceptual units and squaring it
    is what a least-squares objective should do.  Treating that term as an
    objective coefficient instead would make it `L^(1/2.2-1)` per unit squared
    error, i.e. the wrong power, so the convention is fixed by this term.

    `emphasis` then lifts the regions that are visually decisive but
    numerically tiny: the flare, the lobes, and every cell of the curves'
    cross-section (see `profile_multiplier`).
    """
    if mode == "flat":
        w = np.ones(target.shape[:2], np.float32)
    else:
        lum = target.mean(2)
        w = ((lum + floor) ** (1.0 / 2.2 - 1.0)).astype(np.float32)
    if emphasis:
        masks = region_masks(target.shape)
        w = w.copy()
        w[masks["flare"]] *= math.sqrt(EMPHASIS["flare"]["weight"])
        w[masks["lobes"]] *= math.sqrt(EMPHASIS["lobes"]["weight"])
        mult, cov = profile_multiplier(target)
        if cov.any():
            # Replace rather than multiply inside the covered region: the point
            # is that every cell of the cross-section costs the same for the
            # same relative error, and multiplying by a brightness-dependent
            # base weight puts that back out of balance.  The region's overall
            # share is preserved and then lifted.
            w[cov] = (math.sqrt(EMPHASIS["profile"]["weight"]) * float(w[cov].mean())
                      * mult[cov]).astype(np.float32)
    return (w / w.mean()).astype(np.float32)


def normal_flags(params):
    return [L.get("blend", "screen") == "normal" for L in params["layers"]]


def params_wc(params):
    return np.array([wc_from_color(L.get("color", [128, 128, 128])) for L in params["layers"]], np.float32)


def store_wc(params, WC):
    for L, wc in zip(params["layers"], WC):
        for name, v in zip(COMPONENTS, wc):
            L[name] = round(float(v), 5)
        L["color"] = [round(float(v) * 255.0, 2) for v in color_from_wc(wc)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--iters", type=int, default=12)
    ap.add_argument("--weight", default="gamma", choices=["gamma", "flat"])
    ap.add_argument("--no-emphasis", action="store_true",
                    help="fit without lifting the flare and lobe regions")
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()

    params = json.load(open(a.params))
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float32) / 255.0
    target = np.minimum(ref, 254.4 / 255.0)
    A, names = basis_stack(params)
    st = max(1, a.stride)
    tsub, Asub = target[::st, ::st], A[:, ::st, ::st]
    W = make_weight(tsub, a.weight, emphasis=not a.no_emphasis)
    print("fitting %d layers x %s  [stride %d]" % (len(names), str(COMPONENTS), st))
    nf = normal_flags(params)
    WC = fit(Asub, tsub, params_wc(params), W, iters=a.iters, normal=nf)
    store_wc(params, WC)
    out = composite(A, colors(WC), nf)
    print("analytic composite mae=%.4f" % (np.abs(out - target).mean() * 255))
    for L in params["layers"]:
        print("  %-18s %s -> rgb%s"
              % (L["id"], " ".join("%s=%7.4f" % (c, L[c]) for c in COMPONENTS), L["color"]))
    if not a.no_write:
        json.dump(params, open(a.params, "w"), indent=1)
        print("updated", a.params)


if __name__ == "__main__":
    main()
