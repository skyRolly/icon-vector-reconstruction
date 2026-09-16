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



def _median1d(a, size):
    """1-D median filter with `nearest` edge handling, in numpy.

    Replaces `scipy.ndimage.median_filter` on the two profiles that used it.
    SciPy was the only third-party import outside numpy and Pillow and it was
    not in the documented requirements, so `tools/diagnose.py` needed a package
    the README never mentioned.  Two calls on a 90-sample profile do not justify
    the dependency; this is verified equal to SciPy's output on the actual data.
    """
    a = np.asarray(a, np.float64)
    r = int(size) // 2
    idx = np.clip(np.arange(a.size)[:, None] + np.arange(-r, r + 1)[None, :],
                  0, a.size - 1)
    return np.median(a[idx], axis=1)

def _median2d(a, size, block=48):
    """2-D median filter with `nearest` edge handling, in numpy.

    The other half of removing the SciPy dependency.  Verified identical to
    `scipy.ndimage.median_filter(a, size, mode="nearest")` on the reference, at
    2.3x the cost (4.4 s against 1.9 s over the full canvas) -- which is a fair
    price for a diagnostic, and a poor reason to require a package the
    reproduction instructions never listed.  Windowed in row blocks because the
    full sliding-window view of a 1024x1024 image at size 15 would be 1.9 GB.
    """
    a = np.asarray(a, np.float64)
    r = int(size) // 2
    ap = np.pad(a, r, mode="edge")
    out = np.empty_like(a)
    for y0 in range(0, a.shape[0], block):
        y1 = min(y0 + block, a.shape[0])
        win = np.lib.stride_tricks.sliding_window_view(ap[y0:y1 + 2 * r], (size, size))
        out[y0:y1] = np.median(win, axis=(-2, -1))
    return out


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



# The banding metric.  The band-pass scales are the cross-curve widths a stripe
# can have and still read as a stripe: narrower than ~3 px it is indistinguishable
# from the 8-bit grain, wider than ~12 px it reads as shading, not as an edge.
BAND_SIGMAS = (3.0, 6.0, 12.0)
#: The region each lobe's statistic is taken over: the frame interior, split at
#: the curves' mirror axis.  It has to be this wide.  With the narrower boxes
#: used before, only 217 of 481 along-curve stations had every cross-curve
#: sample inside the region, and a row averaged over a short unrepresentative
#: arc segment carries far more apparent coherent structure than a full one:
#: including such rows put the reference's coherent amplitude at 0.508 counts
#: and the render's at 0.764, an apparent 1.5x excess, where on fully populated
#: rows the same measurement gives 0.116 and 0.082 -- the render *below* the
#: reference.  Six rows out of 287 were carrying that conclusion.  With these
#: boxes all 481 stations are fully inside and no average is partial.
BAND_BOXES = {"left": (96, 96, 512, 930), "right": (512, 96, 928, 930)}
BAND_S_BANDS = ((-40, -14), (-70, -40), (-110, -70), (-160, -110), (-220, -160), (-300, -220))
#: The two halves have different causes and different remedies, so they are
#: never pooled.  Inside 40 px the glow basis is the limit -- its effective
#: cross-curve widths step 5.8 -> 20.6 px and the reference's shape lives in
#: that gap; outside 40 px the basis can reach the reference's profile but only
#: by amplitudes that wreck the frame and the flare, so what remains there is a
#: shared-basis trade-off.  Reported in percent because the interior runs at 8
#: to 35 counts and a count there is not the same error as a count at the ridge.
BAND_REGIONS = (("ridge", -40, -14), ("interior", -300, -40))


def _split(q, level):
    """rms of a coherent error and of its oscillatory part, in counts and percent."""
    wl = min(49, 2 * (q.size // 4) + 1)
    sm = np.convolve(q, np.ones(wl) / wl, mode="same")
    k = max(4, q.size // 8)
    osc, lo = (q - sm)[k:-k], level[k:-k]
    return {"cnt": float(np.sqrt((q ** 2).mean())),
            "pct": float(np.sqrt(((q / level) ** 2).mean()) * 100),
            "osc_cnt": float(np.sqrt((osc ** 2).mean())),
            "osc_pct": float(np.sqrt(((osc / lo) ** 2).mean()) * 100)}


def _smooth_nan(a, sigma):
    """Gaussian smoothing along axis 0 that ignores NaNs (normalised convolution)."""
    r = int(math.ceil(3.0 * sigma))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    ok = np.isfinite(a)
    v = np.where(ok, a, 0.0)
    num = np.empty_like(v); den = np.empty_like(v)
    for j in range(v.shape[1]):
        num[:, j] = np.convolve(v[:, j], k, mode="same")
        den[:, j] = np.convolve(ok[:, j].astype(float), k, mode="same")
    return np.where(den > 0.35, num / np.maximum(den, 1e-9), np.nan)


def _band_grid(side):
    """Sampling stations on an arc-aligned (s, t) grid over one lobe.

    Only along-curve stations whose *whole* cross-curve run lies inside the
    region are kept, so every average along the curve is taken over the same
    number of samples.  Mixing full and partial rows is not a detail: see the
    note above BAND_BOXES for the conclusion it reversed.
    """
    x0, y0, x1, y1 = BAND_BOXES[side]
    tdeg = np.arange(-58.0, 38.01, 0.20)
    ss = np.arange(-300.0, -13.99, 1.0)
    xs = np.empty((ss.size, tdeg.size)); ys = np.empty_like(xs)
    for j, t in enumerate(tdeg):
        px, py, nx, ny = arc_station(side, float(t))
        xs[:, j] = px + ss * nx
        ys[:, j] = py + ss * ny
    keep = ((xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)).all(axis=0)
    return ss, xs[:, keep], ys[:, keep], np.ones((ss.size, int(keep.sum())), bool)


def band_report(ref, rec, out):
    """The layered banding inside the curves, measured the way the eye sees it.

    The measurement that decides what this metric has to be: the render's total
    cross-curve band-pass amplitude in the lobes is *below* the reference's
    (0.51 rms against 0.68 at sigma 3 over the whole lobe, and 0.10-0.28 against
    0.49-0.65 across the open interior), so a plain high-pass "smoothness" score
    says the render is already smoother than the reference and would call the
    visible stripes an improvement.  Blur would score better still.  What
    actually differs is coherence along the curve: the reference's band-pass
    content is grain and JPEG texture, uncorrelated from one height to the next,
    so averaging along the curve cancels it as 1/sqrt(N); a layered field
    produces the same cross-curve profile at every height, and what survives
    that average is exactly what reads as a stripe.

    So both numbers here are computed on the along-curve *average* of the
    cross-curve profile, where the reference's own grain is suppressed to a few
    hundredths of a count and anything left is structure the model really has:

      profile error   the averaged profile, render minus reference, split into an
                      overall drift and the oscillatory part.  Alternating-sign
                      annular zones are the layered stripes; this is where they
                      show, and no amount of blurring removes them.
      coherent band-pass   the same average, high-passed.  This catches a narrow
                      cross-curve step that the profile error would average over.

    Both are calibrated by the reference and both are two-sided: having less
    coherent structure than the reference fails as well, which is what blurring
    the region until the stripes stop showing would produce.
    """
    print("\nbanding: coherent cross-curve structure inside the curves")
    print("  measured on the along-curve average, where the reference's grain")
    print("  falls to ~0.03 counts, so anything above that is real structure")
    res = {}
    worst_dev, worst_at = 0.0, None
    osc_rms = 0.0
    err_rms = 0.0
    worst_pct = 0.0
    worst_ridge = 0.0
    for side in ("left", "right"):
        ss, xs, ys, inside = _band_grid(side)
        La = np.where(inside, bilinear(ref, xs, ys).mean(2), np.nan)
        Lb = np.where(inside, bilinear(rec, xs, ys).mean(2), np.nan)
        n = np.isfinite(La).sum(1)
        use = n >= 60
        if use.sum() < 50:
            continue
        Pa = np.nanmean(La, axis=1)[use]
        Pb = np.nanmean(Lb, axis=1)[use]
        s = ss[use]
        grain = float(np.sqrt(np.nanmean(np.square((La - _smooth_nan(La, 3.0))[use]))))
        floor = grain / math.sqrt(max(n[use].mean(), 1.0))
        d = Pb - Pa
        # An overall level or slope mismatch is a photometric error; the
        # oscillation on top of it is the part that draws a visible contour.
        drift = np.convolve(d, np.ones(49) / 49.0, mode="same")
        k = 24
        osc = (d - drift)[k:-k]
        side_res = {
            "floor": floor, "n": float(n[use].mean()),
            "err_rms": float(np.sqrt((d ** 2).mean())),
            "err_p2p": float(d.max() - d.min()),
            "osc_rms": float(np.sqrt((osc ** 2).mean())),
            "osc_p2p": float(osc.max() - osc.min()),
            "bands": [],
        }
        err_rms = max(err_rms, side_res["err_rms"])
        osc_rms = max(osc_rms, side_res["osc_rms"])
        print("  %s curve  (%d s samples, %.0f along-curve samples each)"
              % (side, use.sum(), n[use].mean()))
        print("    reference grain floor on this average: %.4f counts" % floor)
        print("    coherent profile error  rms %6.3f  p2p %6.3f counts" % (
            side_res["err_rms"], side_res["err_p2p"]))
        print("    oscillatory part        rms %6.3f  p2p %6.3f counts  = %.0fx the floor"
              % (side_res["osc_rms"], side_res["osc_p2p"], side_res["osc_rms"] / max(floor, 1e-9)))
        print("      region        n     err_cnt   err%     osc_cnt   osc%")
        for nm, lo, hi in BAND_REGIONS:
            mm = (s >= lo) & (s < hi)
            if mm.sum() < 12:
                continue
            sp = _split(d[mm], Pa[mm])
            side_res[nm] = sp
            worst_pct = max(worst_pct, sp["pct"]) if nm == "interior" else worst_pct
            worst_ridge = max(worst_ridge, sp["pct"]) if nm == "ridge" else worst_ridge
            print("      %-9s %6d %9.3f %6.2f%% %9.3f %6.2f%%"
                  % (nm, mm.sum(), sp["cnt"], sp["pct"], sp["osc_cnt"], sp["osc_pct"]))
        print("         s       level_ref     err      err%      osc")
        for lo, hi in BAND_S_BANDS:
            m = (s >= lo) & (s < hi)
            if m.sum() < 3:
                continue
            mo = (s[k:-k] >= lo) & (s[k:-k] < hi)
            o = float(np.sqrt((osc[mo] ** 2).mean())) if mo.sum() > 2 else float("nan")
            side_res["bands"].append({"s": [lo, hi], "ref": float(Pa[m].mean()),
                                      "err": float(d[m].mean()), "osc": o})
            print("     %5d..%-5d %9.2f %+8.3f %+7.1f%% %8.3f"
                  % (lo, hi, Pa[m].mean(), d[m].mean(),
                     100 * d[m].mean() / max(Pa[m].mean(), 1e-6), o))
        # Split by region, because pooling hides where it is.  Localised in
        # cross-curve distance, the render's excess coherent structure sits
        # entirely in the 26 px strip beside the ridge -- 0.9 to 2.7x the
        # reference's there, on both curves and in every along-curve band --
        # while from 40 px outwards, across the whole open lobe, the render runs
        # 0.03 to 0.7x: smoother than the reference, coherently and in total.
        # A single pooled number for the lobe is dominated by the ridge strip,
        # because that is where the amplitudes are, and reads as though the
        # whole lobe were over-structured.  It is not.
        print("    coherent band-pass amplitude, reference against render:")
        for sg in BAND_SIGMAS:
            row = {}
            for name, L in (("ref", La), ("rec", Lb)):
                hp = L - _smooth_nan(L, sg)
                c = np.nanmean(np.where(np.isfinite(hp), hp, np.nan), axis=1)[use]
                reg = {}
                for nm, lo, hi in BAND_REGIONS:
                    rm = use & (ss >= lo) & (ss < hi)
                    if rm.sum() < 8:
                        continue
                    cr = np.nanmean(hp[rm], axis=1)
                    reg[nm] = float(np.sqrt(np.nanmean(np.square(cr))))
                row[name] = {"coh_rms": float(np.sqrt(np.nanmean(np.square(c)))),
                             "coh_p2p": float(np.nanmax(c) - np.nanmin(c)),
                             "tot_rms": float(np.sqrt(np.nanmean(np.square(hp[use])))),
                             **{"coh_" + k: v for k, v in reg.items()}}
            for nm, _, _ in BAND_REGIONS:
                k = "coh_" + nm
                if k in row["ref"] and k in row["rec"]:
                    row[nm + "_excess"] = row["rec"][k] / max(row["ref"][k], 1e-9)
            ex = row["rec"].get("coh_ridge", 0.0) / max(row["ref"].get("coh_ridge", 1e-9), 1e-9)
            # Two-sided on purpose.  Above 1 the render has coherent structure the
            # reference does not; below 1 it has lost structure the reference does
            # have, which is what blurring until the stripes stop showing gives.
            dev = max(ex, 1.0 / max(ex, 1e-9))
            if dev > worst_dev:
                worst_dev, worst_at = dev, "%s/sigma%g" % (side, sg)
            row["excess"] = ex
            side_res["sigma%g" % sg] = row
            print("      sigma %4.1f  ridge: ref %6.4f rec %6.4f = %5.2fx | "
                  "interior: ref %6.4f rec %6.4f = %5.2fx"
                  % (sg, row["ref"].get("coh_ridge", float("nan")),
                     row["rec"].get("coh_ridge", float("nan")), ex,
                     row["ref"].get("coh_interior", float("nan")),
                     row["rec"].get("coh_interior", float("nan")),
                     row.get("interior_excess", float("nan"))))
        res[side] = side_res
    out["banding"] = res
    out["banding_err_rms"] = err_rms
    out["banding_osc_rms"] = osc_rms
    out["banding_interior_pct"] = worst_pct
    out["banding_ridge_pct"] = worst_ridge
    out["banding_worst_dev"] = worst_dev
    out["banding_worst_at"] = worst_at
    print("  worst interior coherent error  %.2f%%   (shared-basis trade-off; see DECISIONS)"
          % worst_pct)
    print("  worst ridge coherent error     %.2f%%   (glow basis resolution)" % worst_ridge)
    print("  worst coherent profile error   %.3f counts rms  (target: the 0.03 count floor)"
          % err_rms)
    print("  worst oscillatory part         %.3f counts rms  (this is the stripe)" % osc_rms)
    print("  worst ridge-strip band-pass    %.2fx at %s  (target 1.00x, two-sided)"
          % (worst_dev, worst_at))
    print("     the open lobe beyond 40 px runs 0.03-0.7x: smoother than the reference")

def comb_report(ref, rec, out):
    """The horizontal streak family, line by line.

    Above a 21-px median envelope in y - which follows the broad bloom and
    cannot follow a 4-px line - the reference shows a sharp main line plus
    parallel satellites at dy = +6.5, +12 and +18.5 px, at the same y in every
    x-window east and west.  A radial profile averages all of that together,
    which is how a reconstruction came to have one broad hump instead.
    """
    cy = int(round(FLARE_CORE[1] - 0.5))
    cx = FLARE_CORE[0] - 0.5
    wins = ((-210, -110, "west far"), (-75, -25, "west near"),
            (25, 75, "east near"), (110, 210, "east far"))
    print("\nflare streak comb: thin-line amplitude above a 21-px median envelope")
    print("   dy  " + "".join("%19s" % t for _, _, t in wins))
    print("       " + "".join("%19s" % "ref      rec" for _ in wins))
    rows = {}
    for tag, img in (("ref", ref), ("rec", rec)):
        for a, b, name in wins:
            x0 = int(round(cx + min(a, b)))
            x1 = int(round(cx + max(a, b)))
            prof = img.mean(2)[cy - 45:cy + 45, x0:x1].mean(1)
            rows[(tag, name)] = prof - _median1d(prof, 21)
    table = []
    for i, dy in enumerate(range(-45, 45)):
        if dy < -12 or dy > 26:
            continue
        vals = []
        for _, _, name in wins:
            vals += [float(rows[("ref", name)][i]), float(rows[("rec", name)][i])]
        table.append({"dy": dy, "v": vals})
        mark = " <" if dy in (0, 7, 19) else ""
        print("  %+3d  " % dy + "".join("%9.2f%10.2f" % (vals[2 * k], vals[2 * k + 1])
                                        for k in range(len(wins))) + mark)
    out["comb"] = {"windows": [t for _, _, t in wins], "rows": table}
    # one number: rms over the lines the reference actually has
    err = []
    for r in table:
        if r["dy"] in (-1, 0, 1, 6, 7, 8, 18, 19, 20):
            for k in range(len(wins)):
                err.append(r["v"][2 * k + 1] - r["v"][2 * k])
    out["comb_rms"] = float(np.sqrt(np.mean(np.square(err)))) if err else float("nan")
    print("  rms error on the comb's own rows (dy 0, +7, +19): %.2f code values"
          % out["comb_rms"])


def spoke_report(ref, rec, out):
    """The thin spokes, as an angular scan of the structure a 15-px median misses."""
    tr = ref.mean(2) - _median2d(ref.mean(2), 15)
    tc = rec.mean(2) - _median2d(rec.mean(2), 15)
    h, w = tr.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = FLARE_CORE[0] - 0.5, FLARE_CORE[1] - 0.5
    r = np.hypot(xx - cx, yy - cy)
    th = (np.degrees(np.arctan2(-(yy - cy), xx - cx)) + 360) % 360
    dm = np.full((h, w), 1e9)
    for side, (ax, ay, rx, ry) in ARCS.items():
        u = (xx + 0.5 - ax) / rx
        v = (yy + 0.5 - ay) / ry
        rr = np.sqrt(u * u + v * v)
        dm = np.minimum(dm, np.abs(rr - 1) * np.sqrt((u * rx) ** 2 + (v * ry) ** 2)
                        / np.maximum(rr, 1e-6))
    band = (r >= 28) & (r < 110) & (dm > 13)
    rows = []
    for a in range(0, 360, 3):
        m = band & (th >= a) & (th < a + 3)
        if m.sum() < 40:
            continue
        rows.append({"deg": a, "ref": float(tr[m].mean()), "rec": float(tc[m].mean())})
    med = float(np.median([q["ref"] for q in rows]))
    print("\nflare spokes: thin-component mean by 3-degree sector, r 28-110, arcs masked")
    print("  the reference's clean maxima are the spokes; median background %+.2f" % med)
    print("    deg     ref     rec   diff")
    err = []
    for q in rows:
        if q["ref"] - med > 0.6:
            print("   %4d  %6.2f  %6.2f %+6.2f  %s"
                  % (q["deg"], q["ref"], q["rec"], q["rec"] - q["ref"],
                     "#" * int(max(0, (q["ref"] - med)) * 6)))
            err.append(q["rec"] - q["ref"])
    out["spokes"] = rows
    out["spoke_bg"] = med
    out["spoke_rms"] = float(np.sqrt(np.mean(np.square(err)))) if err else float("nan")
    print("  rms error over the reference's own spoke sectors: %.2f code values"
          % out["spoke_rms"])


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



def _provenance(render_path, require=False, expect_size=None, expect_renderer=None):
    """The SVG digest recorded beside a render -- see tools/render.py.

    This was a byte-for-byte copy of compare.py's version, and both trusted the
    sidecar's `svg_sha256` without checking that the sidecar described the PNG
    actually on disk.  One implementation now, in the module that writes them.
    """
    import render as _R
    return _R.read_provenance(render_path, require=require,
                              expect_size=expect_size, expect_renderer=expect_renderer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("render", nargs="?", default=os.path.join(ROOT, "out", "render_1024.png"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--json", default=os.path.join(ROOT, "out", "diagnostics.json"))
    ap.add_argument("--require-provenance", action="store_true",
                    help="fail unless the render can be shown to come from a known SVG")
    ap.add_argument("--expect-size", type=int, default=None,
                    help="also require the sidecar to record this render size")
    ap.add_argument("--expect-renderer", default=None,
                    help="also require the sidecar to record this renderer")
    ap.add_argument("--crops", default=os.path.join(ROOT, "out"))
    a = ap.parse_args()
    ref, rec = load(a.reference), load(a.render)
    out = {"render": os.path.relpath(a.render, ROOT)}
    flare_report(ref, rec, out)
    lobe_report(ref, rec, out)
    profile_report(ref, rec, out)
    band_report(ref, rec, out)
    comb_report(ref, rec, out)
    spoke_report(ref, rec, out)
    crops(ref, rec, a.crops)
    if a.json:
        out = dict(out, source_svg_sha256=_provenance(
            a.render, require=a.require_provenance,
            expect_size=a.expect_size, expect_renderer=a.expect_renderer))
        json.dump(out, open(a.json, "w"), indent=1)
        print("wrote %s" % a.json)


if __name__ == "__main__":
    sys.exit(main())
