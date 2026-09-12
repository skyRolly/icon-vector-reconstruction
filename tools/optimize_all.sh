#!/bin/sh
# Full parameter-fitting cycle.  Each stage optimises one family of parameters
# with the layer colours re-fitted inside the loop, so the stages compose:
#   shapes    stroke widths, blur radii, gradient radii and falloff exponents
#   tapers    where along each arc the glow fades in and out
#   geometry  flare centre, frame box and stroke width, glow clip extent
#   field     background gradient centres
# The arcs' own control points are never searched: they are fitted to the
# sub-pixel ridge at 0.09 px, better than a raster objective can resolve.
set -e
cd "$(dirname "$0")/.."
python3 -u tools/optimize.py --spec shapes   --sweeps 2 --stride 4
python3 -u tools/optimize.py --spec tapers   --sweeps 2 --stride 4
python3 -u tools/optimize.py --spec geometry --sweeps 1 --stride 4
python3 -u tools/optimize.py --spec field    --sweeps 1 --stride 4
python3 -u tools/optimize.py --spec shapes   --sweeps 1 --stride 3
python3 -u tools/fit_photometry.py --iters 30 --stride 2
python3 src/build_svg.py
python3 tools/render.py reconstruction.svg out/render_1024.png
python3 tools/compare.py reference.png out/render_1024.png --out-prefix out/diff --json out/metrics.json
python3 tools/make_previews.py out/render_1024.png
