#!/usr/bin/env python3
"""Isolate one group of layers' required contribution from the reference.

Work in `u = 1 - out`.  There, a screen layer is a MULTIPLICATION and a normal
layer is an AFFINE map:

    screen:  out <- out*(1 - A*C) + A*C      =>   u <- (1 - A*C) * u
    normal:  out <- out*(1 - A)   + A*C      =>   u <- (1 - A) * u + A*(1 - C)

Screen layers therefore commute with each other and a dropped group of them is
a single factor `(1 - f)`; normal layers do not commute with anything.  The
stack here ends with two normal-blended frame layers, so the naive formula

    f = (ref - M) / (1 - M)

is only correct where those layers have zero coverage.  Wherever the frame
stroke and its blur skirt reach, `ref` and `M` have both been put through the
frame's affine map, and dividing them as if they had not distorts the isolated
contribution -- which matters precisely for the arc-glow layers that run up to
the rim.

So the layers after the dropped group are composed into one affine map `(p, q)`
in `u` and inverted before the screen formula is applied:

    u_ref = p * (u_pre * (1 - f)) + q
    =>  f = 1 - ((u_ref - q) / p) / u_pre

where `u_pre` is the kept stack up to the dropped group's position.  With no
normal layer after the group this reduces to `(ref - M)/(1 - M)` exactly, so
the screen-only case is unchanged.  Orderings the algebra cannot express -- a
dropped layer that is itself normal-blended, or a kept normal layer sitting
between two dropped ones -- are REJECTED rather than approximated.

`f` is the isolated group, expressed in the very units its layers use.  That
makes it directly measurable: the flare's own profile, position and rays,
without the curve glow and background mixed in.

    python3 tools/isolate.py --drop flare          -> out/isolated_flare.npy + preview
    python3 tools/isolate.py --drop arc_glow,field --region left
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import fit_photometry as FP  # noqa: E402


class UnsupportedIsolation(ValueError):
    """The requested drop cannot be expressed as a single factor in `u`."""


def _affine_u(A, K, normal, order):
    """Compose the layers in `order` into one affine map on u = 1 - out.

    Returns (p, q) with `u_out = p * u_in + q`.  A screen layer contributes
    (1 - A*C) with no offset; a normal layer contributes (1 - A) with offset
    A*(1 - C).  Both are affine, so the composition is affine and exact.
    """
    H, W = A.shape[1], A.shape[2]
    p = np.ones((H, W, 3), np.float32)
    q = np.zeros((H, W, 3), np.float32)
    for i in order:
        a = A[i][..., None]
        c = K[i][None, None, :]
        if normal[i]:
            m = 1.0 - a
            off = a * (1.0 - c)
        else:
            m = 1.0 - a * c
            off = 0.0
        p = m * p
        q = m * q + off
    return p, q


def isolate(params, ref, drop_prefixes, refit_mask=None, iters=25):
    """Contribution the dropped layers must supply, and the base without them.

    `refit_mask` (True where the fit should look) re-fits the surviving layers
    before isolating.  That matters: the surviving layers were fitted with the
    dropped ones present, so they have already absorbed some of the light that
    belongs to the dropped group.  Isolating against that base attributes the
    absorbed part to the wrong source -- which is how a broad deficit left of
    the flare first read as a bright leftward "ray".  Re-fitting the base on a
    region the dropped group barely reaches breaks that circularity.
    """
    layers = params["layers"]
    dropped = [i for i, q in enumerate(layers)
               if any(q["id"].startswith(pre) for pre in drop_prefixes)]
    if not dropped:
        raise UnsupportedIsolation("nothing matches %s" % (drop_prefixes,))
    all_nf = FP.normal_flags(params)
    bad = [layers[i]["id"] for i in dropped if all_nf[i]]
    if bad:
        raise UnsupportedIsolation(
            "cannot isolate normal-blended layers %s: a normal layer is an affine "
            "step, not a factor, so the dropped group is not a single (1 - f)" % bad)
    lo, hi = min(dropped), max(dropped)
    between = [layers[i]["id"] for i in range(lo + 1, hi)
               if i not in dropped and all_nf[i]]
    if between:
        raise UnsupportedIsolation(
            "kept normal-blended layer(s) %s sit between the dropped layers; the "
            "dropped group cannot be gathered into one factor across them" % between)

    keep_idx = [i for i in range(len(layers)) if i not in set(dropped)]
    keep = [layers[i] for i in keep_idx]
    base = dict(params, layers=keep)
    A, _ = FP.basis_stack(base)
    nf = FP.normal_flags(base)
    if refit_mask is not None:
        w = FP.make_weight(ref) * refit_mask.astype(np.float32)
        WC = FP.fit(A, ref, FP.params_wc(base), w, iters=iters, verbose=False, normal=nf,
                    teal_ok=FP.teal_eligible(base))
        base = json.loads(json.dumps(base))
        FP.store_wc(base, WC)
    K = FP.colors(FP.params_wc(base))
    M = FP.composite(A, K, nf)

    # Split the kept stack at the dropped group's position and invert whatever
    # the layers after it do.  With only screen layers after, (p, q) = (1, 0)
    # and this is exactly the old formula.
    pre = [j for j, i in enumerate(keep_idx) if i < lo]
    post = [j for j, i in enumerate(keep_idx) if i > lo]
    p_pre, q_pre = _affine_u(A, K, nf, pre)
    u_pre = p_pre + q_pre                      # u starts at 1 over black
    p_post, q_post = _affine_u(A, K, nf, post)
    u_ref = 1.0 - ref
    u_mid = (u_ref - q_post) / np.where(np.abs(p_post) < 1e-6, 1e-6, p_post)
    f = 1.0 - u_mid / np.maximum(u_pre, 1e-4)
    return np.clip(f, 0.0, 1.0), M, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--drop", default="flare")
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "isolated"))
    ap.add_argument("--refit-outside", type=float, default=0.0,
                    help="re-fit the surviving layers ignoring a disc of this radius "
                         "around --centre before isolating")
    ap.add_argument("--centre", default="530.95,513.33")
    a = ap.parse_args()
    params = json.load(open(a.params))
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float32) / 255.0
    ref = np.minimum(ref, 254.4 / 255.0)
    pref = [x.strip() for x in a.drop.split(",")]
    mask = None
    if a.refit_outside > 0:
        cx, cy = [float(q) for q in a.centre.split(",")]
        yy, xx = np.mgrid[0:1024, 0:1024]
        mask = np.hypot(xx - cx, yy - cy) > a.refit_outside
    f, M, base = isolate(params, ref, pref, mask)
    json.dump(base, open(a.out + "_" + pref[0] + "_base.json", "w"), indent=1)
    np.save(a.out + "_" + pref[0] + ".npy", f.astype(np.float32))
    Image.fromarray(np.clip(f * 255, 0, 255).astype(np.uint8)).save(a.out + "_" + pref[0] + ".png")
    print("dropped %s; isolated max=%s mean=%.5f -> %s"
          % (pref, np.round(f.max(axis=(0, 1)) * 255, 1), f.mean() * 255, a.out + "_" + pref[0] + ".npy"))


if __name__ == "__main__":
    sys.exit(main())
