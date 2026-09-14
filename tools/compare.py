#!/usr/bin/env python3
"""Compare a rendered reconstruction against reference.png.

Reports several complementary metrics (no single number captures the failure
modes of a dark, high-dynamic-range icon):

  mae / rmse         mean absolute / root-mean-square error, sRGB 0-255
  max_ch             worst single-channel error
  pct_gt N           share of pixels whose max channel error exceeds N
  mae_gamma          MAE after a 1/2.2 "display" boost -- weights the huge
                     dark background area the way the eye does
  ssim               global structural similarity on luminance (gaussian 11x11)
  edge_iou           IoU of binary edge maps (gradient magnitude > threshold)
  region table       MAE broken down per region (frame band, curve band,
                     centre flare, background) so a small bright-core error is
                     not hidden by a large well-matched background

Also writes diff visualisations:
  <out>_diff.png       absolute difference, x4 gain
  <out>_signed.png     red = reconstruction too bright, blue = too dark
  <out>_sbs.png        reference | reconstruction | boosted diff, side by side
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image


def load(p, size=None):
    im = Image.open(p).convert("RGB")
    if size and im.size != (size, size):
        im = im.resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float64)


def gauss_kernel(sigma=1.5, n=11):
    x = np.arange(n) - n // 2
    k = np.exp(-(x ** 2) / (2 * sigma ** 2))
    k /= k.sum()
    return k


def blur(a, sigma=1.5, n=11):
    k = gauss_kernel(sigma, n)
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, a)
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, out)
    return out


def ssim(a, b):
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = blur(a), blur(b)
    sa = blur(a * a) - mu_a ** 2
    sb = blur(b * b) - mu_b ** 2
    sab = blur(a * b) - mu_a * mu_b
    s = ((2 * mu_a * mu_b + C1) * (2 * sab + C2)) / ((mu_a ** 2 + mu_b ** 2 + C1) * (sa + sb + C2))
    return float(s.mean())


def sobel(a):
    kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], float)
    ky = kx.T
    from numpy.lib.stride_tricks import sliding_window_view

    w = sliding_window_view(a, (3, 3))
    gx = (w * kx).sum(axis=(-1, -2))
    gy = (w * ky).sum(axis=(-1, -2))
    return np.hypot(gx, gy)


def regions(h, w):
    yy, xx = np.mgrid[0:h, 0:w]
    s = h / 1024.0
    # frame band: within 14px of the measured rounded-rect frame path
    fx0, fx1, fy0, fy1, r = 65.98 * s, 951.09 * s, 33.88 * s, 991.18 * s, 172.0 * s
    cx = np.clip(xx, fx0 + r, fx1 - r)
    cy = np.clip(yy, fy0 + r, fy1 - r)
    # distance to the rounded rect outline
    dx = np.maximum.reduce([fx0 - xx, xx - fx1, np.zeros_like(xx, float)])
    dy = np.maximum.reduce([fy0 - yy, yy - fy1, np.zeros_like(yy, float)])
    inside_dist = np.minimum.reduce(
        [xx - fx0, fx1 - xx, yy - fy0, fy1 - yy]
    ).astype(float)
    corner = (np.abs(xx - cx) > 0) & (np.abs(yy - cy) > 0)
    dcorner = np.hypot(xx - cx, yy - cy) - r
    dist = np.where(corner, np.abs(dcorner), np.abs(np.where(inside_dist > 0, inside_dist, -np.hypot(dx, dy))))
    frame = dist < 14 * s
    centre = np.hypot(xx - 517 * s, yy - 515 * s) < 90 * s
    return {"frame": frame, "centre": centre & ~frame}


def compare(ref_path, rec_path, out_prefix=None, quiet=False):
    ref = load(ref_path)
    rec = load(rec_path, size=ref.shape[0])
    h, w, _ = ref.shape
    d = rec - ref
    ad = np.abs(d)
    lum_ref = ref.mean(2)
    lum_rec = rec.mean(2)
    g_ref = (ref / 255.0) ** (1 / 2.2) * 255
    g_rec = (rec / 255.0) ** (1 / 2.2) * 255

    m = {
        "mae": float(ad.mean()),
        "rmse": float(np.sqrt((d ** 2).mean())),
        "max_ch": float(ad.max()),
        "mae_gamma": float(np.abs(g_rec - g_ref).mean()),
        "pct_gt2": float((ad.max(2) > 2).mean() * 100),
        "pct_gt8": float((ad.max(2) > 8).mean() * 100),
        "pct_gt24": float((ad.max(2) > 24).mean() * 100),
        "ssim": ssim(lum_ref, lum_rec),
        "mean_bias": float(d.mean()),
    }
    e_ref = sobel(lum_ref) > 40
    e_rec = sobel(lum_rec) > 40
    inter = (e_ref & e_rec).sum()
    union = (e_ref | e_rec).sum()
    m["edge_iou"] = float(inter / union) if union else 1.0

    reg = regions(h, w)
    covered = np.zeros((h, w), bool)
    for name, mask in reg.items():
        covered |= mask
        m["mae_" + name] = float(ad[mask].mean()) if mask.any() else 0.0
    rest = ~covered
    m["mae_rest"] = float(ad[rest].mean())
    # bright/dark split of the remainder
    bright = rest & (lum_ref > 60)
    dark = rest & (lum_ref <= 60)
    m["mae_bright"] = float(ad[bright].mean()) if bright.any() else 0.0
    m["mae_dark"] = float(ad[dark].mean()) if dark.any() else 0.0

    if out_prefix:
        os.makedirs(os.path.dirname(os.path.abspath(out_prefix)) or ".", exist_ok=True)
        Image.fromarray(np.clip(ad * 4, 0, 255).astype(np.uint8)).save(out_prefix + "_diff.png")
        sgn = np.zeros((h, w, 3))
        pos = np.clip(d.mean(2), 0, None) * 6
        neg = np.clip(-d.mean(2), 0, None) * 6
        sgn[..., 0] = np.clip(pos, 0, 255)
        sgn[..., 2] = np.clip(neg, 0, 255)
        sgn[..., 1] = np.clip(np.minimum(pos, neg), 0, 255)
        Image.fromarray(sgn.astype(np.uint8)).save(out_prefix + "_signed.png")
        third = w // 3
        sbs = Image.new("RGB", (third * 3, third))
        for i, arr in enumerate([ref, rec, np.clip(ad * 4, 0, 255)]):
            sbs.paste(Image.fromarray(arr.astype(np.uint8)).resize((third, third), Image.LANCZOS), (i * third, 0))
        sbs.save(out_prefix + "_sbs.png")

    if not quiet:
        print(json.dumps(m, indent=2, sort_keys=True))
    return m



def _provenance(render_path):
    """The SVG digest recorded beside a render, so a report names its own input."""
    import json as _json
    side = str(render_path) + ".prov.json"
    if os.path.exists(side):
        try:
            return _json.load(open(side)).get("svg_sha256")
        except Exception:                                  # noqa: BLE001
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reference")
    ap.add_argument("render")
    ap.add_argument("--out-prefix", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    m = compare(a.reference, a.render, a.out_prefix)
    if a.json:
        m = dict(m, source_svg_sha256=_provenance(a.render))
        open(a.json, "w").write(json.dumps(m, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
