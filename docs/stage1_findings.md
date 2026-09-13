# Stage 1 findings — direct measurement of `reference.png`

> **This is the first-pass record, kept as written.** Several numbers here were
> later refined or corrected by the per-component analyses in `out/analysis/`
> and by `docs/METHOD.md` — in particular: every sub-pixel coordinate below is
> in *pixel-index* space and needs +0.5 to become an SVG coordinate; the frame
> corners are not circular arcs of r~170 but three-arc continuous-curvature
> corners with a main radius of 163.56; and the luminous curves are not
> ellipse arcs but two cubic Beziers each (an ellipse arc leaves a systematic
> 0.4 px residual that the Beziers remove). The findings that survived
> unchanged are the frame edge positions, the stroke width, the mirror axis,
> the waist gap, and the general structure.

All coordinates are in reference pixels (canvas 1024x1024, sRGB, 8-bit, no alpha).
Every number below came from pixel measurement, not assumption. The probes were
run as throwaway scripts during stage 1 and were not kept; the measurements that
the reconstruction still depends on are re-derived on every run by the tools that
did survive -- `tools/regions.py` for the curve frame and the region geometry,
`tools/diagnose.py` for the profiles, comb, spokes and banding, and
`tools/test_pipeline.py` for the invariants -- so the numbers below are checkable
against the reference without that script.

## Canvas / provenance

* 1024 x 1024, PNG colour type 2 (RGB, no alpha), sRGB chunk, 72dpi pHYs.
* XMP says `xmp:CreatorTool = Picasa`; the image carries visible 8x8 DCT
  blocking in dark areas, so it has been through JPEG at some point. The
  ±1..3 LSB mottling in flat regions is compression noise, **not** design
  texture, and must not be reproduced.
* 361 pixels are exactly black; the outer background is not black but a very
  dark blue, about rgb(1,2,7).

## Outer frame (rounded rectangle, single stroke)

Sub-pixel stroke centre-lines, from coverage-weighted centroids of the stroke
cross-section:

| edge | centre-line | notes |
|---|---|---|
| left   | x = 65.98  | straight for y in [280,820] |
| right  | x = 951.09 | straight for y in [280,820] |
| top    | y = 33.88  | straight for x in [340,700] |
| bottom | y = 991.18 | straight for x in [340,700] |

=> frame box 885.1 wide x 957.3 tall, centred at (508.5, 512.5).
The frame is **not square and not centred**: it is 8% taller than wide and sits
~3.5px left of canvas centre. Margins: left 66.0, right 72.9, top 33.9,
bottom 32.8. This asymmetry is real and repeatable across many scan lines.

Stroke width from coverage integral: 6.0 px (plateau + ~1px AA each side).
Stroke colour is neutral grey with a slight blue lift, e.g. rgb(70,78,81) on
the left edge, rgb(120,129,136) at the top-centre, rgb(47,64,66) at the
bottom-centre. Peak brightness varies around the perimeter and peaks near the
middle of each edge, brightest along the **top** edge (lum ~128) and dimmest
along the **bottom** (lum ~64); sides ~76-79. The corners are darker than the
edge middles.

Corner radius is roughly 170 px (top edge goes straight at x >~ 232, left edge
at y >~ 205) — refined in `out/analysis/frame.json`.

## The two luminous curves are elliptical arcs

Ridge centre-lines were extracted at sub-pixel accuracy from the R channel
(G and B clip at 255 along the core) using the midpoint of the 60%-of-peak
crossings, which is immune to the clipped plateau.

Fitting an unconstrained general conic to the left ridge gives an **ellipse**
(discriminant -2.3e-9) with RMS residual **0.29 px** over y in [150,900].
So the left curve is an elliptical arc, not a circle (a circle fit is
inconsistent by tens of pixels) and not a generic traced spline.

Axis-aligned ellipse fits (robust, flare band y in [468,562] excluded):

* left  : centre (78.8, 514.8), rx 385.4, ry 467.9, RMS 0.39 px, apex x 464.1
* right : centre (911.8, 514.8), rx 366.9, ry 458.3, RMS 0.61 px, apex x 544.8

`cx` and `rx` are strongly correlated for an arc that covers only part of the
ellipse, so the individually meaningful quantities are the apex position, the
vertical centre and the local curvature; `out/analysis/curves.json` reports the
well-conditioned parametrisation.

Mirror symmetry: the midpoint between the two ridges is 504.4-504.7 over
y in [125,675] and drifts to ~505.3 by y = 900 and 504.0 near y = 700-750.
So the pair is mirror-symmetric about **x ~= 504.5**, which is *not* the canvas
centre (512) and *not* the frame centre (508.5).

Waist: minimum gap between the two ridges is 79.7 px at y ~= 515-525
(left apex x 464.6, right apex x 544.3). The curves do **not** touch or cross.

Both arcs fade out along their length: R-channel core peak rises 0 -> ~200
between y = 83 and y = 180, holds ~190-240 through the middle, and falls back
to 0 between y = 860 and y = 945. The two fade-out points are symmetric about
the ellipse centre y (514.8 ± 430).

## Core colour and the central light

* Curve core is white with a red deficit: rgb(207..234, 255, 255) through the
  middle, rgb(167,201,205) near the fading tips. G and B are clipped over most
  of the core, so the core's true peak cannot be recovered from the PNG.
* Brightest pixel in the image is (x=543, y=514), rgb(254,255,255) — i.e. the
  central flare sits against the *right* curve, slightly right of the waist
  midpoint. Only 106 pixels exceed lum 250.
* A thin horizontal streak runs from the flare almost the full width of the
  frame; diagonal rays and a broad bloom surround it.

## Background is not flat

At 6x gain the interior shows: a broad teal field, wide glow lobes hugging both
curves (brighter on the concave/centre side), darker patches in the four
quadrant corners, a dark band along the vertical centre above and below the
flare, plus low-frequency "smudge" texture that is characteristic of the
source image rather than of a constructible design.
