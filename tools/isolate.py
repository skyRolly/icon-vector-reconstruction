#!/usr/bin/env python3
"""Isolate one group of layers' required contribution from the reference.

Screen compositing is commutative, so the render is
`out = 1 - prod_i (1 - A_i k_i)` regardless of paint order.  Drop a group of
layers, composite the rest into a base `M`, and the contribution the dropped
group must supply is recoverable exactly:

    ref = M + f*(1 - M)   =>   f = (ref - M) / (1 - M)

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
    keep = [q for q in params["layers"] if not any(q["id"].startswith(p) for p in drop_prefixes)]
    base = dict(params, layers=keep)
    A, _ = FP.basis_stack(base)
    nf = FP.normal_flags(base)
    if refit_mask is not None:
        w = FP.make_weight(ref) * refit_mask.astype(np.float32)
        WC = FP.fit(A, ref, FP.params_wc(base), w, iters=iters, verbose=False, normal=nf)
        base = json.loads(json.dumps(base))
        FP.store_wc(base, WC)
    M = FP.composite(A, FP.colors(FP.params_wc(base)), nf)
    f = (ref - M) / np.maximum(1.0 - M, 1e-4)
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
