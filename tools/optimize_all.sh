#!/bin/sh
# Full parameter-fitting cycle.  Each stage optimises one family of parameters
# with the layer colours re-fitted inside the loop, so the stages compose:
#   shapes    stroke widths, blur radii, gradient radii and falloff exponents
#   tapers    where along each arc the glow fades in and out
#   geometry  flare centre, frame box and stroke width, glow clip extent
#   field     background gradient centres
# The regression checks run first: they are what makes the rest trustworthy.
# The arcs' own control points are never searched: they are fitted to the
# sub-pixel ridge at 0.09 px, better than a raster objective can resolve.
set -e
cd "$(dirname "$0")/.."
python3 -u tools/test_pipeline.py
python3 -u tools/optimize.py --spec shapes   --sweeps 2 --stride 3 --fit-iters 6
python3 -u tools/optimize.py --spec tapers   --sweeps 2 --stride 4
python3 -u tools/optimize.py --spec geometry --sweeps 1 --stride 4
python3 -u tools/optimize.py --spec field    --sweeps 1 --stride 4
python3 -u tools/optimize.py --spec shapes   --sweeps 1 --stride 3 --fit-iters 6
python3 -u tools/fit_photometry.py --iters 30 --stride 2
# The rays last, because they are measured, not searched (D62).  Every stage
# above HOLDS them -- their shapes are not in the search and their colours are
# not re-fitted -- and this restores the geometry of record and then calibrates
# their amplitudes against their own measured profiles, over the background the
# stages above just settled.  A non-zero exit here stops the cycle: a release
# with uncalibrated rays is not a release.
python3 -u tools/measure_flare.py --geometry
# Everything from the rebuild onwards is the publish cycle, which is defined
# once in tools/publish.sh and used both here and on its own.  Keeping it in one
# place is what stops "the documented full cycle" and "what actually produces a
# release" from being two different things -- this script used to stop at the
# previews, with validation, the regression checks and the README left outside
# it, so no single command defined a reviewable state.
exec tools/publish.sh
