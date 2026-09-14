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
import hashlib
import json
import io
import os
import subprocess
import sys
import tempfile

#: Where a Chromium suitable for headless rendering might live.  A single
#: hard-coded Playwright path was the whole of this before, which meant a
#: perfectly good system Chromium counted as "unavailable" and cross-engine
#: validation silently narrowed to one machine's layout.  Order is preference,
#: not likelihood: the env var wins so a caller can always be explicit.
CHROME_ENV = ("ICON_CHROMIUM", "CHROME_PATH", "CHROMIUM_PATH")
CHROME_GLOBS = (
    "/opt/pw-browsers/*/chrome-linux/headless_shell",
    "/opt/pw-browsers/*/chrome-linux/chrome",
    "/opt/pw-browsers/*/chrome-linux64/chrome",
    "~/.cache/ms-playwright/*/chrome-linux/headless_shell",
    "~/.cache/ms-playwright/*/chrome-linux/chrome",
    "/root/.cache/ms-playwright/*/chrome-linux/headless_shell",
)
CHROME_NAMES = ("headless_shell", "chromium", "chromium-browser",
                "google-chrome-stable", "google-chrome", "chrome")
CHROME_FIXED = (
    "/usr/lib/chromium/chromium",
    "/usr/lib/chromium-browser/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def find_chromium():
    """The first usable Chromium, or None.  Never raises.

    Returns the path; `chromium_source()` says how it was found, which is what
    a validation report needs in order to be honest about its own coverage.
    """
    return _chromium()[0]


def chromium_source():
    """(path, how) for the Chromium that would be used -- (None, reason) if none."""
    return _chromium()


def _ok(p):
    return bool(p) and os.path.isfile(p) and os.access(p, os.X_OK)


def _chromium():
    import glob as _glob
    import shutil as _shutil
    for var in CHROME_ENV:
        p = os.environ.get(var)
        if p:
            if _ok(p):
                return p, "$%s" % var
            return None, "$%s is set to %r, which is not an executable file" % (var, p)
    for pat in CHROME_GLOBS:
        hits = sorted(_glob.glob(os.path.expanduser(pat)))
        for p in hits:
            if _ok(p):
                return p, "glob %s" % pat
    for name in CHROME_NAMES:
        p = _shutil.which(name)
        if _ok(p):
            return p, "PATH (%s)" % name
    for p in CHROME_FIXED:
        if _ok(p):
            return p, "well-known path"
    return None, ("no Chromium found: set one of %s, or install one on PATH as %s"
                  % (", ".join("$" + v for v in CHROME_ENV), "/".join(CHROME_NAMES[:3])))


def sha256_file(path):
    """Content digest of a file, for provenance."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def render_resvg_string(svg: str, size: int) -> bytes:
    """Rasterise SVG markup with resvg.  One implementation, shared.

    The regression pipeline used to import `resvg_py` itself when this name was
    absent, so the two could disagree about how the acceptance renderer is
    invoked.  It is defined here so they cannot.
    """
    import resvg_py

    out = resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)
    return bytes(out) if not isinstance(out, (bytes, bytearray)) else out



def render_resvg(svg_path: str, size: int) -> bytes:
    return render_resvg_string(open(svg_path, "r", encoding="utf-8").read(), size)


def render_chromium(svg_path: str, size: int) -> bytes:
    CHROME, how = chromium_source()
    if CHROME is None:
        raise RuntimeError(how)
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
    # A provenance sidecar: which SVG this raster came from, by content.  The
    # README's freshness check used to compare modification times, which a copy
    # or a restore defeats -- a metrics file can be newer than the SVG and still
    # describe a different one.  A digest cannot be wrong about that.
    prov = {"svg_sha256": sha256_file(a.svg), "svg_path": os.path.abspath(a.svg),
            "size": a.size, "renderer": a.renderer,
            "png_sha256": hashlib.sha256(data).hexdigest()}
    json.dump(prov, open(a.out + ".prov.json", "w"), indent=1, sort_keys=True)
    print("wrote %s (%d bytes, %dx%d, %s)" % (a.out, len(data), a.size, a.size, a.renderer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
