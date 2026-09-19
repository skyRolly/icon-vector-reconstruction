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


#: The four states a caller has to be able to tell apart.  Collapsing the
#: middle two into "no browser, never mind" is what let a broken cross-engine
#: check report a successful validation:
#:
#:   configured    an environment variable names a usable binary
#:   discovered    none was named, but one was found -- also usable
#:   misconfigured an environment variable names something that is NOT usable.
#:                 This is a BROKEN SETUP, not an absent optional dependency:
#:                 somebody asked for a specific browser and did not get it, so
#:                 it must not pass as a skip.
#:   absent        nothing named and nothing found.  A genuine optional skip.
#:
#: Execution failure is a fifth outcome and does not live here, because it is
#: only knowable after a render is attempted; `validate.py` reports it.
CHROME_STATES = ("configured", "discovered", "misconfigured", "absent")


def find_chromium():
    """The first usable Chromium, or None.  Never raises.

    Returns the path; `chromium_status()` says how it was found and whether
    "none" means "none configured" or "the configured one is broken", which is
    what a validation report needs in order to be honest about its own coverage.
    """
    return _chromium()[0]


def chromium_source():
    """(path, how) for the Chromium that would be used -- (None, reason) if none."""
    return _chromium()[:2]


def chromium_status():
    """(path, how, state) -- `state` is one of CHROME_STATES."""
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
                return p, "$%s" % var, "configured"
            why = ("does not exist" if not os.path.exists(p)
                   else "is a directory" if os.path.isdir(p)
                   else "is not executable" if not os.access(p, os.X_OK)
                   else "is not a regular file")
            return None, "$%s is set to %r, which %s" % (var, p, why), "misconfigured"
    for pat in CHROME_GLOBS:
        hits = sorted(_glob.glob(os.path.expanduser(pat)))
        for p in hits:
            if _ok(p):
                return p, "glob %s" % pat, "discovered"
    for name in CHROME_NAMES:
        p = _shutil.which(name)
        if _ok(p):
            return p, "PATH (%s)" % name, "discovered"
    for p in CHROME_FIXED:
        if _ok(p):
            return p, "well-known path", "discovered"
    return None, ("no Chromium found: set one of %s, or install one on PATH as %s"
                  % (", ".join("$" + v for v in CHROME_ENV), "/".join(CHROME_NAMES[:3])),
                  "absent")


def sha256_file(path):
    """Content digest of a file, for provenance."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class ProvenanceError(Exception):
    """A render cannot be shown to have come from the SVG its sidecar names."""


#: What hashlib.sha256().hexdigest() emits, and what every sidecar this
#: repository writes contains.
_HEXDIGITS = frozenset("0123456789abcdef")


def _digest_field(d, field, render_path, absent):
    """One sha-256 field of a sidecar, checked for SHAPE before it is used.

    A sidecar is arbitrary JSON and only emptiness was ever tested here, so a
    `png_sha256` of `1` passed, compared unequal to the real digest, and then
    hit `want[:12]` in the very message that exists to REPORT that difference:
    TypeError, raised out of a function whose whole contract is that a sidecar
    it cannot believe raises ProvenanceError.  Callers written to classify
    rather than crash -- `validate.py`'s carried_rasters, whose answer for this
    is `unverifiable` -- went down with it.  A list is worse because it is
    quiet: it slices without complaining and gets formatted into the evidence
    as `['nope']`, so a malformed sidecar reads as a measurement.

    Shape is therefore checked where the value is read rather than where it is
    formatted.  Anything that is not 64 lowercase hex characters is a malformed
    sidecar, which proves nothing about the raster and so is a ProvenanceError
    like every other sidecar that proves nothing.
    """
    v = d.get(field)
    if not v:
        raise ProvenanceError(absent % render_path)
    if not isinstance(v, str) or len(v) != 64 or set(v) - _HEXDIGITS:
        raise ProvenanceError(
            "provenance beside %s records %s=%r, which is not a sha-256 digest: "
            "the sidecar is malformed, so it proves nothing about this file"
            % (render_path, field, v))
    return v


def provenance_path(render_path):
    return str(render_path) + ".prov.json"


def write_provenance(render_path, svg_path, data, size, renderer):
    """Record which SVG this raster came from, by content, beside the raster.

    `data` is the PNG's own bytes, and its digest goes in too.  That second
    digest is the whole point: without it the sidecar describes a FILENAME, and
    a filename can be overwritten by anything.
    """
    # `svg_path` is a label, not evidence -- nothing reads it, and the two
    # digests are what prove anything.  It is stored RELATIVE to the repository
    # root because an absolute one made every committed sidecar carry the
    # machine it was generated on, so regenerating identical artefacts somewhere
    # else changed tracked metadata without changing a single input.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = os.path.relpath(os.path.abspath(svg_path), root)
    prov = {"svg_sha256": sha256_file(svg_path),
            "svg_path": rel if not rel.startswith("..") else os.path.abspath(svg_path),
            "size": size, "renderer": renderer,
            "png_sha256": hashlib.sha256(data).hexdigest()}
    json.dump(prov, open(provenance_path(render_path), "w"), indent=1, sort_keys=True)
    return prov


def clear_provenance(render_path):
    """Remove a sidecar, for a writer that replaces a render without describing it.

    Deleting provenance is honest; leaving a stale one is not.  A tool that
    cannot say where a raster came from must not leave behind a file that says
    it can.
    """
    try:
        os.remove(provenance_path(render_path))
        return True
    except FileNotFoundError:
        return False


def read_provenance(render_path, require=False, expect_size=None,
                    expect_renderer=None, expect_svg=None):
    """The SVG digest recorded beside a render, VERIFIED against the raster itself.

    The sidecar records two digests and only one of them was ever checked.  A
    reader that trusts `svg_sha256` alone is trusting a claim about a path: replace
    out/render_1024.png with different bytes and leave the sidecar untouched, and
    every downstream report goes on attributing its numbers to the SVG named
    there.  That is not a corner case -- it is what a stale artefact, a restored
    backup or a second tool writing the same filename actually looks like.

    So the PNG is hashed and compared with `png_sha256` first.  Only if that
    matches is `svg_sha256` returned, and it is then a statement about content.

    `require=False` returns None when there is no sidecar at all: provenance is
    optional for an ad-hoc render.  It is never optional once a sidecar exists --
    a sidecar that does not describe this file is an error, not an absence,
    because it is evidence that something has gone wrong rather than evidence
    that nothing has been recorded.

    `expect_size` and `expect_renderer` are for the callers that do not want just
    ANY authentic render: the README publishes the 1024-px resvg ACCEPTANCE
    render, and the sidecar has recorded `size` and `renderer` all along without
    anyone reading them.  Hashing alone does not catch this, because the wrong
    render can be perfectly authentic -- `validate.py` writes
    out/render_1024_chromium.png in the same directory from the same SVG, and
    copying it over out/render_1024.png with its own sidecar would satisfy every
    digest here while publishing Chromium's numbers as the acceptance figures.

    `expect_svg` closes the last gap, and it was a real one: everything above
    authenticates the RASTER, and `svg_sha256` stayed a recorded claim about a
    file nobody re-read.  A render whose SVG has since been rebuilt is exactly
    as authentic as one whose SVG has not -- that is what "stale" means, and
    three of this iteration's eight verifiers were caught measuring precisely
    that.  Pass the SVG the caller believes it is measuring and the recorded
    digest becomes checkable rather than merely recorded.  It is opt-in because
    an ad-hoc render of a scratch SVG is legitimate and the file may be gone;
    for the acceptance render, publish.sh passes it.
    """
    side = provenance_path(render_path)
    if not os.path.exists(side):
        if require:
            raise ProvenanceError("no provenance beside %s: it cannot be shown to "
                                  "have come from any particular SVG" % render_path)
        return None
    try:
        d = json.load(open(side))
    except Exception as exc:                               # noqa: BLE001
        raise ProvenanceError("provenance beside %s is unreadable: %s" % (render_path, exc))
    want = _digest_field(d, "png_sha256", render_path,
                         "provenance beside %s records no png_sha256, so it "
                         "describes a filename rather than a file")
    got = sha256_file(render_path)
    if got != want:
        raise ProvenanceError(
            "provenance beside %s describes a different raster (sidecar png_sha256 "
            "%s..., actual %s...): the render was replaced without its sidecar"
            % (render_path, want[:12], got[:12]))
    for field, want_v in (("size", expect_size), ("renderer", expect_renderer)):
        if want_v is None:
            continue
        got_v = d.get(field)
        if got_v != want_v:
            raise ProvenanceError(
                "provenance beside %s records %s=%r where %r was required: the "
                "raster is authentic but it is not the render this caller measures"
                % (render_path, field, got_v, want_v))
    svg = _digest_field(d, "svg_sha256", render_path,
                        "provenance beside %s names no SVG")
    if expect_svg is not None:
        if not os.path.exists(expect_svg):
            raise ProvenanceError(
                "provenance beside %s was to be checked against %s, which does not "
                "exist" % (render_path, expect_svg))
        now = sha256_file(expect_svg)
        if now != svg:
            raise ProvenanceError(
                "provenance beside %s records svg_sha256 %s... but %s now hashes to "
                "%s...: the render is authentic and stale -- it predates the SVG it "
                "is being measured as" % (render_path, svg[:12], expect_svg, now[:12]))
    return svg


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
    write_provenance(a.out, a.svg, data, a.size, a.renderer)
    print("wrote %s (%d bytes, %dx%d, %s)" % (a.out, len(data), a.size, a.size, a.renderer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
