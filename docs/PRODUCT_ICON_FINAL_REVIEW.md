# Candidate B final review

> **Acceptance update — record updated 2026-10-24 (Asia/Shanghai):** B0 is owner-approved
> unchanged, and the completed integration/namespace decisions are approved and merged.
> See the [current engineering record](PRODUCT_ICON_ENGINEERING.md) for actual merge/CI
> evidence and remaining manual validation. The review below is the original design-stage
> snapshot; its recommendation/pending-merge wording and dated JSON evidence are historical.

## Control and observations recorded before experiments

Control B0 is the published Candidate B at PR #10 head
`d231a7a42b3ae55af6d62031ba1c2a4d7343574f`. Review uses original PNGs and
direct SVG renders, never JPEG captures or an enlarged master standing in for
small exports. The native pixel policy is optical at 16/20/24/32 and regular
at 40/48/64/128/256/512/1024. Images must be opened at 100%; browser fitting
can conceal the differences discussed here.

Before generating alternatives, inspected the original 1024 and 512 PNGs
individually, and the actual 256/128/64/48/40/32/24/20/16 exports at 1:1 on
`#080c12`, `#252d38`, `#808080` and `#edf0f4`. Also inspected the 1024 PNG
composited on light gray at its original dimensions.

| Aspect | B0 observation before experiments |
|---|---|
| Balance and centering | Opposing curves have balanced mass and generous top/bottom space. The right-biased central source is intentional, not a centering error. No reason to move the motif. |
| Rounded-square silhouette | Equal apparent width/height and continuous corners at 1024–128. The outline is quieter than the light motif. It reads as a square body rather than the historical tall frame. |
| Edge visibility | Upper/left boundary is faintly visible on near-black; lower/right boundary partly merges. Medium-dark, neutral and light surroundings make the whole silhouette clear. This is a restrained appearance, with a possible near-black visibility tradeoff to investigate. |
| Central interaction | A compact right-biased point and short horizontal light connection remain visible at 48–128. At 16–24 the source reduces to a tiny bridge and loses internal detail; no large white blob. |
| Curve separation | Two distinct opposing curves remain identifiable. At 16 px they approach one pixel near the middle; both outer lobes still read. At 32 the optical cores remain fine rather than heavy. |
| Curve ends | Deliberately taper into darkness. At 16–24 the terminal fraction disappears, while the principal curvature survives. Large-size tips are not clipped. |
| UI contrast | Cyan motif contrasts well with the body on all four backgrounds. Body contrast is weakest against near-black. No bright corner matte is apparent at native size. |
| Premium quality and identity | The dark field, restrained rays and two luminous curves give a coherent optical identity. More glow or a frame could easily weaken this hierarchy. |
| 32-to-40 transition | Fine glow returns in the regular 40 px source; a modest weight/atmosphere change is visible side by side. No sudden geometry or identity change. Test small factors before considering any policy change. |

## Focused experiments and selection

**Recommend B0 unchanged; B-final is exactly B0.** No production artwork,
geometry, palette, flare setting or small-size policy changed. This is a
review/evidence update. The original A/C study remains archived; it was not
reopened for this acceptance round.

| Candidate | Exact controlled change | Native-size result and decision |
|---|---|---|
| B0 / F0 | Current published B, including its small treatment | Best overall hierarchy; retained. |
| B1 / edge | Edge width 1.6 → 2.0; stop opacities .55/.20/.32 → .60/.26/.40. Body field unchanged. | Inspected at native 1024/256/64/32 on light and dark. A clearer hairline at 1024; negligible useful separation at launcher sizes. Does not solve the lower-field near-black tradeoff sufficiently to justify a more outlined large icon. Rejected. |
| B2 / depth | Local upper-left `#27465e` radial light, opacity .16 → 0, over B0; no global background change. | Same four sizes and backgrounds. Slightly clearer upper body, but the lighting sweep becomes a separate visible surface cue at large size. B0 is quieter and more coherent. Rejected. |
| F1 / compact source | Only `flare_core_w`: radius ×.94, colour ×1.12; original anchor and asymmetric cloud unchanged. | Native 128/64/32, light/dark. Changes the compact source on close comparison without a clear recognition improvement in use. Rejected. |
| F2 / separation | Immediate `flare_halo` colour ×.88, compact `flare_core_w` colour ×1.06; other effects unchanged. | Native 128/64/32, light/dark. Slightly less local atmosphere; no improved distinction between the already separated curves. Rejected. |
| S1 / narrower small cores | Core width gain 1.65 → 1.50; other factors unchanged. | Native 16/20/24/32, with regular 40/48 beside them. Tiny curves become more fragile; no worthwhile transition improvement. Rejected. |
| S2 / small light | Small glow .64 → .70 and flare .55 → .65; core width stays 1.65. | Same native sizes. Slightly more central glow, without recovering the taper ends or making both curves easier to distinguish. B0 is cleaner. Rejected. |

No individual refinement survived, so no combination was promoted. B-final was
checked independently against B0 and is byte-identical. There is no speculative
edge/flare combination hidden in the recommendation. The pinned control and
experiment vectors remain reproducible in `design/final-review.json` and
`tools/review_product_icon.py`; historical parameters are copied in memory and
never written. S1/S2 fall back to the exact B0 regular master above 32 px.

## Compact owner review

- [Historical / B0 / B-final](../assets/anamorph/previews/final/before-after.png)
  at equal native 256 px. B0 and B-final intentionally look identical.
- [Constrained candidates](../assets/anamorph/previews/final/candidates.png):
  boundary at 256/64/32, flare at 128/64/32, small sources at 16/20/24/32 and
  regular 40/48. The exact [experiment SVGs](../assets/anamorph/previews/final/)
  also support full 1024 px inspection; do not zoom the small PNGs to judge use.
- [Native-size ladder](../assets/anamorph/previews/selected-size-ladder.png):
  original direct renders at 1024/512/256/128/64/48/32/24/16. Each icon occupies
  its stated number of image pixels. Open the PNG at 100%.
- [Four backgrounds and simulated launcher](../assets/anamorph/previews/final/backgrounds.png):
  actual 16..256 px sources. The launcher is a labelled generic UI composition,
  not a captured or validated desktop session.
- [Mask/source study](../assets/anamorph/previews/final/masking.png): independent
  rounded body, full-bleed flat fallback, actual unmasked native foreground
  composition, and an explicitly approximate mask. No native Apple rendering.

## Small-size acceptance

Both curves remain distinguishable at 16/20/24/32 on all four backgrounds.
The interaction becomes a compact light connection; it cannot preserve the
large master's internal diffraction detail at 16 px. The extreme taper ends
fade naturally before the mathematical endpoints, with no abrupt cut or body
clipping. The ×1.65 cores do not read as heavy filled bands at native size.

The regular 40 px image restores secondary atmosphere, so a modest side-by-side
change remains at the 32→40 boundary. S1/S2 did not improve that tradeoff.
Keep the existing cutoff at **32 actual raster pixels**, including Retina
slots. Do not extend it to 48/64. All 11 portable raster sizes are generated
directly from their assigned SVG, rather than resampling one master PNG.

## Geometry, masking and export interpretation

The independent body is still 960 × 960 with 32-unit equal margins, exponent
2.61/radius 310.3, and one uniform motif transform. The 1024 alpha bounds are
`(32,32,992,992)`. At 16/24 antialiasing touches the canvas boundary because the
nominal inset is less than one pixel; bounds remain balanced in both axes.

The opaque imagery asset still contains the independent rounded body on a
square field. It is **not** an Apple native input. The Apple flat fallback has
a fully opaque 1024 square background and no inset body or enclosure edge.
The three native foregrounds are transparent, unmasked 1024 canvases; their
empty corners are foreground whitespace, not a second rounded mask. They have
the one documented motif transform, no additional inset, no baked blur and no
system material. Full-bleed native background/masking is configured separately.
Only the study applies a mathematical full-bleed mask, labelled approximate.

Conventional ICNS/iconset, ICO and Linux PNG resources intentionally use the
precomposed independent silhouette. Linux scalable SVG equals the regular
master. Exact-size hicolor PNGs provide the optical treatment at 16/24/32;
a desktop choosing the scalable SVG at those sizes would use regular artwork.
Actual icon-theme selection and WM identity need a desktop-session check.

The native Apple source composition is visibly leaner than the precomposed
optical artwork. Its eventual material, flare prominence and small-size
appearance require Composer tuning; this package does not establish native
visual equivalence. See [Apple workflow](APPLE_ICON_WORKFLOW.md) and the
[unchanged read-only integration matrix](ANAMORPH_ICON_INTEGRATION_PLAN.md).

## Acceptance and remaining limits

The final product publish command completed: **14 checks passed**, independent
Inkscape/resvg checks passed at 32/128/512/1024, the Linux desktop template
passed syntax validation, and **all 91 generated files matched a clean rebuild
byte-for-byte**. All 47 platform/handoff files match the pinned published B0
digests. ICO's nine frames and ICNS's eleven entries match their actual source
pixels, including the correct small variant. All 354 protected historical
files and the byte-identical reconstruction rebuild also pass. Historical CI
was successful on control head `d231a7a`; consult PR #10's checks for the final
review commit's complete regression status.

No blocking visual defect was found in the selected independent artwork.
Known visual tradeoffs are the subtle lower edge on near-black, disappearing
extreme tips and reduced flare detail at 16 px, and the modest 32→40 atmosphere
transition. These were examined directly; the tested changes did not produce
a better overall icon.

**Readiness category 2: ready with documented non-blocking native-platform
limitations**, for owner merge as an independent icon-design baseline once
the current-head checks pass. Merging sources, approving the brand, integrating
into Anamorph and shipping native installers are separate decisions. This
review performs none of the latter actions and does not authorize a merge.

Native Icon Composer/Xcode/actool/iconutil, six Apple appearances, Finder/Dock,
Windows PE/ISCC/Explorer/shortcuts/DPI and Linux desktop/WM behavior remain
unverified. Prepared `.icns` and layers are not native-certified resources or
a real `.icon` project. Missing Apple tools do not block a source-design merge.

Measured verification is recorded in
[PRODUCT_ICON_VALIDATION.json](PRODUCT_ICON_VALIDATION.json) and the
[engineering record](PRODUCT_ICON_ENGINEERING.md). The canonical recommendation
remains [anamorph.svg](../assets/anamorph/master/anamorph.svg).
