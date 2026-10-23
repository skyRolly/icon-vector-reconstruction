# Future Anamorph icon integration plan — READ ONLY audit

**Integration has NOT been performed.** No files, build settings, installers,
icons, commits, PRs or releases in `skyRolly/Anamorph` were changed. This plan
requires a separate owner instruction before implementation.

The final B acceptance round retains all platform handoff bytes unchanged.
Its [masking/source audit](PRODUCT_ICON_FINAL_REVIEW.md#geometry-masking-and-export-interpretation)
confirms distinct conventional and native Apple inputs. The matrix below
remains an integration plan, with the same native validation requirements;
none of its future hooks was applied to Anamorph.

## Inspected implementation

- Current remote main, confirmed with `git ls-remote`:
  **`c4f390f9cccaa9551d680cb1305fa4a669b24587`** (Anamorph 0.9.9).
- [`CMakeLists.txt` at that commit](https://github.com/skyRolly/Anamorph/blob/c4f390f9cccaa9551d680cb1305fa4a669b24587/CMakeLists.txt#L411):
  VST3 on all desktop platforms, AU additionally on Apple, Standalone enabled
  by default. No VST2, AAX, AUv3, LV2, CLAP or iOS application target is shipped.
- JUCE **9.0.4**, immutable dependency
  `3fb5cbc0340758596dac39f7c8de47d562b4896e`. `juce_add_plugin(Anamorph)` sets
  RollyTech, product Anamorph, bundle ID `com.rollytech.anamorph` and frozen
  plug-in codes. No `ICON_BIG`, `ICON_SMALL` or `ICON_COMPOSER_BUNDLE` is set;
  no existing product PNG/SVG/ICO/ICNS resource was found in the tracked tree.
- [`build.yml`](https://github.com/skyRolly/Anamorph/blob/c4f390f9cccaa9551d680cb1305fa4a669b24587/.github/workflows/build.yml):
  Linux x86-64, Windows x86-64, macOS universal arm64+x86_64. Existing x86 ISA
  requirements and all DSP/serialization/host identity constraints are outside
  icon integration scope.
- Packaging: flat manual/portable ZIPs per OS; Windows Inno Setup 6 executable;
  macOS component-selectable `.pkg`; Linux `install.sh`/`uninstall.sh` inside
  the ZIP. Release workflow archives the validated staging tree; installers
  are moved unchanged. No DMG, MSI, AppImage, deb or rpm is produced.
- macOS bundles are stripped, universal and ad-hoc signed in staging; the
  inspected release pipeline is not Developer-ID/notarized. Windows installer
  is not Authenticode signed. Icon changes must precede existing signing and
  staging validation, never patch a signed bundle afterward.
- About panel in `src/PluginEditor.cpp` is text and existing glass rendering;
  there is no product-logo slot or splash screen that needs an icon asset.

## Verified JUCE hooks

The **pinned dependency source**, rather than current JUCE docs for a different
release, was inspected:
[`JUCEUtils.cmake`](https://github.com/juce-framework/JUCE/blob/3fb5cbc0340758596dac39f7c8de47d562b4896e/extras/Build/CMake/JUCEUtils.cmake#L650).

- `ICON_BIG` / `ICON_SMALL` supply raster inputs to `juceaide macicon/winicon`.
  macOS generates `AppIcon.icns` (or the Composer icon name), marks it as a
  bundle resource and records `JUCE_ICON_FILE`. Windows generates `icon.ico`
  and a shared `.rc` object via `_juce_add_resources_rc`.
- `_juce_create_windows_package` writes VST3 `Plugin.ico` and `desktop.ini`
  pointing to it, then sets Windows system attributes. Those Explorer folder
  attributes and caching need verification through both ZIP and Inno routes.
- `ICON_COMPOSER_BUNDLE` is a real supported argument in this pinned version.
  Its Xcode-generator path includes the `.icon` folder as an icon-composer
  resource and sets the asset-catalog icon name. Its non-Xcode Darwin path
  invokes `generateXcassetsFromIcon.cmake` / `xcrun actool` (26+ checked).
  That path's target-variable expansion and the actual Anamorph Ninja/CI
  generator require a native configure/build test; code presence is not proof
  that this combination works. No native project is supplied by this PR.
- Linux has no equivalent ELF icon resource branch in `_juce_generate_icon`.
  A desktop entry and installed icon theme are required for launchers. A native
  JUCE window icon is a separate runtime/WM check, not guaranteed by CMake flags.

## Integration-target matrix

Status describes capability; **none of these future changes is implemented**.

| Platform / target | Classification | Prepared input / future hook | Validation still needed |
|---|---|---|---|
| macOS Standalone `.app`, Finder, Dock | Supported with build changes | Conventional PNG inputs through `ICON_BIG/SMALL`, or approved native `.icon` after Composer validation; inspect `Contents/Resources/AppIcon.icns` and `CFBundleIconFile` | Native build, plist/resource extraction, Finder/Dock at small/large sizes, cache refresh |
| macOS VST3 bundle file icon | Platform dependent, supported with build changes | Same JUCE conventional bundle resource hook; `Anamorph.vst3/Contents/Resources` | Finder and host scan; no DAW icon guarantee |
| macOS AU `.component` file icon | Platform dependent, supported with build changes | JUCE generated bundle icon/resource/plist for AU | Finder, `auval`, Logic/GarageBand scanning; host list may stay text/generic |
| macOS `.pkg` Finder file icon | Unsupported as a standard Distribution-XML ICNS hook | Keep normal Installer package file icon; extended-attribute custom Finder icons are not a portable release contract | Native productbuild/Finder test if owner requests nonstandard customization |
| macOS Installer UI | Supported with packaging changes, optional | Existing `build-pkg.sh` has no `<background>` or `--resources`; a future resource/background can use selected opaque artwork | Native Installer UI on light/dark displays; no extra artwork generated without a layout need |
| Windows Standalone `.exe` / Explorer | Supported with build changes | JUCE `ICON_BIG/SMALL` → ICO → generated RC resource | Inspect PE `RT_GROUP_ICON/RT_ICON` resources and Explorer sizes |
| Windows Start Menu / Taskbar | Directly supported once EXE icon is configured; runtime verification pending | Existing Inno shortcut points to `{app}\Anamorph.exe`, without a custom `IconFilename`; taskbar normally follows application/window identity | Launch from shortcut/EXE, pin/unpin, native-window/taskbar behavior at 100–250% DPI |
| Windows VST3 Explorer bundle icon | Supported with build/packaging changes; platform dependent | JUCE `Plugin.ico` / `desktop.ini`; preserve/set directory and INI system attributes when installing | Explorer after ZIP extraction and Inno install; resource presence alone does not ensure folder-icon display |
| Windows DAW plug-in list | Host controlled | No portable VST3 icon slot guarantees a DAW's browser artwork | Test each intended host; no promise that custom binary/folder resources will be used |
| Inno Setup installer executable | Supported with packaging changes | Add `SetupIconFile` pointing to prepared `windows/Anamorph.ico` | Native ISCC build and setup/uninstall icon inspection |
| Windows uninstall entry / uninstaller | Directly supported existing EXE reference; installer icon hook also relevant | Existing `UninstallDisplayIcon={app}\Anamorph.exe`; `SetupIconFile` also affects Setup/Uninstall | Check VST3-only installation: EXE is absent, so future packaging must provide a stable installed icon for that selection |
| Inno wizard artwork | Supported but optional; not selected | Current `WizardStyle=modern`, no custom wizard image. Current Inno supports PNG/BMP and 164:314 image-area aspect ratio | Avoid an unnecessary vertical banner; if requested, create a dedicated layout and check current compiler/DPI behavior |
| Linux Standalone ELF file | Unsupported as a portable embedded file-icon convention | Keep executable; use launcher/icon-theme resources | File managers and JUCE native-window/WM behavior need runtime checks |
| Linux application launcher / desktop entry | Supported with packaging changes | `linux/com.rollytech.anamorph.desktop` and `linux/hicolor` PNG/SVG | `desktop-file-validate`; launch under GNOME/KDE, icon lookup, WM/taskbar identity, per-user/system install and uninstall |
| Linux VST3 bundle/host list | Host controlled / not verified for custom folder artwork | No icon injection found in JUCE Linux VST3 layout; bundle contains `Contents/x86_64-linux/Anamorph.so` and metadata | Native host/browser test; do not install a global generic VST3 MIME override for this product |
| Portable/manual ZIP | Supported with packaging changes | Existing executable/bundle resources travel with payload; Linux launcher/theme files would need staging and install/uninstall handling | Archive inventory, platform permissions/Windows attributes and actual launch after extraction |
| Downloads, docs, GitHub presentation | Directly usable artwork, pending brand approval | Master SVG/opaque or rounded PNG; before/after sheet is review imagery | Owner choice and correct background/scale; no automatic publication |
| About / splash | No existing integration slot; not selected | Current About panel remains as designed | Separate UI design request if desired |

Host control is independent of filesystem icon support. AU metadata does not
provide a universal image for all host plug-in lists; VST3 directory icons are
not a cross-DAW branding API. Those targets are retained in this matrix rather
than silently omitted.

## Exact inputs and proposed future destinations

Paths on the left are in **this repository** under `assets/anamorph/`.
Destinations are proposed paths in Anamorph, not files that were created there.

| Prepared asset | Proposed Anamorph destination | Future consumer |
|---|---|---|
| `master/anamorph-rounded-1024.png` | `resources/icons/anamorph-1024.png` | `ICON_BIG`, conventional desktop route |
| `portable/png/anamorph-32.png` | `resources/icons/anamorph-32.png` | `ICON_SMALL`; inspect JUCE's generated tiny frames against supplied direct renders |
| `windows/Anamorph.ico` | `resources/icons/windows/Anamorph.ico` | Inno `SetupIconFile`; optional explicit RC route if exact prepared frames are required |
| `macos/Anamorph.icns`, `macos/Anamorph.iconset/` | `resources/icons/macos/` | Validated fallback/reference and native iconutil round-trip; JUCE normally regenerates its own ICNS |
| `apple/layers/`, `apple/import-manifest.json` | `resources/icons/apple/source/` | Native Composer authoring; do not pass the manifest to Xcode as a project |
| **Future native-validated** `Anamorph.icon` | `resources/icons/apple/Anamorph.icon` | `ICON_COMPOSER_BUNDLE` after native CI/generator verification |
| `linux/hicolor/` | `resources/icons/linux/hicolor/` | Stage to `$XDG_DATA_HOME/icons/hicolor` or `/usr/local/share/icons/hicolor` |
| `linux/com.rollytech.anamorph.desktop` | `packaging/linux/com.rollytech.anamorph.desktop` | Install to `$XDG_DATA_HOME/applications` or `/usr/local/share/applications` |
| `master/anamorph.svg`, opaque/rounded PNGs | `docs/assets/anamorph/` if approved | Documentation/presentation only |

## Future implementation sequence

1. Obtain brand choice and **separate authorization to change Anamorph**. Create
   a new integration branch there and record its new starting commit; this
   audit is a snapshot, not an instruction to overwrite future main changes.
2. Copy approved inputs to the proposed paths, recording this icon PR's source
   revision and asset digests. Add `ICON_BIG`/`ICON_SMALL` to `juce_add_plugin`
   without changing formats, bundle/plugin IDs, DSP code or compatibility data.
3. Add the Inno `SetupIconFile` hook. For VST3-only installs, place an icon in
   a stable installed location and point `UninstallDisplayIcon` to it instead
   of an absent optional EXE. Ensure uninstall removes only the new owned files.
4. Add Linux launcher/theme staging and symmetric install/uninstall handling.
   Honor `$XDG_DATA_HOME` (fallback `~/.local/share`) for per-user installation;
   use `/usr/local/share` for system-local data. Current executable destinations
   remain `~/.local/bin/Anamorph` and `/usr/local/bin/Anamorph`; VST3 destinations
   remain `~/.vst3` and `/usr/lib/vst3`. Verify launcher PATH lookup; use an
   actual installed absolute executable path if the desktop session lacks it.
5. Keep macOS installer destinations `/Applications`,
   `/Library/Audio/Plug-Ins/VST3`, `/Library/Audio/Plug-Ins/Components` and Windows
   destinations Program Files/Anamorph and Common Files/VST3. Do not introduce
   package UI artwork just to consume an available PNG.
6. Run the native checks in the matrix and existing Anamorph release gates.
   Compare regenerated JUCE ICO/ICNS against the prepared source; confirm no
   image became double-masked. Perform signing after resource generation.
7. Consider the native Composer hook only after the genuine project and the
   current non-Xcode build path are validated. Inspect default/dark/clear/tint
   and older macOS fallback, in addition to normal audio plug-in validation.

## Rollback

Revert the future integration commit(s), restore the previous CMake icon
configuration and packaging resource list, remove only files introduced by
that integration, and rebuild/re-sign/repackage. Reinstall the previous validated
bundles/executable and refresh OS icon caches/shortcuts as necessary. Do not
modify plug-in IDs, user presets or saved sessions. The original icon repository
tree is separately recoverable from `backup/pre-anamorph-icon-design-20261023`.

## Additional primary references

- [Inno Setup SetupIconFile](https://jrsoftware.org/ishelp/topic_setup_setupiconfile.htm):
  recommended 16/32/48/64/256 entries are all present in the prepared 9-frame ICO.
- [Inno WizardImageFile](https://jrsoftware.org/ishelp/topic_setup_wizardimagefile.htm):
  current sizing/DPI rules; older fixed-pixel assumptions were not reused.
- [Apple Distribution XML background element](https://developer.apple.com/library/archive/documentation/DeveloperTools/Reference/DistributionDefinitionRef/Chapters/Distribution_XML_Ref.html):
  Installer UI background is distinct from the `.pkg` file icon.
- [Freedesktop icon theme specification](https://specifications.freedesktop.org/icon-theme/latest/):
  PNG/scalable SVG and hicolor fallback. SVG support is optional, so PNG sizes
  are provided too.

Unknown native behavior is explicitly a future test above. A passing icon
export or design review does not authorize copying anything into Anamorph.
