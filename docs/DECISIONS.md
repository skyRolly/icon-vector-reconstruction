# Decision record

Why the reconstruction looks the way it does inside. Each entry states the
decision, the evidence, and what was rejected.

---

## D1. Representation: hand-built parametric SVG, no raster component

**Decision.** A single parametric SVG: one path for the frame (straight runs
plus three arcs per corner), two cubic-Bezier paths for the luminous curves
(reused, offset, by every glow layer), and blurred ellipses, rects, cones and
gradients for the central light and the background. Every mark is driven by a
named number in `src/params.json`. No embedded bitmap, no traced outlines.
(The layer count and the file size are not restated here: they are generated
into the README from `src/params.json` and the built file, because this entry
and the README both carried stale counts for a whole iteration -- 22 and 28
named layers, ~52 and ~68 KB, against the real 29 and 74 KB.)

**Evidence.** Everything visible decomposes into geometry plus smooth optical
falloffs: the curves are sub-pixel-accurate Beziers (section 3 of
`docs/METHOD.md`), the glow separates into a product of an inward profile and an
along-curve modulation (i.e. a blurred stroke with a taper), the colour space is
a narrow non-negative cone (D6: a PCA of the interior gives eigenvalues 0.981 /
0.012 / 0.007, so the light is *nearly* two-dimensional, but the third dimension
is where the whole dark background lives, and each layer carries three
non-negative amounts, not two), and the background is two radial gradients plus
a ramp. Nothing needed a per-pixel description.

**Alternatives evaluated.**

* *Automatic bitmap tracing.* Rejected on principle for this image and not used
  even as an aid: the subject is 95% smooth gradient. A tracer would emit
  thousands of iso-luminance contours of JPEG noise, would not scale (the
  contours are rasterisation artefacts, not design), and would not be editable.
* *Hybrid SVG + one raster layer* for the background texture. Rejected: the
  only thing a raster layer would add is the reference's own JPEG blocking and
  generator smudge (D7). It would have improved the metrics slightly while
  making the artwork non-scalable and non-editable.
* *A single mega-filter* doing the whole composite with `feComposite
  arithmetic`. Rejected: portable but unreadable, and it would have made the
  analytic fitting impossible.

## D2. Curves: two cubic Beziers per curve, not an ellipse arc

**Decision.** Each curve is two cubic segments joined at the apex with a
vertical tangent.

**Evidence.** Ridge RMS 0.083/0.093 px against 0.331/0.473 px for the best
axis-aligned ellipse arc; verified end-to-end (render the candidate, re-extract
the ridge, compare with the reference ridge) at 0.11/0.13 px versus 0.33/0.47 px.
The ellipse's residual is a smooth 4-5 lobe +-0.4 px shape that no fifth conic
parameter removes.

**Rejected.** Circle (RMS 1.7-1.8 px). Parabola (5 px). Rotated ellipse and
general conic: the general conic converges to the rotated ellipse, and the
fitted rotation swings from -24 to +11 degrees with the y-range used, so the
parameter is absorbing model error, not measuring a tilt. A superellipse
exponent helps the left curve and not the right. The elliptical-arc form is
kept in `src/params.json` (as `measured_ellipse_fits_pixelindex`) because the
glow clip still uses it, and it documents what the shape is close to.

## D3. Frame corners: a 3-arc continuous-curvature corner

**Decision.** Each corner is blend arc (r 639.06, 5.0916 deg), main arc
(r 163.561, 79.8168 deg), blend arc -- the corner design tools draw with "corner
smoothing" on.

**Evidence.** Residual to the measured corner outlines: 0.13-0.27 px, against
0.35-0.44 px for a single cubic Bezier corner, 0.66-0.84 px for a circular
rounded rect tangent to the measured straight edges, and 2.5-2.7 px for a
superellipse. Independently: the local radius of curvature runs 250-400 px near
the straights and 145-175 px through the 45-degree region; a circle fitted to
the corner points alone sits 1.9-2.7 px inside both straight edges, so it
cannot join them; and the centre-line is still 0.66 px inward 195 px from the
box corner, where any circular corner fitting the 45-degree region would be
exactly on the line. All four corners share one radius to +-0.21 px.

**Rejected.** `<rect rx>` / circular arcs (a visible 1.4-1.8 px corner
mismatch). A per-corner superellipse, which was this reconstruction's own
earlier answer: fitting |dx/r|^n + |dy/r|^n = 1 with the centre pinned so the
curve is tangent to the measured edges gives n = 2.45, r = 203 and ~0.7 px --
better than a circle, and still five times the 3-arc residual. It is left in
`src/build_svg.py` (`squircle_rect_path`, selectable via
`frame.corner_model`) because it documents what the shape is close to.
Per-corner radii were not used: the four agree within noise.

## D4. Glow: three offset blurred strokes per curve

**Decision.** Each curve's glow is three stroked copies of its own path, offset
inward by 3.28 / 16.20 / 62.07 px and blurred so their perpendicular profiles
are Gaussians of sigma 7.22 / 26.92 / 56.59 px, each with its own measured fade
along the curve.

**Evidence.** Cross-sections out to +-320 px at 45 stations per arc are
reproduced, core included, to 2.4-2.7 code values rms (JPEG noise floor 1.3) by
exactly that decomposition, with the sigmas and offsets *global* -- one set for
both curves and every station -- and only the amplitudes varying. The inward
offsets are what produce the measured 2.8-3.5x concave/convex asymmetry.

**Rejected.**

* *Symmetric blurred strokes only*: cannot produce the asymmetry at all. The
  first version of this reconstruction did that and left the region between the
  curves several counts too bright and the concave side too dark.
* *An ellipse filled with a light-centred radial gradient*: reproduces the
  asymmetry but not the along-the-curve modulation. Along a normal at
  mid-latitude the distance to the central light barely changes while the
  brightness drops 4x, which rules out any light-centred radial field.
* *Wide blurred strokes clipped to each curve's own ellipse*: this was the
  second version, and it works (it was the single biggest fidelity jump of the
  whole job, MAE 9.19 -> 6.80). The measured three-Gaussian decomposition
  replaced it because it needs no clip, no extra `clipPath` defs, and reaches a
  lower peak error (max channel error 147 -> 100). **Partly reinstated in
  D13**: three inward-offset strokes get the sign of the asymmetry right and
  its extent wrong, and the clip is the only thing that stops the broad
  concave tail from also filling the space between the curves.

## D5. Colour: a three-component non-negative cone

**Decision.** Every layer carries three non-negative numbers: how much
white(1, 1, 1), cyan(0, 0.94, 1) and blue(0, 0, 1).

**Evidence.** PCA of the interior colour *directions* gives eigenvalues 0.981 /
0.012 / 0.007, so the light is nearly two-dimensional — but "nearly" is not
"is", and the third dimension is where the whole background lives. Over the
946 964 reference pixels above luminance 3, the non-negative fit in this basis
is off by **0.010/255**; dropping blue and keeping white+cyan alone is off by
**1.84/255**, and white alone by 9.96/255. The same ordering holds at every
brightness threshold (1.5-1.8/255 for white+cyan at thresholds 10, 25 and 60).
The reason is the dark field: across its 620 317 pixels between luminance 3 and
14 the mean colour is (1.8, 7.1, 13.4), G/B = **0.53**, against cyan's 0.94.

The point of the basis is not compression, it is a modelling safeguard: the
non-negative cone spanned by these three vectors is exactly `R <= G <= B`, the
family the reference uses everywhere, so a shape error can no longer be hidden
by inventing a colour.

**Rejected.**

* *White + cyan only.* This was the previous decision, and it was wrong by a
  factor of 180 in the colour residual. An earlier version of this record and
  of the README said each layer "carries just two numbers"; the code had three
  components all along. Corrected here and in `README.md`.
* *Free RGB per layer.* Fits marginally better in the raw metric but produced
  physically absurd layers (a magenta core, a green bloom) as the optimiser
  used hue to compensate for shape error, and made the SVG much harder to
  reason about.

## D6. Compositing: `mix-blend-mode: screen`

**Decision.** Screen over an opaque black base, clip on every element.

**Evidence, measured in both engines.** `screen` gives identical results in
resvg and Chromium (64 over 96 -> 136 in both). `plus-lighter` — the physically
correct operator — is **not** implemented by resvg (it falls back to 96 where
Chromium gives the correct 160), so it is unusable here. A group carrying
`clip-path` becomes an isolated group and silently kills `mix-blend-mode` for
its children (96 instead of 136, in *both* engines), so clips are set on each
element instead of on a wrapper. `clip-path` and `filter` on the element itself
compose correctly with the blend mode.

Screen is also a good model for the reference: light adds while dim, and rolls
off into a clipped white core.

## D7. Not reproduced: JPEG blocking and generator texture

**Decision.** The reference's +-1..3 count 8x8 DCT blocking, and the
low-frequency smudge texture in the side lobes, are not reproduced.

**Evidence.** XMP says `CreatorTool = Picasa` and the blocking is on an 8x8
grid — it is a compression artefact of the delivered file, not of the artwork.
The smudge has no constructible geometry and differs between the two lobes.

**Cost.** These set the noise floor on every metric: a perfect reconstruction of
the underlying design would still show ~1-2 counts of MAE from them.
The brief explicitly forbids introducing texture not supported by the reference,
and reproducing an artefact of the file format is not fidelity to the design.

## D8. Filter regions and colour interpolation are pinned

**Decision.** Every blur filter has an explicit user-space region clamped to
the frame's bounding box, and `color-interpolation-filters="sRGB"`.

**Evidence.** The SVG default region (-10%/120% of the object bounding box)
visibly clips a sigma-165 blur of a thin path. The SVG *default* colour
interpolation is linearRGB, which changes every glow falloff; pinning sRGB
matches the reference's own compositing space and removes an engine-dependent
variable. Clamping the region to the frame bbox is lossless (filtering happens
before clipping) and cut the render time by a third.

## D9. Fitting: analytic photometry, searched geometry

**Decision.** Layer colours are fitted in closed form; layer shapes and the
geometry are searched by bounded coordinate descent with the colours re-fitted
inside the loop.

**Evidence.** The closed-form composite (D6) makes the colour problem a smooth
52-parameter least-squares that needs no rendering, so it converges in seconds
and cannot be the bottleneck. Shapes have to be searched because they change the
coverage fields. Per-layer bounds are part of the artwork, not just the search:
without them the optimiser swaps a "near" glow for a "wide" one or collapses the
core stroke into the halo — numerically free, but it destroys the layer stack's
meaning.

## D11. The central light: no bright disc, plus a separate glint

> **Superseded by D14.** Kept because its evidence still stands and because one
> of its conclusions was wrong in a way worth recording. "No bright disc" was
> read off the *composite*, where the flare centre reads luminance 224; the
> exact isolation in D14 shows the flare's own contribution peaking exactly
> there, at additive luminance 4.9, and 198 pixels above luminance 248 in a
> plateau ~20 px across. What the reference does not have is a bright disc with
> a *peak*; it has one with a flat, clipped top. The reconstruction now carries
> a plateau-topped core, and the "glint" of this entry is that core.

**Decision.** The centre is built from a two-part horizontal streak, two
horizontally stretched blooms, three individually placed one-sided rays, and a
separate compact glint at (535.0, 514.8) -- and *no* bright disc at the flare
centre.

**Evidence.** At the flare centre the image reads lum 224 and nothing within
15 px of it reaches 245; along the waist the luminance rises monotonically from
one core to the other with no local maximum in between. Meanwhile every
off-arc pixel above lum 245 lies in one small patch centred (531.3, 512.8),
whose excess over the mirrored image is a clean bump of FWHM 35.5 px centred at
(534.5, 514.3) with a peak of 170/255 -- and the two right-hand rays converge
on it. So the visually brightest thing in the icon is not the flare centre.

**Rejected.** A radial "core" disc at the flare centre -- which is what this
reconstruction had for several iterations. It produced a local maximum the
reference does not have (+11 code values at r < 12 and -6 at r = 12-25 in the
ring profile) and cost 2.4 MAE in the central region. A symmetric starburst
primitive was also rejected: the three measured rays are one-sided and are
neither 4- nor 6-fold symmetric, so a symmetric primitive invents three rays
that are not there -- at 3-5 code values each, they would be as strong as the
real ones.

**Ambiguity kept in the record.** The glint's vertical centre (514.8)
coincides with the curves' own symmetry axis (514.85) rather than with the
streak (512.2), so it can be read either as a second glint element of the flare
placed on the right curve's apex (which is what the ray convergence says) or as
an extra inner glow lobe belonging to the right curve. Both readings produce
the same pixels; the reconstruction draws it as one radial layer and does not
claim which it is.

## D12. Renderer choices, measured in both engines

224 purpose-built test SVGs were rendered in both resvg and headless Chromium.
What that settled:

* **`mix-blend-mode` must be written in `style=""`.** As a presentation
  attribute it is ignored by *both* engines.
* **`screen` is byte-identical** in both at every stack depth 1..16, and it is
  sRGB-space screen (three grey-64 layers give 148, not the linear 106.7).
  Plain-alpha stacks diverge instead (resvg rounds, Chromium truncates: 4 code
  values at depth 16, and a 28% total-ink difference in a 10-layer blurred halo
  against 2.3% for the screen version).
* **`plus-lighter` is unusable**: resvg silently falls back to normal (48 where
  Chromium gives the correct 144).
* **Filter regions must be explicit and in user space.** With the default
  region a sigma-40 blur loses the element entirely in resvg (ink 0) and is
  clipped in Chromium; the default region is also the geometry bbox with the
  *stroke excluded*, so a 60 px stroke loses 5.8% of its ink in both. A margin
  of 3 sigma clips exactly nothing.
* **`color-interpolation-filters` must be written explicitly.** The absent
  default is linearRGB in both, but `auto` diverges (109 vs 192 on the same
  additive chain). It has no effect on a monochrome blurred shape -- only alpha
  is convolved -- so it does not change any glow's falloff here; it matters
  only where different colours combine.
* **Known residual disagreement.** Both engines use a three-pass box blur, but
  with different box sizes: resvg's effective sigma is 0.98-0.99 of nominal and
  Chromium's 0.94, so resvg's wide glows are 3.5-5.3% wider. Small blurs are
  worse: a 1 px line at sigma 2 peaks at 51 in resvg and 43 in Chromium. This
  is the main reason the two engines disagree at all on this artwork
  (`out/validation.md` quantifies it end to end), and it is not fixable from
  the SVG side.
* resvg also quantises stroke-outline edges to multiples of 0.25 px, so there
  is no point tuning frame geometry below ~0.13 px.
* **Chromium renders each *dim* screen layer slightly brighter, and it
  accumulates.** Measured on this artwork by rendering subsets: one dim layer
  alone is +0.26 to +0.33 code values brighter in Chromium than in resvg, four
  of the field layers together +1.32, two corner layers +0.50 -- roughly
  additive, and roughly absent on bright layers (three arc glows: +0.22 in
  total). Across the whole 29-layer stack it is a **+2.77** mean offset.
  That offset is nearly all of the cross-engine difference: the MAE between the
  two engines is 2.907, and 1.355 once the mean is removed, so the two engines
  agree on the artwork's *structure* and disagree on a near-uniform lift of the
  dark background. It is a compositing-precision artefact, not something the
  SVG can express its way out of: the layers cannot be merged, because a
  gradient modulates alpha only and each of these layers carries a different
  colour. It is the cost of the extra elements iteration 2 added -- the same
  figure was about +2.0 with 22 layers -- and it is the one number that got
  worse while every fidelity measure improved.

## D13. The broad glow is clipped to the lobe, and one stroke leans the other way

**Decision.** Two components were added to each curve. `arc_haze` is a wide,
low-amplitude stroke deep in the lobe, `clip-path`-ed to that curve's own
ellipse so it puts *nothing* on the convex side. Two components are offset
**outward**, towards the space between the curves: `arc_glow2b` (the wider of
the pair) and `arc_glow1b`. Every other glow component is offset inward.

**Evidence.** Signed-distance profiles pooled over both curves, with everything
within 200 px of the central light excluded (section 4a of `METHOD.md`). Above
the far-field floor the concave excess is 1.7x the convex one 11 px out and
5.9x 100 px out; the convex side is indistinguishable from the background by
100-130 px while the concave side still carries 6 code values at 170 px. On the
inter-curve midline at y=200, 140 px from *both* curves, the reference sits at
3.9 code values against 13.5 at a lobe point 140 px from one curve.

Against that measurement the previous stack was 13-19% too dark in the band
28-70 px between the curves and 6-11% too bright in the lobe 14-38 px out —
because every one of its strokes was inset into the lobe, so the convex side
only ever saw their tails. `arc_glow2b` cut the profile's rms relative error
from 8.6% to 7.0% with no change in global MAE (2.2753 -> 2.2745).

**Rejected.**

* *Retuning the three existing strokes.* A scan of `arc_haze` over
  width x inset x blur = 4 x 3 x 3 found nothing better than the starting
  point: the concave side was already within 11% everywhere, so no amount of
  broad-concave shape fixed a convex-side deficit. That is what identified the
  missing component rather than a missing parameter value.
* *Removing `field_mid`, the broad central wash, instead.* Tried: the profile
  error got worse (7.0% -> 8.0%) and the global MAE much worse (2.275 ->
  2.478). It earns its place; what it needed was a searchable vertical squash,
  since a round blob of its size over-fills the top and bottom of the lens.
* *Reusing `glow3`'s measured fade for both new components.* Splitting the
  profile error by along-curve angle showed why that is wrong: near the waist
  the two sides balanced, but towards the tips (\|t\| 40-62 degrees) the
  reconstruction was +27% on the concave side and -15% on the convex one, i.e.
  far too one-sided exactly where `glow3`'s fade has died. The three original
  fades are measured station by station and stay tables; the two new components
  carry their own tunable ramps (`tapers.haze`, `tapers.glow2b`), which is
  honest about the fact that no station-by-station measurement exists for them.
* *A softer, unclipped version of `arc_haze`.* The hard edge a clip leaves at
  the curve is a real artefact, but it falls under a core stroke two orders of
  magnitude brighter and is invisible at every resolution tested; an unclipped
  stroke wide enough to reach 270 px into the lobe puts 20-40% of that light
  between the curves, where the reference is at its darkest.

## D14. The central light's extent is bounded by measurement, not by the metric

**Decision.** The flare is rebuilt from an exact isolation of its own
contribution (`tools/isolate.py`, method in section 5a of `METHOD.md`): a
plateau-topped compact core, two halo terms whose widest is bounded at 210 px,
a thin 59-px-west-centred streak, a broad fan, and five cones. (D21 rebuilds
it again, to the measured streak comb and the thin spokes; the shipped layer
list is in `src/params.json` and is not restated here.)

**Evidence.** In additive luminance the isolated flare falls from 2.30 at r=6
to 0.02 at r=92 and **0.005 at r=115**, i.e. nothing measurable past
~130-160 px. The previous widest bloom had r=378 px and its surplus filled the
space between the curves — the darkest part of the interior. Three further
measurements each forced a specific change:

* 198 reference pixels sit above luminance 248 in a plateau ~20 px across; the
  previous reconstruction rendered 67 of them and was 20 code values too dark
  at the centre. This one renders 184, and 170 against the reference's 170
  within 60 px of the centre.
* the streak's additive excess peaks at 0.76 across two pixel rows, and the old
  markup (a 2 px rect blurred by 2.7 px) caps on-axis coverage at 0.29 — so the
  layer's colour was pinned at white and the streak still rendered three times
  too faint. The rect height and the blur are now both derived from `sigma_y`
  at `h / sigma_b = 3.92`, giving 0.95 on-axis with `sigma_eff = sigma_y`.
* the westward fan's half width grows from ~10 px at r=30 to ~28 px at r=92, so
  a parallel-sided quad can match its near part or its far part but not both.
  Rays now carry a `spread`.

**Effect, as measured at the time of this change.** Flare radial profile
agreement went from -20/-13/-11 code values at r<45 to within +-4.3 at every
radius; MAE within 110 px of the core 10.01 -> 7.9; peak channel error over the
whole image 112 -> 96. These are the figures for *this* decision and not the
current state of the reconstruction: D21 rebuilt the streak afterwards, and the
current numbers are in the README's generated fidelity table and in
`out/diagnostics.json`.

**Rejected.**

* *Raising the bloom's amplitude to close the r<12 deficit.* That deficit was a
  plateau-versus-peak error, and the amplitudes were already clipped against
  white — three separate layers were sitting exactly at the colour bound, which
  is the signature of a shape that cannot deliver what the fit wants.
* *A dedicated flat-topped disc at the centre.* This was tried and it worked: a
  `plateau` fraction on the falloff law, holding it at its peak over the first
  part of the radius, took the centre from 20 code values too dark to within 3.
  It is not in the final reconstruction, because it was the right fix for a
  model that was wrong elsewhere. Once the halo's radius came down to its
  measured 92 px and the streak markup stopped capping its own on-axis
  coverage, the sum of halo and streaks saturates over the measured plateau by
  itself: re-fitting left the flat-topped disc at 0.006 of full amplitude, and
  removing it changed the whole-image MAE by -0.0001 — it heads the
  `tools/prune_layers.py` report. The parameter went with it rather than
  staying as an unused knob; the SVG is byte-identical without it.
* *A symmetric starburst primitive.* The angular maxima are at 45-60, 110-120,
  175-195, 225-255, 300 and 330-345 degrees, with the westward one 3-5x the
  eastward one. Neither 4- nor 6-fold symmetry, so the primitive would invent
  rays that are not in the image.

## D15. The fitting objective scores the glow's shape cell by cell

**Decision.** The per-pixel fitting weight has a third emphasis term. The
glow's cross-section is divided into cells -- (signed distance from the curve) x
(along-curve band), plus the four interior corners past the curve ends, and
since the flare rebuild also the flare's radius x sector cells and its streak
comb, 222 in all -- and each cell receives the same influence, shaped as
`1 / (L + floor)^(2p)` inside the cell, *replacing* the display-curve weight
there rather than multiplying it. The cells are disjoint by construction. The
floor and the exponent are `EMPHASIS["profile"]`'s, and D20 measures them: the
shipped values are 0.006 and 1.0. `tools/test_pipeline.py` prints the cell count
and the cost spread on every run, so neither figure has to be remembered here.

**Evidence, in three steps, each one a thing that went wrong first.**

1. *Scale.* The objective is a weighted sum of squares, so what a cell costs
   for a given *relative* error is `(total weight) x (r L)^2`. Equalising that
   needs `1/L^2`, not `1/L`, and needs the base weight out of the way. All the
   figures here are now measured with the *production* formula, because the
   earlier ones were not and two different numbers ended up standing for two
   different things under the same name. With the shaping in place a uniform 1%
   relative error costs 4.57x more in the worst cell than the best; with the
   display curve alone and no cell shaping, 51.23x. And while the weight was
   being applied in the wrong convention (see below) the production spread was
   183.27x -- the mechanism by which "a numerically strong global score"
   coexisted with an obvious local error: a 19% deficit 45 px inside the curves
   cost the fit less than a 2% error on the frame.
2. *Where the floor sits.* `1/L^2` with no floor equalises relative error
   exactly -- Weber's law -- and Weber's law fails near black: 15% of the
   7.5-count outermost cell is one code value and invisible, 15% of the
   42-count innermost cell is six and not. The floor is therefore a visibility
   threshold. It was 0.012 (3 code values) here; D20 re-measures it and ships
   0.006, about the quantisation scale.
3. *Cells, not distance-only bins.* Pooling along the curve hid the tips
   completely. Every pooled bin read within 5%, while the lobe within 80 px of
   a curve end was 20-30% too dark -- and because the objective could not see
   it, the taper search had drained it further (iteration 1 was 15-20% too dark
   there, not 30%). Splitting by along-curve band is what surfaced it.

`tools/test_pipeline.py` checks all three: the cost of a 1% relative error
across the cells, that the outermost along-curve band is covered, and that the
interior corners are covered.

**Rejected.**

* *A fully relative weight, `1/(L + f)` over the whole image.* It did improve
  global MAE (2.2955 -> 2.2501) but degraded the flare (bias -4.0 -> -5.6 code
  values inside r=40) and still left every structural error in place, because
  those are shape errors and no reweighting fixes a shape.
* *Overlapping cells.* Cells that share pixels are each weighted as if they
  owned them, and the shared pixels take whichever value was written last; the
  cost spread went from 2.3x to 6.2x. They are made disjoint in
  `regions.weight_cells`.
* *Cells past the curve ends.* Tempting, since that is where the worst deficit
  was, but there is no curve there -- it would have been asking the glow layers
  to light a region with no source. The deficit belongs to a separate element;
  see D18.

## D16. Optimiser correctness, and the checks that keep it

**Decision.** Five defects that could invalidate an optimisation result were
fixed and are now covered by `tools/test_pipeline.py`, which
`tools/optimize_all.sh` runs first.

* **Stale layer caching.** The basis cache was keyed on layer id with a
  hand-maintained list of which parameters invalidate which layers; the list
  and the builder had drifted, so trials were scored against streak artwork
  that the parameters no longer described. The cache key is now a SHA-1 of the
  SVG the layer would actually render, which makes a stale entry impossible by
  construction, and the builder itself answers which layers read the global
  flare centre (`build_svg.flare_dependent_layers`).
* **Search intervals that excluded the current value.** `field_grad.cx` sat at
  890.33 while the generated interval ended at 820, which silently froze it:
  every proposal landed outside and was rejected unevaluated. Field intervals
  are now generated around the current value, and any interval that still fails
  to contain it is widened with a log line. A check asserts that every
  generated interval contains its parameter's value.
* **Parameters nested under `paint/`.** `exterior_corner`'s gradient centre is
  `paint.cx` / `paint.cy`, which the field spec builder never looked at, so
  that layer was skipped entirely. Both spellings are discovered now.
* **List-valued parameters.** An anisotropic `[x, y]` blur produced no specs at
  all. Each component is now searched separately, with per-component intervals;
  the check exercises this against a probe layer so it cannot pass vacuously if
  the shipped artwork happens to use only scalars.
* **A degenerate parameter under search.** `corner_r_blend` was searched with a
  +-300 px span although the corner fit only measures the blend's lateral
  offset `r (1 - cos a)`; it had drifted 639.06 -> 619.06 for a 0.08 px change
  in that offset, leaving the documented value wrong. It is now held at its
  fitted value and only the turn angle — which spans the identifiable
  direction — is searched.

**Rejected.** *Clamping `field_grad.cx` into the old interval.* The value was
not the error; the interval generator was. Clamping would have moved a measured
gradient centre 70 px to satisfy a bound that had no evidence behind it.

## D17. Headless Chromium is optional in fact as well as in the README

**Decision.** `tools/validate.py` takes `--no-chromium`, checks that the binary
exists before invoking it, catches a failed launch, and says plainly in its
report that the cross-engine rows were not measured while the resvg rows are
unaffected.

**Evidence.** The README said Chromium was optional; `validate.py` invoked it
unconditionally, so the documented validation command failed on a clean
checkout with only the documented dependencies installed. Behaviour and
documentation now agree; `python3 tools/validate.py --quick --no-chromium`
completes with numpy, Pillow and resvg-py alone.

## D18. The light in the four interior corners is its own element

**Decision.** Two layers, `corner_in` and `corner_in_top`: each a wide stroked
copy of the frame path, clipped to the interior, blurred, painted with a radial
gradient centred in the icon so that it lights the corners and not the edge
midpoints. Two rather than one because the top pair of corners is brighter and
reaches further into the interior than the bottom pair, and a single layer
splits the difference and is wrong at both ends.

**Evidence.** Over interior pixels more than 40 px from either curve and more
than 250 px from the central light, within 100 px of the frame, the corner
quadrants read 9.5-11.0 code values in the reference against 7.0-8.3 rendered
(30% too dark over 67 000 px) while the edge midpoints agreed to 0.1-0.7. The
deficit does not decay with distance from the *curve*, it decays with distance
from the *frame*, and only near the corners. Nothing else in the model is
corner-weighted on the inside: `exterior_corner` is clipped to the outside, and
the interior field gradient is a single monotone ramp, which cannot be bright
at all four corners at once.

The primitive works because of the frame's own geometry: its path is 651 px
from the icon centre at the corners against 442-478 px at the edge midpoints,
so a radial gradient rising across that range separates the two.

**Rejected.**

* *Extending the curve glow past the curve ends.* The Bezier endpoints are at
  \|t\| = 66-69 degrees; the deficit runs from there to 90. Filling it with
  curve glow would put light where the reference has no curve, and would need
  the glow layers to stop obeying their own measured cross-section.
* *Making the interior field gradient corner-weighted.* It is one radial ramp
  centred well outside the canvas -- measured, and it beats flat by 33% in G
  MAE on a glow-free mask. A single ramp cannot be bright at four corners, and
  replacing it with something that can would discard a measured element to fix
  an unrelated one.

## D10. Asymmetries are preserved, not tidied

The frame is 885 x 957 (not square) and sits 3.5 px left of the canvas centre;
the curves' mirror axis is x = 504.5, which is neither the canvas centre nor the
frame centre; the curves' own vertical centre is y = 514.85 while their apexes
are at y = 517-519; the pair departs from mirror symmetry by up to 1 px in the
bottom third. All of these are measured, repeatable, and reproduced. The brief
asks for the observable result, not for a tidier design.

## D19. The banding inside the curves: what it is, and what it is not

The reported defect was "vertical banding / layered stripes" in the lobes, and
five hypotheses were tested before anything was changed. Four are refuted and
recorded here so they are not tried again.

**The metric had to be built first, because the obvious one is backwards.**
A high-pass "smoothness" score says the render is *smoother* than the reference:
in the lobes its total cross-curve band-pass amplitude is 0.34 counts rms at
sigma 3 against the reference's 0.62. Blurring would score better still. What
differs is coherence along the curve. The reference's band-pass content is grain
and JPEG texture, uncorrelated from one height to the next, so averaging along
the curve cancels it as 1/sqrt(N) -- to 0.029 counts at N ~ 450. A layered field
produces the same cross-curve profile at every height and survives that average
untouched, and what survives is exactly what the eye reads as a stripe. So the
measurement is the along-curve-*averaged* cross-curve profile, the reference
supplies its own value for every part of it, and the target is two-sided: less
coherent structure than the reference fails as well, because that is what
blurring the region until the stripes stop showing would produce.
`band_report` in `tools/diagnose.py` is that measurement.

**Refuted: gradient stop interpolation.** SVG gradients interpolate linearly, so
every stop is a slope discontinuity. Replacing the sampling with a monotone
cubic (PCHIP) through the measured knots plus error-driven adaptive sampling to
1.0 code values changed the far-lobe contour residual from 0.3271 to 0.3284 --
i.e. not at all. The smooth interpolation was kept anyway, because it is a more
faithful rendering of the profile the parameters describe, but it is not a
banding fix and must not be described as one.

**Refuted: 8-bit output and dithering.** A float render averaged over 4096
samples and a dithered render show identical patches.

**Refuted: filter-region truncation.** The old comment's claim that clamping the
region inside the frame bbox was lossless *was* wrong and is fixed, but the
measured effect was at most 1.33 counts, mean -0.102.

**Refuted: the renderer.** The analytic float composite (no 8-bit step
anywhere), the shipped 1024 px resvg render, and a 4096 px render box-downsampled
to 1024 score 0.3920, 0.3901 and 0.3863 -- all 1.67-1.69x the reference. The
excess is in the model, not in any rasteriser.

**Refuted: one bad layer.** Removing each of the 29 layers in turn moves the
coherent amplitude by at most 1.6%, and removing the field layers makes it
slightly *worse*: the fit has arranged partial cancellation between them.

**What it actually is: two defects, in different places, with different causes.**
Localising the error in cross-curve distance separates them, and pooling them
was what made the earlier readings contradictory.

*Inside 40 px of the ridge* the glow basis cannot reach the reference's shape.
The effective cross-curve widths of the glow strokes step 5.8 px (`arc_glow1`)
to 20.6 px (`arc_glow2`), a factor of 3.5, and the best achievable residual
peaks inside that step, changing sign across it (+0.38 counts at s -40..-20 and
-0.46 at -20..0 on the right curve). Adding one stroke in the gap raises the
best achievable accuracy there from 1.11%/1.78% to 0.40%/0.34% (left/right) and
its oscillatory part from 0.82%/0.87% to 0.31%/0.42%. Position matters as much
as width: the same effective width at inset 14 instead of 6-10 is markedly
worse. That is the evidence for `arc_glow1c`, and it is the whole of it -- one
blurred stroke on the existing Bezier path, six numbers, no new geometry.

*Beyond 40 px* the basis can reach the reference's profile, but not while the
rest of the image is fitted. The profile-only optimum -- non-negative amplitudes
fitted to the lobe profile and nothing else -- reaches 0.99%/1.15%, against
2.97%/3.92% achieved. It gets there by using 13 of 29 layers and wrecking
everything else: global MAE 1.90 -> 8.20, frame 1.30 -> 7.48, centre 90 px
7.53 -> 35.16, between the curves 4.34 -> 24.86. So that bound is not a target.
The lobe's pedestal comes from field, exterior and flare layers that are pinned
by their duties elsewhere, and what remains in the interior is the price of a
shared basis, not a fitting failure. It is stated here rather than hidden
because it is the honest limit of this model: the interior's residual coherent
error is about 1% oscillatory on levels of 8-35 counts, which is under the
reference's own grain, and driving it lower would take a different
decomposition, not a better fit.

**Rejected on measurement: a lobe-localised field component.** The obvious way
to give the interior its own freedom is a soft radial gradient centred in each
lobe. It improves the global metrics -- MAE 1.9849 -> 1.9619, SSIM 0.9720 ->
0.9730 -- and makes the region it was added for *worse*: the right lobe's
coherent error goes 4.32% -> 4.86% and its ridge 4.16% -> 5.06%. It is not in
the model. This is the clearest case in the project of a change that a global
metric endorses and the measurement of the actual defect rejects.

**Rejected on measurement: the glow as gradients instead of blurred strokes.**
A filter's Gaussian is a three-pass box blur in both engines, departing from a
true Gaussian by 1.5-2.1 code values in coherent bands that follow the blurred
object -- which is exactly the shape a banding complaint would take. And the
replacement is in principle *exact* rather than approximate: the curves are lens
ellipses, so the iso-distance contours on the concave side are that ellipse
scaled, which is precisely what a radial gradient with the ellipse's own aspect
ratio paints, with the along-curve fade applied as a mask on the element (a mask
on a wrapping group isolates it and kills `mix-blend-mode`, exactly like
`clip-path`; verified in both engines). It was built and measured, and it
reconstructs the lobes *worse* than the blurred strokes do: 0.352 against 0.326.
The code has been removed rather than left in place unexercised, because this
project has already had one builder kind rot that way -- `arc_lens` referenced a
schema that no longer existed and would have crashed had anything used it. The
measurements are kept here instead, which is the part worth keeping.

**The gradient stop tolerance, and the wrong measure I first chose it with.**
The adaptive stop sampling was added while testing the interpolation hypothesis
above. With the hypothesis refuted it had to justify its bytes, and the first
attempt measured it against MAE: between 1 and 2 code values of tolerance the
file gives back 10.2 KB for 0.002 of MAE, so 2 looked free.

It is not free, because MAE is not sensitive to the thing a stop tolerance
controls. A piecewise-linear stop leaves a *contour ring*, coherent over
hundreds of pixels, and 0.15 counts of coherent ring is visible where 0.15
counts of grain is not. Measured properly -- each render differenced against one
at 0.15 counts, which has no rings, over the two lobes:

| tolerance | 0.35 | 0.70 | 1.00 | 2.00 | 4.00 |
|---|---|---|---|---|---|
| ring rms | 0.077 | 0.098 | 0.141 | 0.150 | 0.230 |
| worst ring | 1.33 | 1.33 | 1.67 | 3.00 | 4.33 |
| file (KB) | 130 | 104 | 94 | 83 | 77 |

Between 1 and 2 the rms barely moves and the *worst* ring doubles, 1.7 counts to
3.0, in lobes that sit at 8-35 counts. The shipped value is 1. Below it the file
grows much faster than the artifact shrinks.

**And the rings are mostly not the stops.** The same measurement bounds how much
of the visible contour structure stop density can account for: 0.14 counts rms,
against 0.76 counts of coherent cross-curve structure in the render overall. The
rest is the genuine curvature of the overlapping smooth gradients. Rendered in
arc-aligned coordinates and stretched to +-1.5 counts, the render shows several
overlapping families of smooth contours -- one per radial gradient centre -- and
the reference at the same stretch shows incoherent JPEG blocking. The reference's
own coherent structure there measures 0.51 counts, so the render's excess is real
but modest: 1.5x, not a different kind of thing. What differs as much as the
amplitude is that the reference's structure is buried in 0.88 counts of
incoherent grain and the render's is naked. That is an observation about why a
1.5x excess reads as strongly as it does -- not a reason to accept it, and not a
reason to add grain.

## D20. The profile weighting's strength is now a parameter, chosen by measurement

Fixing the squared-weight bug in D15 changed the objective's *strength*, not
only its correctness, and that had to be re-decided rather than inherited.

The bug made the profile term's objective coefficient `1/(n^2 (L+floor)^4)`
where the comments described `1/(n (L+floor)^2)` -- a fourth-power law in
brightness instead of a square, which leaned far harder on the dim far-lobe
cells than the design said it did. Correcting it to the documented form, with
the floor it had inherited, made the lobe interior measurably *worse*. So the
strength of the shaping had been doing real work by accident.

Two parameters were therefore separated and both settled by measurement, on a
colour-only fit from a fixed set of shapes:

* **The visibility floor**, 0.012 (3 code values) as inherited. Lowering it to
  0.006 (1.53 counts, about the quantisation scale) improves the coherent
  profile error from 0.781 to 0.665 counts and the cell error from 6.3% to
  5.6%; 0.003, 0.0015 and 0.0 are all within noise of 0.006 (0.665-0.690). So
  0.006, and the guard against chasing sub-quantisation error is kept.
* **The brightness exponent** `p`, now explicit in
  `EMPHASIS["profile"]["exponent"]`: the coefficient is
  `1/(n (L+floor)^(2p))`, so p = 1 equalises relative error across cells and
  larger p pushes past it. p = 1 is best on every measure -- MAE 1.967 against
  1.998 (p 1.5) and 2.050 (p 2.0), ridge error 2.53%/3.70% against 3.23%/7.75%
  and 4.81%/10.45%, interior 3.41%/4.26% against 3.95%/4.44% and
  4.83%/5.20%. The correct objective is also the best one; the bug was not
  compensating for anything, and the earlier reading that it was came from
  comparing a re-fit against a baseline whose *shapes* had been tuned to the
  old objective.

It is a parameter rather than a constant because nothing in principle fixes it
at 1 -- it is a claim about visibility, and this artwork answers it.

## D21. The central streak is centred on the core, with a falloff per side

**Decision.** `flare_streak` sits on the flare centre and carries a separate
falloff and gain for its east half (`profile_e`, `east_gain`), both searched.
`flare_ray_e` goes back to being a broad wedge rather than a thin spoke.

**Evidence.** The streak row cannot be measured naively: the two curve ridges
cross it at dx -65.5 and +14.5 from the flare core, so a window at dx -75..-40
or +15..+40 is entirely inside a curve's core and reads the core, not the
streak. Every earlier reading of this streak's asymmetry was taken that way. With
the ridges masked (ridge distance > 30 px) the reference's thin-line residual
above a 21-px median envelope is

| dx | -210..-160 | -160..-110 | -110..-75 | -40..-15 | +40..+75 | +75..+110 | +110..+160 | +160..+210 |
|---|---|---|---|---|---|---|---|---|
| reference | 5.15 | 11.75 | 19.44 | 31.57 | 15.85 | 7.14 | 3.07 | 1.62 |
| before | 5.65 | 17.14 | 38.63 | 15.70 | 2.28 | 1.39 | 0.29 | 0.01 |

Both sides fall off from the core, the west more slowly than the east. The
shipped layer instead displaced a *symmetric* streak 58 px west of the core with
a 37 px e-folding, and that one substitution produced three separate errors: its
peak sat 58 px off the core (15.70 at dx -40..-15 where the reference has 31.57,
38.63 at -110..-75 where it has 19.44), its east end truncated at core+158, and
the east side ran 7x too faint inside the span and to nothing outside it, where
the reference still carries 1.6-3.1 counts out to +210. The bounds could not have
recovered it either: `profile` was capped at 0.3 of a 215 px half-length, so the
reachable e-folding stopped at 65 px against a measured 77-90.

The thin-component angular scan says the same thing from the other direction:
at 0 degrees (due east) the reference reads 5.99 counts and the render 0.83.

**Effect.** Thin-line rms error along the streak 9.42 -> 6.14 code values at the
starting parameters, before any search, for +0.005 of whole-image MAE.

**`flare_ray_e`.** The same scan finds no thin spoke at 48 degrees: -0.58 counts
in the reference against +2.02 in the render. What D14 measured at 45-60 degrees
was a maximum in the *total* angular profile, which a broad wedge produces and a
thin spoke does not. Iteration 3 made every ray thin while chasing the six
spokes that are real, and then the fit drove this one hard to cover broad energy
with a thin primitive -- which is what turned the flare into a visible starburst.
The broad angular profile confirms the mechanism: at 165-180 degrees the render
is 3.5-9.0 counts too *dark* broadly while its thin line there is 7.2 counts too
*bright*. The westward energy was in the wrong shape, not the wrong amount.

**Not changed.** The six thin spokes at 91, 111, 225, 248, 265 and 328 degrees
stay: they are in the reference's thin-component scan at 1.2-3.5 counts and are
not an invention. Their amplitudes are over-driven (111 degrees reads 7.13
against 1.71, 249 reads 4.32 against 1.60) and that is left to the fit, because
the over-drive is a consequence of the two errors above and not a separate one.
