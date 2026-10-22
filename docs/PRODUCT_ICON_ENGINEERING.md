# Product icon engineering and handoff record

## Repository safety

| Item | Recorded state |
|---|---|
| Starting remote `main` | `0e39f2421dd1256e6224b117b63d6933ca55e0b5` — actual PR #9 merge / D78 state |
| Starting tree | `a7df69dfffc12f4c745771089d61db9fa2fef67b` |
| Remote recovery branch | `backup/pre-anamorph-icon-design-20261023` at exactly the starting commit/tree |
| Backup verification | Remote ref compared; branch checked out in a temporary worktree, clean and identical; recovery checkout removed, branch retained |
| Design branch | `design/anamorph-icon-modernization`, created and pushed separately from the exact starting commit |
| Initial working tree | Clean; no unrelated uncommitted changes, tags or open icon-repository PRs found |
| Anamorph inspected read-only | `c4f390f9cccaa9551d680cb1305fa4a669b24587`, confirmed as current remote main |

The original reconstruction remains the root deliverable. Its unchanged SHA-256
digests are:

| File | SHA-256 |
|---|---|
| `reference.png` | `cf35ca00fa38d263d734b44fb7a1ba21080b0e25487fcb8a1d2cf48389a9a4a7` |
| `reconstruction.svg` | `68dc93919a4cc9dbdcea1e2a984e0dc193955b122babe37245b4d5edcc786586` |
| `src/params.json` | `c651f3874fc5c321a91c4d469c5e0dc31a2f552594f8cab7125e460bbb701de5` |
| `src/build_svg.py` | `496b6f4e97efbc46d3885e0e0f241224716671ec9ef9c38ddd57497cd709ede2` |

`design/baseline.json` pins all 354 pre-existing files other than README, which
only gains a separate product-design section. Historical outputs, tests,
publish/render utilities, parameters, reference, method and decision records
are protected by content digest; no history is rewritten.

## Package and reproducibility

The selected product is **B**, canonical source
`assets/anamorph/master/anamorph.svg`. Editable material/layout values live in
`design/anamorph.json`; existing reconstruction primitives are imported rather
than copied into another renderer.

The generated package has **75 files**: 55 PNGs, 12 SVGs, 3 supporting JSONs,
1 ICO, 1 ICNS, 1 desktop entry, plus the digest manifest and asset-matrix index.
The PNG count includes actual equal-scale review sheets, platform resources
and four candidate/control renders, not 54 unrelated masters.

- PNG matrix: 16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024 px.
- ICO: 9 independently verified PNG frames, 16/20/24/32/40/48/64/128/256.
- ICNS: 11 standard image slots spanning 16..1024 actual pixels, including
  Retina slots and explicit `icp4/icp5/icp6` small entries. Pillow writes the
  base container; the exporter supplies standard small PNG elements and a
  consistent table of contents. Every decoded frame matches its vector-derived
  PNG. Native `iconutil` validation remains pending.
- Conventional macOS iconset: all ten 16..512 pt, 1x/2x source filenames.
- Apple: three crisp numbered SVG layers, background/appearance handoff,
  unmasked flat square source and optional opaque RGB single-1024 iOS catalog.
  No fabricated `.icon` file or `Assets.car` is shipped.
- Linux: PNG hicolor directories, scalable SVG, desktop-entry template.

See the exhaustive [asset matrix](../assets/anamorph/manifests/ASSET_MATRIX.md)
for every path, dimension, alpha/color interpretation, use and validation status.
The [manifest](../assets/anamorph/manifests/assets.json) pins production source
content and exact versions: numpy 2.4.6, Pillow 12.3.0, resvg-py 0.5.0.

The source revision is a digest of named source-file digests, with the original
base commit recorded separately. It therefore does not falsely label new
uncommitted artwork as coming from an old Git commit, or change merely because
the final export is committed. Export staging never reads previously generated
PNGs; sources changing during export cause failure. `--check` compares all
regenerated file bytes and rejects missing, extra or stale files.

The completed clean rebuild matched **all 75 files byte-for-byte**, source
revision `fab84095b3c903c9d1c97449e8790b506f3c674e588d4307578a5ebd06c658a8`.

## Validation record

Final measured results are in [PRODUCT_ICON_VALIDATION.json](PRODUCT_ICON_VALIDATION.json).
The review uses geometry/format/reproduction checks and visual inspection,
without a product-versus-reference pixel-error objective.

The historical publish cycle completed with **82 regression checks passed**
and a byte-identical reconstruction rebuild; its optional Chromium check did
not execute successfully, as detailed below. After preserving the accepted
historical reports, **all 13 product checks passed**, independent Inkscape
checks passed at all four sizes, and `desktop-file-validate` passed. The final
remote backup/main refs and the clean Anamorph tree were verified again before
submission.

Commands:

```sh
python -m pip install -r requirements.txt
python tools/setup_baseline.py
sh tools/publish.sh
python tools/export_product_icon.py
python tools/export_product_icon.py --check
python tools/test_product_icon.py --cross-renderer --engine inkscape --report docs/PRODUCT_ICON_VALIDATION.json
desktop-file-validate assets/anamorph/linux/com.rollytech.anamorph.desktop
```

`sh tools/publish_product_icon.sh` is the single product publish command: it
generates, validates formats/geometry and independent rendering, checks the
launcher when its optional validator is installed, and proves a clean rebuild.
It never calls the historical publish workflow or updates historical artifacts.

The product suite checks historical digests/byte-identical rebuild, deterministic
candidate SVGs, square visual/alpha geometry, SVG IDs/references and absence of
bitmap embedding, complete/current manifests, PNG dimensions/sRGB, clean
transparent pixels, opaque Apple fallback, unmasked native layers, actual
ICO offsets/frames/pixels, ICNS lengths/TOC/frames/profiles/pixels, catalog and
iconset contents, reproducible small renders, curve visibility away from the
flare, and highlight budget.

Independent resvg/Inkscape 1.4 comparisons measured mean absolute RGB error
(8-bit units) of **0.81579 at 32**, **0.33900 at 128**, **0.25636 at 512**,
**0.22824 at 1024**. At 32 px, 99th-percentile channel error is 12 and maximum
24; at 1024 they are 4 and 30. These differences are explicitly recorded, not
called pixel identity. The review threshold is MAE ≤3/255 at every checked
size; exceeding it fails and requires investigation. Fine antialias/filter
differences still merit native visual review before shipping.

Desktop Chromium 154 is present but failed or timed out during headless startup
in this environment. The historical publish command correctly reports its
optional cross-engine failure; its renderer was not edited. Independent product
validation uses the working Inkscape renderer. Historical reports generated by
the environment-specific publish attempt are kept out of the design change so
the original accepted artifacts remain intact; this does not claim a new
Chromium validation. Optional Inkscape/Chromium is needed only for the second
opinion, not for product export.

`.github/workflows/checks.yml` is unchanged. The separate `product-icon.yml`
rebuilds the entire package, runs the product checks with Inkscape and validates
the Linux launcher. GitHub's live checks on the review PR are the authority for
CI completion; local validation is not represented as a remote CI result.

## Limits and owner decisions

- Owner brand choice: B is recommended, with A/C and layout control retained.
- Native Composer import, material tuning, all six iOS/macOS 27 appearances,
  exact system masking and older-OS fallback remain unverified.
- Xcode/actool/catalog and native iconutil; JUCE `.app`/VST3/AU resources,
  Finder/Dock; Windows PE resources/ISCC/shortcuts/uninstall; Linux desktop/WM
  behavior have not been exercised on their target desktops.
- Binary formats are validated structurally and by decoded pixel content on
  Linux; they are not labelled native-packaging-certified.
- Anamorph currently ships VST3+Standalone on desktop, plus macOS AU. iOS
  assets do not imply an iOS product. Host-controlled plug-in lists may ignore
  all custom icons.
- No deployment, adoption, integration, main-branch change or PR merge is
  authorized by this report. The [integration plan](ANAMORPH_ICON_INTEGRATION_PLAN.md)
  specifies the future hooks, destinations, validations and rollback procedure.

Anamorph is unchanged. The original reconstruction is available in main, the
backup and this design branch. The design PR must remain open and unmerged for
human review; auto-merge must remain disabled.
