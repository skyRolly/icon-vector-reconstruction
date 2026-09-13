#!/usr/bin/env python3
"""Targeted diagnostics for the two regions a global metric cannot police.

A whole-image MAE is dominated by the ~80% of the canvas that is dark
background, so it barely moves when the central flare or the illumination
inside the curves is wrong.  These are the measurements that do move, and they
are reported reference-vs-render side by side in the same units.

  flare   centre position, radial falloff, horizontal and vertical cuts,
          angular structure, and the regional error
  lobes   brightness against perpendicular distance from each curve, at
          several heights, left and right reported separately
  crops   reference | render | signed difference, for both regions

    python3 tools/diagnose.py out/render_1024.png
    python3 tools/diagnose.py out/render_1024.png --json out/diagnostics.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from regions import (ARCS, FLARE_CORE, PROFILE_EDGES, PROFILE_T_BANDS,  # noqa: E402
                     corner_cells, profile_bins, profile_cells)


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def bilinear(a, x, y):
    h, w, _ = a.shape
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1); y1 = np.clip(y0 + 1, 0, h - 1)
    x0 = np.clip(x0, 0, w - 1); y0 = np.clip(y0, 0, h - 1)
    fx = (x - x0)[..., None]; fy = (y - y0)[..., None]
    return (a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x1] * fx * (1 - fy)
            + a[y1, x0] * (1 - fx) * fy + a[y1, x1] * fx * fy)


def arc_station(side, tdeg):
    cx, cy, rx, ry = ARCS[side]
    t = math.radians(tdeg)
    s = 1.0 if side == "left" else -1.0
    px = cx + s * rx * math.cos(t)
    py = cy + ry * math.sin(t)
    nx, ny = s * ry * math.cos(t), rx * math.sin(t)
    n = math.hypot(nx, ny)
    return px, py, nx / n, ny / n


def flare_report(ref, rec, out):
    cx, cy = FLARE_CORE
    h, w, _ = ref.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot(xx - cx, yy - cy)
    th = (np.degrees(np.arctan2(-(yy - cy), xx - cx)) + 360) % 360
    rows = []
    print("flare: radial profile about the measured core (%.2f, %.2f)" % (cx, cy))
    print("      r      ref      rec     diff")
    for r0, r1 in ((0, 6), (6, 12), (12, 20), (20, 30), (30, 45), (45, 65),
                   (65, 90), (90, 130), (130, 180), (180, 250)):
        m = (r >= r0) & (r < r1)
        a, b = ref.mean(2)[m].mean(), rec.mean(2)[m].mean()
        print("  %3d-%3d %8.2f %8.2f %+8.2f" % (r0, r1, a, b, b - a))
        rows.append({"r": [r0, r1], "ref": a, "rec": b})
    out["flare_radial"] = rows
    # peak position of each image near the core
    win = r < 45
    for nm, img in (("ref", ref), ("rec", rec)):
        lum = np.where(win, img.mean(2), 0)
        iy, ix = np.unravel_index(np.argmax(lum), lum.shape)
        m = win & (lum > 0.9 * lum.max())
        ys, xs = np.nonzero(m); wt = lum[m]
        out["flare_peak_" + nm] = {"peak_xy": [int(ix), int(iy)], "peak_lum": float(lum.max()),
                                   "centroid": [float((xs * wt).sum() / wt.sum()),
                                                float((ys * wt).sum() / wt.sum())]}
        print("  %s peak lum %.1f at (%d, %d); >90%% centroid (%.2f, %.2f)"
              % (nm, lum.max(), ix, iy, *out["flare_peak_" + nm]["centroid"]))
    print("  horizontal cut through the core (y = %d):" % round(cy))
    print("     x:  " + " ".join("%6d" % x for x in range(380, 700, 30)))
    for nm, img in (("ref", ref), ("rec", rec)):
        print("   %s:  " % nm + " ".join("%6.1f" % img[round(cy), x].mean() for x in range(380, 700, 30)))
    print("  vertical cut through the core (x = %d):" % round(cx))
    print("     y:  " + " ".join("%6d" % y for y in range(390, 650, 25)))
    for nm, img in (("ref", ref), ("rec", rec)):
        print("   %s:  " % nm + " ".join("%6.1f" % img[y, round(cx)].mean() for y in range(390, 650, 25)))
    out["flare_cut_h"] = {nm: [float(img[round(cy), x].mean()) for x in range(330, 740, 10)]
                          for nm, img in (("ref", ref), ("rec", rec))}
    out["flare_cut_v"] = {nm: [float(img[y, round(cx)].mean()) for y in range(340, 690, 10)]
                          for nm, img in (("ref", ref), ("rec", rec))}
    print("  angular structure, mean lum minus the per-band median:")
    print("      band " + " ".join("%5.0f" % a for a in np.arange(0, 360, 30)))
    ang = {}
    for r0, r1 in ((30, 50), (50, 80), (80, 120), (120, 180)):
        band = (r >= r0) & (r < r1)
        for nm, img in (("ref", ref), ("rec", rec)):
            lum = img.mean(2); med = np.median(lum[band])
            vals = []
            for a in np.arange(0, 360, 30):
                mm = band & (th >= a) & (th < a + 30)
                vals.append(float(lum[mm].mean() - med) if mm.sum() > 10 else float("nan"))
            ang["%s_%d_%d" % (nm, r0, r1)] = vals
            print("  %s %3d-%3d " % (nm, r0, r1)
                  + " ".join("%+5.1f" % v if np.isfinite(v) else "    ." for v in vals))
    out["flare_angular"] = ang
    m = r < 110
    out["flare_mae"] = float(np.abs(ref - rec)[m].mean())
    print("  MAE within 110 px of the core: %.3f" % out["flare_mae"])


def lobe_report(ref, rec, out):
    print("\nlobes: mean luminance against inward distance from each curve")
    res = {}
    for side in ("left", "right"):
        print("  %s curve  (s < 0 = concave side, towards the nearer frame edge)" % side)
        print("      t     " + " ".join("%6d" % s for s in (-20, -40, -70, -110, -160, -220, -300)))
        for tdeg in (-45, -25, -5, 15, 35):
            px, py, nx, ny = arc_station(side, tdeg)
            ss = np.array([-20, -40, -70, -110, -160, -220, -300], float)
            xs, ys = px + ss * nx, py + ss * ny
            a = bilinear(ref, xs, ys).mean(1)
            b = bilinear(rec, xs, ys).mean(1)
            res["%s_%+d" % (side, tdeg)] = {"s": ss.tolist(), "ref": a.tolist(), "rec": b.tolist()}
            print("   %+4d ref " % tdeg + " ".join("%6.1f" % v for v in a))
            print("        rec " + " ".join("%6.1f" % v for v in b))
            print("        d   " + " ".join("%+6.1f" % v for v in (b - a)))
    out["lobe_profiles"] = res
    h, w, _ = ref.shape
    yy, xx = np.mgrid[0:h, 0:w]
    for side, box in (("left", (110, 200, 430, 840)), ("right", (600, 200, 920, 840))):
        x0, y0, x1, y1 = box
        m = np.zeros((h, w), bool); m[y0:y1, x0:x1] = True
        cx, cy, rx, ry = ARCS[side]
        u = (xx - cx) / rx; v = (yy - cy) / ry
        rr = np.sqrt(u * u + v * v)
        d = np.abs(rr - 1.0) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2) / np.maximum(rr, 1e-6)
        m &= d > 25
        out["lobe_mae_" + side] = float(np.abs(ref - rec)[m].mean())
        out["lobe_bias_" + side] = float((rec - ref)[m].mean())
        print("  %s lobe (>25 px from the ridge): MAE %.3f, bias %+.3f"
              % (side, out["lobe_mae_" + side], out["lobe_bias_" + side]))
    print("  colour in the lobes (mean rgb, same masks):")
    for side, box in (("left", (140, 260, 400, 780)), ("right", (640, 260, 900, 780))):
        x0, y0, x1, y1 = box
        a = ref[y0:y1, x0:x1].reshape(-1, 3).mean(0)
        b = rec[y0:y1, x0:x1].reshape(-1, 3).mean(0)
        out["lobe_rgb_" + side] = {"ref": a.tolist(), "rec": b.tolist()}
        print("    %-5s ref (%5.2f,%5.2f,%5.2f)  rec (%5.2f,%5.2f,%5.2f)   G/B ref %.3f rec %.3f"
              % (side, *a, *b, a[1] / a[2], b[1] / b[2]))


def profile_report(ref, rec, out):
    """Brightness against signed distance from the curve, both sides.

    This is the measurement the global metric cannot see: the reference's glow
    is strongly one-sided (1.7x brighter on the concave side 11 px out, 5.9x
    brighter 100 px out), and getting that asymmetry wrong moves every pixel in
    the lobes and between the curves by only a code value or two -- while
    changing the picture completely.
    """
    print("\nprofile: mean luminance against signed distance from the curve")
    print("  s < 0 concave (lobe) side, s > 0 convex (between the curves)")
    print("       s        n      ref      rec     diff     rel")
    rows = []
    rel = []
    for lo, hi, m in profile_bins(ref.shape):
        a = ref.mean(2)[m].mean()
        b = rec.mean(2)[m].mean()
        r = (b - a) / max(a, 1e-6)
        rel.append(r)
        rows.append({"s": [lo, hi], "n": int(m.sum()), "ref": float(a), "rec": float(b)})
        print("  %5d..%-5d %7d %8.2f %8.2f %+8.2f %+7.1f%%"
              % (lo, hi, m.sum(), a, b, b - a, 100 * r))
    rms = float(np.sqrt(np.mean(np.square(rel)))) if rel else float("nan")
    out["profile"] = rows
    out["profile_rms_rel"] = rms
    print("  rms relative error over the bins: %.1f%%" % (100 * rms))

    # Pooling along the curve hides the tips: the same reconstruction can sit
    # within 5% in every pooled bin and be 30% too dark 80 degrees along.
    cells = profile_cells(ref.shape)
    grid = {}
    crel = []
    for lo, hi, t0, t1, m in cells:
        a = ref.mean(2)[m].mean()
        b = rec.mean(2)[m].mean()
        r = (b - a) / max(a, 1e-6)
        crel.append(r)
        grid[(lo, t0)] = (float(a), float(b), int(m.sum()))
    out["profile_cells"] = [{"s": [lo, hi], "t": [t0, t1], "n": int(m.sum()),
                             "ref": float(ref.mean(2)[m].mean()),
                             "rec": float(rec.mean(2)[m].mean())}
                            for lo, hi, t0, t1, m in cells]
    crms = float(np.sqrt(np.mean(np.square(crel)))) if crel else float("nan")
    out["profile_cells_rms_rel"] = crms
    print("\n  the same profile by along-curve band (relative error, |t| in degrees):")
    print("       s     " + "".join("%9s" % ("%d-%d" % t) for t in PROFILE_T_BANDS))
    for lo, hi in zip(PROFILE_EDGES[:-1], PROFILE_EDGES[1:]):
        if lo == -9:
            continue
        cellrow = ["%+8.1f%%" % (100 * (grid[(lo, t0)][1] - grid[(lo, t0)][0])
                                 / max(grid[(lo, t0)][0], 1e-6))
                   if (lo, t0) in grid else "        ." for t0, t1 in PROFILE_T_BANDS]
        print("  %5d..%-5d" % (lo, hi) + "".join(cellrow))
    print("  rms relative error over the %d cells: %.1f%%" % (len(cells), 100 * crms))

    # Past the curve ends there is no curve glow, but the reference is not dark
    # there either; this is the light in the four interior corners.
    ccs = corner_cells(ref.shape)
    if ccs:
        print("\n  interior corners, by distance inside the frame:")
        print("     d_frame  half       n      ref      rec      rel")
        rows = []
        for lo, hi, half, m in ccs:
            a = ref.mean(2)[m].mean()
            b = rec.mean(2)[m].mean()
            rows.append({"d": [lo, hi], "half": half, "n": int(m.sum()),
                         "ref": float(a), "rec": float(b)})
            print("   %4d..%-4d %-7s %7d %8.2f %8.2f %+7.1f%%"
                  % (lo, hi, half, m.sum(), a, b, 100 * (b - a) / max(a, 1e-6)))
        out["corners"] = rows
        out["corner_rms_rel"] = float(np.sqrt(np.mean(
            [((r["rec"] - r["ref"]) / max(r["ref"], 1e-6)) ** 2 for r in rows])))
        print("  rms relative error over the corner cells: %.1f%%"
              % (100 * out["corner_rms_rel"]))


def crops(ref, rec, outdir):
    os.makedirs(outdir, exist_ok=True)
    for name, box, scale in (("flare", (410, 400, 650, 630), 2),
                             ("lobe_left", (110, 180, 470, 860), 1),
                             ("lobe_right", (560, 180, 920, 860), 1)):
        x0, y0, x1, y1 = box
        a, b = ref[y0:y1, x0:x1], rec[y0:y1, x0:x1]
        d = b - a
        sg = np.zeros_like(a)
        sg[..., 0] = np.clip(d.mean(2) * 6, 0, 255)
        sg[..., 2] = np.clip(-d.mean(2) * 6, 0, 255)
        hh, ww, _ = a.shape
        im = Image.new("RGB", (ww * 3 + 16, hh), (40, 40, 40))
        for i, arr in enumerate((a, b, sg)):
            im.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), (i * (ww + 8), 0))
        if scale != 1:
            im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
        im.save(os.path.join(outdir, "diag_%s.png" % name))
    print("\nwrote crops to %s (reference | render | signed difference x6)" % outdir)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render", nargs="?", default=os.path.join(ROOT, "out", "render_1024.png"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--json", default=os.path.join(ROOT, "out", "diagnostics.json"))
    ap.add_argument("--crops", default=os.path.join(ROOT, "out"))
    a = ap.parse_args()
    ref, rec = load(a.reference), load(a.render)
    out = {"render": os.path.relpath(a.render, ROOT)}
    flare_report(ref, rec, out)
    lobe_report(ref, rec, out)
    profile_report(ref, rec, out)
    crops(ref, rec, a.crops)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
        print("wrote %s" % a.json)


if __name__ == "__main__":
    sys.exit(main())
