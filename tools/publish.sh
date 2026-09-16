#!/bin/sh
# The publish cycle: turn the committed parameters into the complete, checked
# set of release artifacts.  This is the definition of "release-ready" -- if it
# passes, a reviewer can reproduce every number the README reports.
#
# Order matters and is a dependency order, not a preference:
#   1. rebuild the SVG          -- everything below measures THIS file
#   2. render it
#   3. metrics, diagnostics, validation, previews   -- all measure that render
#   4. regression checks        -- on the rebuilt artefacts, not on stale ones
#   5. README last              -- it publishes 3, so 3 must be settled first
#   6. reproducibility          -- the committed params must rebuild this SVG
#
# README regeneration used to sit outside this cycle entirely, which is how a
# flare MAE of 6.37 came to be published against an actual 7.11: out/diagnostics
# .json was never regenerated and nothing checked that it matched the artwork.
set -e
cd "$(dirname "$0")/.."

echo "== 1. rebuild =="
python3 src/build_svg.py

echo "== 2. render =="
python3 tools/render.py reconstruction.svg out/render_1024.png

echo "== 3. measure =="
# --require-provenance: these two write the JSON the README publishes, so they
# must be able to PROVE the raster they measured came from the SVG rebuilt in
# step 1.  Without it a stale out/render_1024.png with an old sidecar beside it
# is measured and published as if it were the shipped artwork.
python3 tools/compare.py reference.png out/render_1024.png --out-prefix out/diff --json out/metrics.json --require-provenance
python3 tools/diagnose.py out/render_1024.png --json out/diagnostics.json --require-provenance
python3 tools/validate.py
python3 tools/make_previews.py out/render_1024.png

echo "== 4. regression checks =="
python3 -u tools/test_pipeline.py

echo "== 5. README =="
python3 tools/update_readme.py

echo "== 6. reproducibility =="
# The committed parameters must rebuild the committed SVG byte for byte.  This
# is the check that catches an optimiser that reported one state and saved
# another, which has happened.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
python3 src/build_svg.py --params src/params.json --out "$tmp/repro.svg" > /dev/null
if cmp -s "$tmp/repro.svg" reconstruction.svg; then
    echo "src/params.json reproduces reconstruction.svg exactly"
else
    echo "FAIL: src/params.json does not reproduce reconstruction.svg" >&2
    # POSIX sh: no process substitution.  Two plain files, then diff them.
    head -c 4000 "$tmp/repro.svg" > "$tmp/a.txt"
    head -c 4000 reconstruction.svg > "$tmp/b.txt"
    diff "$tmp/a.txt" "$tmp/b.txt" | head -20 >&2 || true
    exit 1
fi
echo "PUBLISH OK"
