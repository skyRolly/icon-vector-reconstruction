#!/bin/sh
# Separate product pipeline. The historical tools/publish.sh remains unchanged.
set -eu
cd "$(dirname "$0")/.."
python3 tools/export_product_icon.py
python3 tools/test_product_icon.py --cross-renderer
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate assets/anamorph/linux/tech.rolly.anamorph.desktop
else
    printf '%s\n' 'Linux launcher syntax: not checked (desktop-file-validate unavailable).'
fi
python3 tools/export_product_icon.py --check
