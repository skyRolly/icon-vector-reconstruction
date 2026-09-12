#!/usr/bin/env python3
"""Render an SVG to PNG at a controlled resolution.

Two independent renderers are available so that the reconstruction can be
cross-validated (SVG filter/blend semantics differ subtly between engines):

  resvg     -- via the `resvg-py` binding.  Fast (~60ms at 1024px), used for
               the optimisation loop and as the renderer of record.
  chromium  -- the headless Chromium shipped in this environment.  Slower
               (~1.2s) but represents "what a browser shows".

Usage:
    python3 tools/render.py reconstruction.svg out/render_1024.png --size 1024
    python3 tools/render.py reconstruction.svg out/chrome_1024.png --renderer chromium
"""
import argparse
import io
import os
import subprocess
import sys
import tempfile

CHROME = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"


def render_resvg(svg_path: str, size: int) -> bytes:
    import resvg_py

    svg = open(svg_path, "r", encoding="utf-8").read()
    out = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)
    return bytes(out) if not isinstance(out, (bytes, bytearray)) else out


def render_chromium(svg_path: str, size: int) -> bytes:
    if not os.path.exists(CHROME):
        raise RuntimeError("headless chromium not found at %s" % CHROME)
    with tempfile.TemporaryDirectory() as td:
        # Wrap in HTML so the SVG is scaled to the requested raster size.
        html = os.path.join(td, "wrap.html")
        svg = open(svg_path, "r", encoding="utf-8").read()
        open(html, "w", encoding="utf-8").write(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;background:#000}"
            "svg{display:block;width:%dpx;height:%dpx}</style>%s" % (size, size, svg)
        )
        png = os.path.join(td, "shot.png")
        subprocess.run(
            [
                CHROME,
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--screenshot=" + png,
                "--window-size=%d,%d" % (size, size),
                "file://" + html,
            ],
            check=True,
            capture_output=True,
        )
        return open(png, "rb").read()


def render(svg_path: str, size: int = 1024, renderer: str = "resvg") -> bytes:
    if renderer == "resvg":
        return render_resvg(svg_path, size)
    if renderer == "chromium":
        return render_chromium(svg_path, size)
    raise ValueError("unknown renderer %r" % renderer)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("out")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--renderer", default="resvg", choices=["resvg", "chromium"])
    a = ap.parse_args()
    data = render(a.svg, a.size, a.renderer)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "wb").write(data)
    print("wrote %s (%d bytes, %dx%d, %s)" % (a.out, len(data), a.size, a.size, a.renderer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
