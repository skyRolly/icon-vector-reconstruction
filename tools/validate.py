#!/usr/bin/env python3
"""Render the reconstruction at several sizes, in both engines, and report.

Checks three different things, which are easy to confuse:

1. FIDELITY at the reference resolution (1024): reconstruction vs reference.png.
2. CROSS-ENGINE agreement at 1024: resvg vs Chromium on the same SVG.  Any
   disagreement here is a portability problem in the SVG, not an artwork problem.
3. SCALE COHERENCE: render at 4096/2048/512/256, box-downsample to 1024, and
   compare with the reference.  A vector artwork should get *closer* to the
   reference as the render resolution rises (the reference itself being a
   1024-px raster of a smooth original); a construction that depends on
   1024-px rasterisation accidents shows up as divergence.

    python3 tools/validate.py                 # full sweep -> out/validation.md
    python3 tools/validate.py --quick
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import compare as C  # noqa: E402
import render as R  # noqa: E402


def to_array(png_bytes):
    return np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB")).astype(np.float64)


def box_down(a, target):
    h = a.shape[0]
    assert h % target == 0, (h, target)
    k = h // target
    return a.reshape(target, k, target, k, 3).mean(axis=(1, 3))


def metrics(ref, rec):
    d = np.abs(rec - ref)
    g = np.abs((rec / 255.0) ** (1 / 2.2) - (ref / 255.0) ** (1 / 2.2)) * 255
    return {
        "mae": float(d.mean()),
        "rmse": float(np.sqrt(((rec - ref) ** 2).mean())),
        "max": float(d.max()),
        "mae_gamma": float(g.mean()),
        "ssim": C.ssim(ref.mean(2), rec.mean(2)),
        "pct_gt8": float((d.max(2) > 8).mean() * 100),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", default=os.path.join(ROOT, "reconstruction.svg"))
    ap.add_argument("--reference", default=os.path.join(ROOT, "reference.png"))
    ap.add_argument("--outdir", default=os.path.join(ROOT, "out"))
    ap.add_argument("--report", default=os.path.join(ROOT, "out", "validation.md"))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--no-chromium", action="store_true",
                    help="skip the cross-engine comparison (it is optional)")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ref = np.asarray(Image.open(a.reference).convert("RGB")).astype(np.float64)

    sizes = [1024, 2048] if a.quick else [256, 512, 1024, 2048, 4096]
    rows = []
    for size in sizes:
        png = R.render(a.svg, size, "resvg")
        open(os.path.join(a.outdir, "render_%d.png" % size), "wb").write(png)
        arr = to_array(png)
        if size >= 1024:
            rec = box_down(arr, 1024) if size > 1024 else arr
            m = metrics(ref, rec)
            note = "downsampled %d->1024" % size if size > 1024 else "native"
        else:
            refd = box_down(ref, size)
            m = metrics(refd, arr)
            note = "reference downsampled to %d" % size
        rows.append(("resvg", size, note, m))

    # Chromium is a second opinion, not a dependency: the resvg rows above are
    # the report.  It is skipped -- with a note in the report, not a crash --
    # when the binary is absent or --no-chromium is given, so a checkout with
    # only the documented requirements can run this.
    cross = None
    chrome_path, chrome_how = R.chromium_source()
    want_chrome = not a.no_chromium and chrome_path is not None
    if want_chrome:
        print("chromium: %s  (found via %s)" % (chrome_path, chrome_how))
    if want_chrome:
        try:
            png = R.render(a.svg, 1024, "chromium")
            open(os.path.join(a.outdir, "render_1024_chromium.png"), "wb").write(png)
            chrome = to_array(png)
            rows.append(("chromium", 1024, "native", metrics(ref, chrome)))
            cross = metrics(to_array(R.render(a.svg, 1024, "resvg")), chrome)
        except Exception as exc:                      # noqa: BLE001
            print("chromium render failed (%s); continuing without it" % exc)
            want_chrome = False
    elif not a.no_chromium:
        print("cross-engine check SKIPPED -- %s" % chrome_how)

    lines = ["# Validation report", "",
             "Fidelity of `reconstruction.svg` against `reference.png`, plus",
             "cross-engine and cross-resolution behaviour.", "",
             "| engine | render size | comparison | MAE | RMSE | max | MAE(gamma) | SSIM | %px>8 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for eng, size, note, m in rows:
        lines.append("| %s | %d | %s | %.3f | %.3f | %.0f | %.3f | %.4f | %.2f |"
                     % (eng, size, note, m["mae"], m["rmse"], m["max"], m["mae_gamma"], m["ssim"], m["pct_gt8"]))
    lines += ["", "## Cross-engine agreement at 1024 (resvg vs Chromium)", ""]
    if cross:
        lines += ["| MAE | RMSE | max | SSIM |", "|---|---|---|---|",
                  "| %.3f | %.3f | %.0f | %.5f |"
                  % (cross["mae"], cross["rmse"], cross["max"], cross["ssim"]), ""]
    else:
        lines += ["Not measured in this run: headless Chromium was unavailable or disabled.",
                  "The resvg rows above are unaffected.", ""]
    open(a.report, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    json.dump({"rows": [{"engine": e, "size": s, "note": n, **m} for e, s, n, m in rows],
               "cross_engine": cross},
              open(os.path.join(a.outdir, "validation.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
