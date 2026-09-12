#!/usr/bin/env python3
"""Fit every layer's light amount analytically against reference.png.

Two measured facts make this cheap and well-posed:

1.  The reconstruction composites with `screen` over black, so the render is
    a closed form in the layer coverages (see src/build_svg.py):

        out = 1 - prod_i (1 - A_i * k_i)

    `A_i` is layer i's coverage field -- anti-aliasing x blur x gradient alpha
    -- which depends only on that layer's *shape*.  Render each layer once in
    white and every layer's colour can be fitted without re-rendering.

2.  All of the light in the reference lies in a two-dimensional colour space.
    A PCA of 300 000 interior pixels' colour directions gives eigenvalues
    0.981 / 0.012 / 0.007, and the best two-basis decomposition is
    white + cyan(0, 0.94, 1.00) with a mean absolute error of 0.63/255.
    So each layer carries just two numbers: how much white and how much cyan.
    That halves the free parameters, keeps every fitted colour physically
    plausible (no green or magenta glow appearing to patch a shape error), and
    matches the reference's own structure -- one white-hot core plus one cyan
    emission.

    d out_ch / d w_i = A_i * WHITE_ch * (1 - out_ch) / (1 - A_i k_i,ch)
    d out_ch / d c_i = A_i * CYAN_ch  * (1 - out_ch) / (1 - A_i k_i,ch)

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
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import build_svg  # noqa: E402

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
        K = np.clip(WC @ B, 0.0, 1.0).astype(np.float32)
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
        return out, before, suf

    def sse(WC):
        out, _, _ = forward(WC)
        return float((((out - Tf) * Wf[:, None]) ** 2).sum())

    cur = sse(WC)
    for it in range(iters):
        out, before, suf = forward(WC)
        r = ((out - Tf) * Wf[:, None]).reshape(-1)
        cols = []
        for i in idx:
            g = Af[i][:, None] * suf[i]
            if not isnorm[i]:
                g = g * (1.0 - before[i])
            for bi in range(NB):
                cols.append((g * B[bi][None, :] * Wf[:, None]).reshape(-1))
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
            out, _, _ = forward(WC)
            print("  iter %d  mae=%.4f  weighted_sse=%.6g  lam=%.3g"
                  % (it, float(np.abs(out - Tf).mean() * 255), cur, lam))
        if not accepted:
            break
    return WC.astype(np.float32)


def make_weight(target, mode="gamma", floor=0.02):
    if mode == "flat":
        return np.ones(target.shape[:2], np.float32)
    lum = target.mean(2)
    w = (lum + floor) ** (1.0 / 2.2 - 1.0)
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
    ap.add_argument("--stride", type=int, default=2)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()

    params = json.load(open(a.params))
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float32) / 255.0
    target = np.minimum(ref, 254.4 / 255.0)
    A, names = basis_stack(params)
    st = max(1, a.stride)
    tsub, Asub = target[::st, ::st], A[:, ::st, ::st]
    W = make_weight(tsub, a.weight)
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
