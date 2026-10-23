# Product icon engineering and handoff record

## Current approval and integration status — record updated 2026-10-24 (Asia/Shanghai)

The owner explicitly confirms that all five predecessor PRs are merged and their human
architecture reviews, ADR decisions and associated owner-decision items are approved in
**“Priority P0 — Record Final Owner Approvals and Close Outstanding Governance Decisions.”**
B0 remains accepted unchanged, as previously approved with design PR #10. The completed
Linux resource namespace decision is **Approved**; implementation is **Merged**. The
original final-approval date is **NOT RECORDED**; this is the record-update date.

| Completed scope | Actual merge commit |
|---|---|
| [icon-vector-reconstruction #12](https://github.com/skyRolly/icon-vector-reconstruction/pull/12), Linux handoff `tech.rolly.anamorph` | `233786d3922e7ea144de235db466924147ab213d` |
| [Anamorph #170](https://github.com/skyRolly/Anamorph/pull/170), Accepted ADR-0062 native JUCE inputs | `b4a95b3a6d86acf222de523c6fb04de23ad8e602` |
| [Anamorph #171](https://github.com/skyRolly/Anamorph/pull/171), Accepted ADR-0063 namespace | `b4ea7a2ac25b89b943d350a6bb0d42ccc6273727` |
| [Anamorph #172](https://github.com/skyRolly/Anamorph/pull/172), Accepted ADR-0064 stable uninstall icon | `1e17f5845a90919949435c60d6ddf2bf2bd3fde1` |
| [Anabasis #51](https://github.com/skyRolly/Anabasis/pull/51), Accepted ADR-0048 namespace `tech.rolly.anabasis` | `626eb9a04d8da37995eb66fcf2c8c1fe986f7989` |

Fetched icon main is `233786d3922e7ea144de235db466924147ab213d`, whose first parent is
`35cf982f9d2e33bde5c4a1bf84b17205ce1e6b80` and implementation parent is
`0309f9069268de515b518c8429094af55e4e5047`. Anamorph main is the #172 merge, with
#170 → #171 → #172 on its first-parent chain. Anabasis main is the #51 merge with
first parent `1a40afd190d6994e33cfa12ae3fca0f375d4687c`. These are verified merged
implementations, not pending adoption. No duplicate ADR is introduced here.

Evidence: icon [main product CI 40021007797](https://github.com/skyRolly/icon-vector-reconstruction/actions/runs/40021007797)
and [historical CI 40021007794](https://github.com/skyRolly/icon-vector-reconstruction/actions/runs/40021007794)
passed at the icon merge. Anamorph [native JUCE run 39970834429](https://github.com/skyRolly/Anamorph/actions/runs/39970834429)
passed on `84d74b4c332da76abce780d165d1ec57e41a6fce`. [Installer run 40011141822](https://github.com/skyRolly/Anamorph/actions/runs/40011141822)
at `cac80161f578dbd570631b3e5c2647f690a0c1ff` passed native B0 Setup/uninstaller
resources, six install/reinstall snapshots and three uninstalls; artifact 12526403791
ZIP SHA-256 is `520af953866654edf046cf9a2cba7d96c8598758d07a0365b4167b495348f28c`.
These checks do not establish Explorer/DPI appearance. Anamorph's JUCE-generated ICNS
validation does not validate this repository's distinct independent ICNS or a Composer project.

Owner/brand/design and completed-integration approval blockers are closed. Real DAW recall,
AU/VST3 discovery/cache behavior, human audition, actual macOS installation/receipt
registration, Finder/Dock, genuine Icon Composer appearances, Explorer/DPI, Linux GNOME/KDE
runtime appearance and Anabasis Windows runtime installation remain unverified for this work.
Future Linux/Composer architecture, shipping and unrelated owner decisions are not approved
by this reconciliation. The original dated design/native reports below, including
`design/final-review.json`, remain historical evidence; their former pending-approval and
no-integration wording is superseded by this current record.

Reconciliation validation: pinned numpy 2.4.6 / Pillow 13.0.0 / resvg-py 0.5.0;
91-file export and isolated `--check` rebuild match; all 15 product tests pass;
independent Inkscape 1.4 comparisons pass at 32/128/512/1024 px; the canonical Linux
launcher passes `desktop-file-validate`. All 89 non-index exported files are byte-identical
to inspected main, and design/historical inputs (including `design/final-review.json`)
are unchanged. Only status text, exporter status metadata and the two regenerated indices
change. All 68 local links in changed documentation resolve. Cross-repository ADR/index,
main-ancestry and protected-file audits pass. No runtime test is inferred from these checks.

## Historical design and validation record

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

The selected product is **published B0, unchanged after final review**, canonical source
`assets/anamorph/master/anamorph.svg`. Editable material/layout values live in
`design/anamorph.json`; existing reconstruction primitives are imported rather
than copied into another renderer.

The generated package has **91 files**: 59 PNGs, 24 SVGs, 3 supporting JSONs,
1 ICO, 1 ICNS, 1 desktop entry, plus the digest manifest and asset-matrix index.
The PNG count includes actual equal-scale review sheets, platform resources
and candidate/control renders. The final acceptance round adds four compact
review sheets and twelve constrained experiment SVGs; it does not add new
platform masters. All 47 platform/handoff files retain their published B0 bytes.

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

The initial 75-file B0 package rebuilt byte-for-byte at source revision
`fab84095b3c903c9d1c97449e8790b506f3c674e588d4307578a5ebd06c658a8`.
The final package's source revision and clean-rebuild result are recorded in
the generated manifest and measured report, including the new review sources.
The final `sh tools/publish_product_icon.sh` completed successfully: **all 91
files matched byte-for-byte**, source revision
`859d31a747a9a1ca0bf7bee8519ae4956fe676ecbf6ef091a8419575a08bfeb3`.

## Final acceptance round

Fetched and inspected PR #10 at head
`d231a7a42b3ae55af6d62031ba1c2a4d7343574f`, base `main`, head branch
`design/anamorph-icon-modernization`. Both `product-icon` and historical
`checks` workflows were successful on that exact head (push and PR runs).
There were no review submissions, discussion comments or inline threads.
The working tree was clean; remote main and backup were still at the original
commit/tree; Anamorph remained clean at the recorded read-only audit commit.
No branches or PRs were recreated. Auto-merge was disabled.

The [final visual record](PRODUCT_ICON_FINAL_REVIEW.md) captures observations
before experiments and the exact B1/B2/F1/F2/S1/S2 settings. Every refinement
was rejected after native-size inspection. B-final is B0, with no changes to
`design/anamorph.json` or `src/product_icon.py`. The master SHA-256 is
`9d944b2b04abeb92dddc6840cf949d126162169159e937f23a384160d0db56b4`;
the small SVG is
`88d56815ea3596a143e3609a99daaa1697ffff27e264bff855d866c131475acd`.

`design/final-review.json` pins the control configuration and all 47 production
and platform handoff digests. `tools/review_product_icon.py` reuses the existing
renderer and makes only in-memory experiment changes. The exporter includes
those sources and all four new sheets/twelve vectors in its exhaustive digest
manifest. It still builds from fresh vectors and rejects stale files.

The existing 13 product checks and every historical check remain intact. One
additional product check independently pins the unchanged B0 platform files
and control SVGs. No acceptance threshold was relaxed and no artwork was
adjusted to force a test to pass. Re-run the same product publish command;
current-head GitHub checks are the authority for the final commit's CI status.

The final product run passed **14 checks**, including all 47 unchanged handoff
digests. A negative control modified one pixel of a valid 16 px PNG in an
isolated temporary copy; the new B0 preservation check rejected it. Production
files were untouched. Independent Inkscape/resvg comparisons again passed at
32/128/512/1024, with the same measured differences as B0 below. Additional
256 px checks passed for opaque imagery (MAE .28800), full-bleed flat fallback
(.56564), left/right native foregrounds (.04824/.05649) and interaction
(.00317), all in 8-bit RGB units over black. These compare vector renderers,
not native Apple materials. `desktop-file-validate` and Python/shell syntax
also passed.

PNG corner alpha and light/dark composites were inspected at native sizes.
Transparent RGB is zeroed; antialias pixels have no visible bright/dark matte.
Equal alpha bounds are preserved, with subpixel insets naturally reaching the
canvas at 16/24. ICO/ICNS actual decoded pixels, not only filenames/container
headers, are checked against the direct raster sources. Linux hicolor PNGs
match those sources, while scalable SVG equals the regular master. Desktop
selection of scalable SVG at tiny sizes may bypass the optical variant and
remains a native session check.

The Apple mask/source study confirms the independent pre-rounded body is
distinct from full-bleed flat input and unmasked crisp foreground layers.
Only the mathematical preview applies an approximate mask. No real `.icon`
project, `iconutil` validation or native Liquid Glass rendering is claimed.

Recommendation: **category 2, ready with documented non-blocking native-platform
limitations**, as an independent icon-design baseline after current-head CI
passes. That was the design-stage recommendation; B0 approval, #10/#12 merges and
Anamorph's completed integration are now recorded above. Shipping remains separate.

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
desktop-file-validate assets/anamorph/linux/tech.rolly.anamorph.desktop
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

- Owner brand choice: B0 is accepted unchanged; A/C remain the earlier archive.
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

The original reconstruction and backup remain preserved. The original design and
completed integration PRs are merged as recorded above; no pending brand/merge decision
remains for that scope. This reconciliation grants no release or future architecture approval.

## Linux resource namespace — 2026-10-23

The current handoff uses `tech.rolly.anamorph`, from the owner's `rolly.tech`
domain: the desktop filename/Icon field, eight hicolor PNG basenames and the
scalable SVG basename agree. Export definitions, the generated digest inventory,
launcher validator and integration commands use the same names. The earlier
inspection and `design/final-review.json` remain historical evidence.

Starting main: `35cf982f9d2e33bde5c4a1bf84b17205ce1e6b80`. Regenerating with the
pinned pipeline produces 91 reproducible files. Every PNG, SVG, ICO and ICNS is
byte-identical to that main, including all nine renamed Linux images; the only
changed asset contents are the desktop Icon field and the two generated indices.
The historical review guard still checks every old digest; only the intentional
desktop field rename is reversed for that historical hash comparison. A separate
namespace test requires the exact current file set and matching portable pixels.

Validation: 15 product tests, `export_product_icon.py --check`,
`desktop-file-validate`, and independent Inkscape 1.4 comparisons at 32/128/512/1024
pass with the pinned Python dependencies. Historical reconstruction/master/design
files and the backup branch are unchanged. No desktop installation, icon cache,
GNOME/KDE/WM session or native Apple/Windows display result is claimed. This PR
changes resource names only; plugin namespace/installer work is reviewed separately.

The prepared local environment initially carried Pillow 12.3.0 while current
requirements.txt pins **13.0.0**. CI rejected only that manifest dependency
field; no image differed. Regenerated with the actual declared pins
(numpy 2.4.6 / Pillow 13.0.0 / resvg-py 0.5.0), repeated the reproducible export,
15 tests and Inkscape checks, and re-compared every visual byte against starting
main. The source dependency declarations and all visual assets remain unchanged.
