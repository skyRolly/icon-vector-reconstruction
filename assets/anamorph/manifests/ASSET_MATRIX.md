# Generated asset inventory

Rebuild with `python tools/export_product_icon.py`. All dimensions are pixels unless noted. Native platform validation and brand approval remain pending. `assets.json` records every content digest. The inventory and digest index exclude themselves to avoid circular hashes.

| Path | Format | Dimensions | Alpha | Color space | Target | Validation |
|---|---|---|---|---|---|---|
| `apple/Assets.xcassets/AppIcon.appiconset/Anamorph-1024.png` | PNG | [1024, 1024] | no | sRGB | Optional iOS 1024 px flat fallback; Anamorph currently has no iOS target | Opaque RGB/sRGB validated; actool pending |
| `apple/Assets.xcassets/AppIcon.appiconset/Contents.json` | JSON | n/a | format/source dependent | n/a | Optional current iOS flat fallback asset catalog | JSON validated; actool pending |
| `apple/Assets.xcassets/Contents.json` | JSON | n/a | format/source dependent | n/a | Optional current iOS flat fallback asset catalog | JSON validated; actool pending |
| `apple/import-manifest.json` | JSON | n/a | format/source dependent | n/a | Human-readable import handoff; not an Apple project format | structurally validated |
| `apple/layers/01-left.svg` | SVG | [1024, 1024] | yes | sRGB | Icon Composer foreground import | SVG structure validated; native import/materials pending |
| `apple/layers/02-right.svg` | SVG | [1024, 1024] | yes | sRGB | Icon Composer foreground import | SVG structure validated; native import/materials pending |
| `apple/layers/03-interaction.svg` | SVG | [1024, 1024] | yes | sRGB | Icon Composer foreground import | SVG structure validated; native import/materials pending |
| `linux/com.rollytech.anamorph.desktop` | DESKTOP | n/a | format/source dependent | n/a | Future launcher template; executable must be installed on PATH | desktop-file-validate checked separately; not installed |
| `linux/hicolor/128x128/apps/com.rollytech.anamorph.png` | PNG | [128, 128] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/16x16/apps/com.rollytech.anamorph.png` | PNG | [16, 16] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/24x24/apps/com.rollytech.anamorph.png` | PNG | [24, 24] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/256x256/apps/com.rollytech.anamorph.png` | PNG | [256, 256] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/32x32/apps/com.rollytech.anamorph.png` | PNG | [32, 32] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/48x48/apps/com.rollytech.anamorph.png` | PNG | [48, 48] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/512x512/apps/com.rollytech.anamorph.png` | PNG | [512, 512] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/64x64/apps/com.rollytech.anamorph.png` | PNG | [64, 64] | yes | sRGB | Freedesktop icon theme / launcher | structurally validated |
| `linux/hicolor/scalable/apps/com.rollytech.anamorph.svg` | SVG | [1024, 1024] | yes | sRGB | Freedesktop scalable icon | structurally validated |
| `macos/Anamorph.icns` | ICNS | [16, 32, 64, 128, 256, 512, 1024] | yes | sRGB tagged PNG frames | Finder/Dock/bundle conventional fallback | Pillow decode and chunk validation; macOS iconutil/Finder pending |
| `macos/Anamorph.iconset/icon_128x128.png` | PNG | [128, 128] | yes | sRGB | macOS conventional iconset: 128 pt at 1x | structurally validated |
| `macos/Anamorph.iconset/icon_128x128@2x.png` | PNG | [256, 256] | yes | sRGB | macOS conventional iconset: 128 pt at 2x | structurally validated |
| `macos/Anamorph.iconset/icon_16x16.png` | PNG | [16, 16] | yes | sRGB | macOS conventional iconset: 16 pt at 1x | structurally validated |
| `macos/Anamorph.iconset/icon_16x16@2x.png` | PNG | [32, 32] | yes | sRGB | macOS conventional iconset: 16 pt at 2x | structurally validated |
| `macos/Anamorph.iconset/icon_256x256.png` | PNG | [256, 256] | yes | sRGB | macOS conventional iconset: 256 pt at 1x | structurally validated |
| `macos/Anamorph.iconset/icon_256x256@2x.png` | PNG | [512, 512] | yes | sRGB | macOS conventional iconset: 256 pt at 2x | structurally validated |
| `macos/Anamorph.iconset/icon_32x32.png` | PNG | [32, 32] | yes | sRGB | macOS conventional iconset: 32 pt at 1x | structurally validated |
| `macos/Anamorph.iconset/icon_32x32@2x.png` | PNG | [64, 64] | yes | sRGB | macOS conventional iconset: 32 pt at 2x | structurally validated |
| `macos/Anamorph.iconset/icon_512x512.png` | PNG | [512, 512] | yes | sRGB | macOS conventional iconset: 512 pt at 1x | structurally validated |
| `macos/Anamorph.iconset/icon_512x512@2x.png` | PNG | [1024, 1024] | yes | sRGB | macOS conventional iconset: 512 pt at 2x | structurally validated |
| `master/anamorph-apple-square.svg` | SVG | [1024, 1024] | no | sRGB | Unmasked full-bleed flat fallback; not layered native source | structurally validated |
| `master/anamorph-opaque-1024.png` | PNG | [1024, 1024] | no | sRGB | Vector-derived 1024 px master raster | structurally validated |
| `master/anamorph-opaque.svg` | SVG | [1024, 1024] | no | sRGB | Opaque precomposed square for imagery | structurally validated |
| `master/anamorph-rounded-1024.png` | PNG | [1024, 1024] | yes | sRGB | Vector-derived 1024 px master raster | structurally validated |
| `master/anamorph-small.svg` | SVG | [1024, 1024] | yes | sRGB | 16–32 px optical master | structurally validated |
| `master/anamorph-square-1024.png` | PNG | [1024, 1024] | no | sRGB | Vector-derived 1024 px master raster | structurally validated |
| `master/anamorph.svg` | SVG | [1024, 1024] | yes | sRGB | Canonical independent product master | structurally validated |
| `portable/png/anamorph-1024.png` | PNG | [1024, 1024] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-128.png` | PNG | [128, 128] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-16.png` | PNG | [16, 16] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-20.png` | PNG | [20, 20] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-24.png` | PNG | [24, 24] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-256.png` | PNG | [256, 256] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-32.png` | PNG | [32, 32] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-40.png` | PNG | [40, 40] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-48.png` | PNG | [48, 48] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-512.png` | PNG | [512, 512] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `portable/png/anamorph-64.png` | PNG | [64, 64] | yes | sRGB | Portable imagery / cross-platform icon input | structurally validated |
| `previews/apple-layers-flat.png` | PNG | [900, 624] | no | sRGB | Review: actual native SVG foreground geometry without masking or system material; native effects pending | structurally validated |
| `previews/before-after.png` | PNG | [1120, 620] | no | sRGB | Review and release/documentation illustration | structurally validated |
| `previews/candidates/A-1024.png` | PNG | [1024, 1024] | yes | sRGB | Full-resolution candidate review | structurally validated |
| `previews/candidates/A.svg` | SVG | [1024, 1024] | yes | sRGB | Editable alternative for owner review | structurally validated |
| `previews/candidates/B-1024.png` | PNG | [1024, 1024] | yes | sRGB | Full-resolution candidate review | structurally validated |
| `previews/candidates/B.svg` | SVG | [1024, 1024] | yes | sRGB | Editable alternative for owner review | structurally validated |
| `previews/candidates/C-1024.png` | PNG | [1024, 1024] | yes | sRGB | Full-resolution candidate review | structurally validated |
| `previews/candidates/C.svg` | SVG | [1024, 1024] | yes | sRGB | Editable alternative for owner review | structurally validated |
| `previews/candidates/square-baseline-1024.png` | PNG | [1024, 1024] | yes | sRGB | Full-resolution candidate review | structurally validated |
| `previews/candidates/square-baseline.svg` | SVG | [1024, 1024] | yes | sRGB | Editable alternative for owner review | structurally validated |
| `previews/comparison-1024-light.png` | PNG | [6336, 1124] | no | sRGB | Review: all designs at native 1024 px on light desktop | structurally validated |
| `previews/comparison-1024.png` | PNG | [6336, 1124] | no | sRGB | Review: all designs at native 1024 px on dark desktop | structurally validated |
| `previews/comparison-128-dark.png` | PNG | [1080, 228] | no | sRGB | Review: native 128 px on dark desktop | structurally validated |
| `previews/comparison-128-light.png` | PNG | [1080, 228] | no | sRGB | Review: native 128 px on light desktop | structurally validated |
| `previews/comparison-16-dark.png` | PNG | [1080, 116] | no | sRGB | Review: native 16 px on dark desktop | structurally validated |
| `previews/comparison-16-light.png` | PNG | [1080, 116] | no | sRGB | Review: native 16 px on light desktop | structurally validated |
| `previews/comparison-32-dark.png` | PNG | [1080, 132] | no | sRGB | Review: native 32 px on dark desktop | structurally validated |
| `previews/comparison-32-light.png` | PNG | [1080, 132] | no | sRGB | Review: native 32 px on light desktop | structurally validated |
| `previews/comparison-512-light.png` | PNG | [3264, 612] | no | sRGB | Review: all designs at native 512 px on light desktop | structurally validated |
| `previews/comparison-512.png` | PNG | [3264, 612] | no | sRGB | Review: all designs at native 512 px on dark desktop | structurally validated |
| `previews/comparison-64-dark.png` | PNG | [1080, 164] | no | sRGB | Review: native 64 px on dark desktop | structurally validated |
| `previews/comparison-64-light.png` | PNG | [1080, 164] | no | sRGB | Review: native 64 px on light desktop | structurally validated |
| `previews/corner-study.png` | PNG | [1140, 440] | no | sRGB | Review: equal square bounds/radius, alternative corner curvature; not a system mask | structurally validated |
| `previews/final/B0-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/B0.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/B1-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/B1.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/B2-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/B2.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/F1-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/F1.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/F2-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/F2.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/S1-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/S2-small.svg` | SVG | [1024, 1024] | yes | sRGB | Final review experiment; not a selected platform asset | structurally validated |
| `previews/final/backgrounds.png` | PNG | [1080, 1560] | no | sRGB | Final native 16..256 exports on four backgrounds and labelled simulated launcher | structurally validated |
| `previews/final/before-after.png` | PNG | [900, 360] | no | sRGB | Historical / B0 / selected final, equal native 256 px | structurally validated |
| `previews/final/candidates.png` | PNG | [1140, 1568] | no | sRGB | Constrained B boundary, flare and small factors, native pixels on light/dark | structurally validated |
| `previews/final/masking.png` | PNG | [1168, 400] | no | sRGB | Independent / full-bleed flat / unmasked native layers / approximate mask, no Apple effects | structurally validated |
| `previews/masking-comparison.png` | PNG | [1120, 620] | no | sRGB | Review: approximate system enclosure versus precomposed icon; native mask pending | structurally validated |
| `previews/selected-size-ladder.png` | PNG | [1140, 2300] | no | sRGB | Review: selected master and small variant at native sizes | structurally validated |
| `previews/small-optical-comparison.png` | PNG | [1200, 380] | no | sRGB | Review: same geometry with reduced glow/rays and stronger curve cores | structurally validated |
| `windows/Anamorph.ico` | ICO | [16, 20, 24, 32, 40, 48, 64, 128, 256] | yes | sRGB source samples; embedded PNG frames untagged | EXE / Explorer / Start Menu / Taskbar / Inno Setup SetupIconFile | All directory entries and decoded pixels validated; Windows resource/ISCC pending |
