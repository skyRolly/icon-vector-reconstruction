#!/usr/bin/env python3
"""Drop layers that do not earn their place.

The layer stack is deliberately over-complete while fitting: several glow terms
overlap, so the search can trade between them.  That is good for fidelity and
bad for the deliverable, which should contain no element a reader cannot
account for.  This tool re-fits without each layer in turn and reports the cost
of removing it; with --apply it removes the ones whose cost is below a
threshold, cheapest first, re-fitting after each removal.

    python3 tools/prune_layers.py                       # report only
    python3 tools/prune_layers.py --apply --max-cost 0.01
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import build_svg  # noqa: E402
import fit_photometry as FP  # noqa: E402


def evaluate(params, ref, stride=2, iters=14, cache=None):
    A, _ = FP.basis_stack(params, cache=cache)
    tgt = ref[::stride, ::stride]
    Asub = A[:, ::stride, ::stride]
    W = FP.make_weight(tgt)
    nf = FP.normal_flags(params)
    # The calibrated rays keep their profile-calibrated colours (fit_photometry.
    # held_free): re-fitting them here would score each removal against rays
    # the whole-image objective had re-shaped.
    WC = FP.fit(Asub, tgt, FP.params_wc(params), W, iters=iters, verbose=False, normal=nf,
                free=FP.held_free(params), teal_ok=FP.teal_eligible(params))
    out = FP.composite(Asub, FP.colors(WC), nf)
    return float(np.abs(out - tgt).mean() * 255), WC


def protected(keep_arg):
    """Layers never offered for removal: --keep, plus every ray of record.

    A ray is a few code values over a few hundred pixels, so removing one
    costs well under --max-cost of MAE while deleting a structure the reference
    plainly has.  Its evidence is its measured profile (tools/ray_lines.py),
    not a whole-image error, so this tool is the wrong judge of it.
    """
    import measure_flare as MFL
    return set(x.strip() for x in keep_arg.split(",") if x.strip()) | set(MFL.RAY_GEOMETRY)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=os.path.join(ROOT, "src", "params.json"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-cost", type=float, default=0.01,
                    help="remove a layer if dropping it costs less than this much MAE")
    ap.add_argument("--keep", default="exterior,field_base,arc_core,frame_base,frame_rim")
    a = ap.parse_args()

    params = json.load(open(a.params))
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float32) / 255.0
    ref = np.minimum(ref, 254.4 / 255.0)
    keep = protected(a.keep)
    cache = {}
    base, _ = evaluate(params, ref, cache=cache)
    print("baseline mae = %.4f (%d layers)" % (base, len(params["layers"])))
    while True:
        costs = []
        for L in params["layers"]:
            if L["id"] in keep:
                continue
            trial = copy.deepcopy(params)
            trial["layers"] = [q for q in trial["layers"] if q["id"] != L["id"]]
            mae, _ = evaluate(trial, ref, cache=cache)
            costs.append((mae - base, L["id"]))
        costs.sort()
        for c, lid in costs:
            print("  dropping %-20s costs %+.4f mae" % (lid, c))
        if not a.apply or not costs or costs[0][0] > a.max_cost:
            break
        c, lid = costs[0]
        params["layers"] = [q for q in params["layers"] if q["id"] != lid]
        base, WC = evaluate(params, ref, cache=cache)
        FP.store_wc(params, WC, only=FP.held_free(params))
        print("removed %s -> mae %.4f (%d layers)" % (lid, base, len(params["layers"])))
    if a.apply:
        base, WC = evaluate(params, ref, iters=25, cache=cache)
        FP.store_wc(params, WC, only=FP.held_free(params))
        json.dump(params, open(a.params, "w"), indent=1)
        print("wrote %s: %d layers, mae %.4f" % (a.params, len(params["layers"]), base))


if __name__ == "__main__":
    main()
