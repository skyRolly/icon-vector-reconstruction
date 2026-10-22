# Apple icon source preparation — iOS/macOS 27

Reviewed 2026-10-23. **Prepared for native tooling; no validated `.icon` project
or native platform compliance certification is claimed.** The Linux environment
has no Icon Composer, Xcode, `actool`, `iconutil`, Simulator or Apple device.

## Official sources and what they establish

| Official source | Relevant current guidance | Package response |
|---|---|---|
| [HIG: App icons](https://developer.apple.com/design/human-interface-guidelines/app-icons) | Square 1024 px layouts for iOS/iPadOS/macOS; unmasked layers, opaque full-bleed background, coherent identity across six appearances; sRGB is supported | 1024 px crisp vector foreground layers, separate background recipe; no native corner alpha mask |
| [Apple Design Resources](https://developer.apple.com/design/resources/) | Current iOS 27 app-icon production template and macOS 27 resources | Current template downloaded and inspected; its artwork is not redistributed |
| [Icon Composer](https://developer.apple.com/icon-composer/) | Default/Dark/Mono annotations, current specular/refraction controls; tool requires macOS Tahoe 26.4 or later | Native material decisions deferred to the real tool; no simulated native project file |
| [Xcode: creating an icon with Icon Composer](https://developer.apple.com/documentation/xcode/creating-your-app-icon-using-icon-composer) | Numbered SVG layers, shared canvas, background/material tuning in Composer; preview clear/tinted via Mono | Three numbered semantic foreground SVGs and import manifest; all six appearances remain native validation tasks |
| [Xcode: asset catalogs](https://developer.apple.com/documentation/xcode/configuring-your-app-icon) | Current flat fallback workflow | Optional single-1024 iOS app-icon catalog prepared; `actool` compilation pending; Anamorph has no iOS build target |

These are source requirements/recommendations. Candidate B's cooler palette,
edge intensity and the decision to favor restrained light are design judgments,
not Apple requirements. Liquid Glass is a platform material, not an instruction
to bake extra glare into the vector artwork.

## Corner research

The current official [iOS 27 template download](https://devimages-cdn.apple.com/design/resources/download/iOS-27-Icon-Templates-Photoshop-Illustrator.dmg)
has SHA-256 `4498b294bbb364501f71129444207fd30ed7e429f6dcee856ba5bf3cbe50c7f6`.
Its Illustrator PDF/vector document, demo `.icon` metadata and exported default
PNG were inspected. We measured the *enclosure contour*, not the demo's symbol:
first alpha ≥128 pixel in rows 3..259 at pixel centres. A grid fit gives radius
331/exponent 2.61 at 1024 px with RMS about 1.23 px. The standalone 960 px body
therefore uses radius 310.3/exponent 2.61. The original 2.45 corner model and
the current-template-inspired contour were compared in rendered compositions.

This approximation is appropriate for independent artwork. It is not Apple's
exact continuous mask or a replacement for Composer/Xcode preview. The
[masking comparison](../assets/anamorph/previews/masking-comparison.png) is
explicitly labelled as a geometry study.

## Distinct export concepts

- `master/anamorph.svg` and `master/anamorph-rounded-1024.png`: independent
  rounded-square body, transparent outside. Appropriate for conventional
  desktop icon containers and documentation.
- `master/anamorph-opaque.svg` / `anamorph-opaque-1024.png`: independent body
  composited on an opaque square field for imagery that cannot carry alpha.
- `master/anamorph-apple-square.svg` / `anamorph-square-1024.png`: full-bleed
  unmasked flat artwork. The optional asset catalog uses an opaque RGB PNG.
  This flat fallback retains authored optical effects and is separate from the
  clean native material source below.
- `apple/layers/01-left.svg`, `02-right.svg`, `03-interaction.svg`: three
  unmasked 1024 px canvases containing crisp filled shapes derived from the
  measured cubics. No blur, opacity, screen blend, shadow, enclosure border or
  baked specular material. Their transparent area is empty foreground, not a
  rounded-square canvas mask. Background is configured in Composer.

All paths above are relative to `assets/anamorph/`. SVG interpolation and all
standalone PNG tags are sRGB. ICNS contains tagged sRGB PNG frames; ICO's
embedded PNG samples are derived from sRGB and decoded pixel-for-pixel but do
not carry a profile tag. No Display P3 gamut expansion is claimed.

The [flat layer study](../assets/anamorph/previews/apple-layers-flat.png) shows
the actual three SVG foregrounds at 16, 32, 128 and 512 px on a plain background,
without native materials or masking. It is a source-legibility check, not an
Icon Composer preview.

## Final masking audit

The [four-way source study](../assets/anamorph/previews/final/masking.png)
compares the independent 960-unit body, full-bleed flat fallback, actual crisp
native-layer composition and that composition under an approximate full-bleed
mask. The latter is a non-native preview. B0 and all Apple handoff bytes remain
unchanged in the final acceptance round.

The flat fallback has an opaque 1024 × 1024 background without a pre-rounded
body or enclosure edge. Native foregrounds contain one motif similarity
transform and no body mask or extra 32-unit inset. Configure their full-bleed
background in Composer. Do not import the opaque imagery master (which still
contains a rounded body) or the conventional precomposed ICNS into this route.
That would retain the independent inset inside another system mask.

The crisp composition has less authored atmosphere than B's conventional
artwork. Native materials, central-light prominence, small sizes and all six
appearances still require actual Composer/Xcode inspection. Structural source
correctness and this approximation do not establish native visual equivalence.

## Remaining native steps

1. Open Icon Composer on a supported Mac. Create a new genuine document with
   a 1024 × 1024 iOS/macOS canvas. Configure the opaque background using the
   gradient colours in `apple/import-manifest.json`.
2. Import the three numbered SVGs in order, preserving their complete canvases
   and placement. Group the two curves if they should share material behavior.
3. Tune the system's specular highlights, refraction and translucency with
   restrained depth. Do not add the static precomposed glow stack to every
   foreground layer. Compare the native result with B's optical identity.
4. Inspect Default and Dark, then Mono with clear/light, clear/dark,
   tinted/light and tinted/dark. Use real contrasting wallpapers and native
   small sizes. The same geometry supplies all six; no cosmetic recoloured
   PNG set has been invented. The native dark background and Mono contrast
   still require adjustment/approval in the tool.
5. Save as `Anamorph.icon`, reopen and inspect it in Icon Composer, then compile
   and inspect with Xcode. Only then may it be described as a validated native
   project. Check current and older OS fallback rendering.
6. Independently validate the conventional iconset on macOS:

   ```sh
   iconutil --convert icns --output /tmp/Anamorph-native.icns assets/anamorph/macos/Anamorph.iconset
   iconutil --convert iconset --output /tmp/Anamorph-roundtrip.iconset /tmp/Anamorph-native.icns
   ```

   Compare decoded sizes/alpha, Finder and Dock rendering, then validate the
   JUCE-generated bundle plist and resources. Native conversion may encode the
   container differently; exact container-byte identity with Pillow is not a
   requirement, but source pixel/geometry consistency is.

The supplied `import-manifest.json` is human-readable handoff metadata, **not
Apple's project format**. iOS is a future asset-preparation use case, not a newly
supported Anamorph platform. Build/integration changes need separate owner
authorization; see the [integration plan](ANAMORPH_ICON_INTEGRATION_PLAN.md).
