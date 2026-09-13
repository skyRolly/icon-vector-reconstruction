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
in the lobes its total cross-curve band-pass amplitude is 0.51 counts rms at
sigma 3 against the reference's 0.68, and across the open interior 0.10-0.28
against 0.49-0.65 -- a third of it. Blurring would score better still. What
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

**Refuted for the lobe as a whole, confirmed for the ridge strip: one bad
layer.** Removing each layer in turn and scoring the *whole* lobe moves the
coherent amplitude by at most 1.6%, and removing the field layers makes it
slightly worse -- the fit has arranged partial cancellation between them. That
is the answer to the wrong question, because the whole-lobe figure dilutes the
strip where the excess actually is. Scored on the ridge strip alone the answer is
unambiguous: removing `arc_glow1` takes it from 0.9215 to 0.2370 counts on the
left curve and 0.7507 to 0.3017 on the right -- **74% and 60%** of the total,
against the reference's own 0.4950 and 0.5791. `arc_glow1c` accounts for 4% and
8%, and every other layer for under 1%. Removing `arc_glow1` overshoots to 0.48x
and 0.52x of the reference, so the layer is not spurious: its cross-curve
profile is too sharp, and the amount by which is measurable against the
reference's own coherent amplitude rather than against a preference for
smoothness.

**And softening it is not the fix.** `arc_glow1`'s blur is the one parameter
that sets how much 3-px-scale cross-curve content it puts in that strip, so it
was swept with the cost reported beside the gain:

| blur | sigma_eff | ridge coh L | ridge coh R | MAE | SSIM | ridge profile err | interior |
|---|---|---|---|---|---|---|---|
| 5.108 | 5.8 | 1.85x | 1.30x | **1.9723** | **0.9726** | **4.00%** | **4.13%** |
| 7.0 | 7.6 | 1.99x | 1.52x | 1.9968 | 0.9720 | 3.39% | 5.36% |
| 9.0 | 9.4 | 1.68x | 1.36x | 2.0406 | 0.9712 | 4.52% | 5.17% |
| 11.0 | 11.4 | 1.34x | 1.16x | 2.0946 | 0.9705 | 5.96% | 5.07% |
| 12.0 | 12.3 | 1.20x | 1.06x | 2.1181 | 0.9700 | 6.55% | 5.10% |

Blurring the layer does bring the coherence ratio down, from 1.85x to 1.20x, and
makes the *profile error in the same strip worse* as it does so -- 4.00% to
6.55% -- along with the global MAE (+0.146) and SSIM. This is the blur-to-satisfy-
the-metric outcome that the two-sided target exists to catch, caught here by the
measurements beside it. The layer is left as it is.

What that leaves is a real limitation of the blurred-stroke family rather than a
parameter error: a blurred stroke that matches the reference's *level* in the
14-40 px strip necessarily carries more 3-px-scale cross-curve structure there
than the reference does, and the two cannot be separated by choosing a blur.
Separating them needs a primitive whose profile can be flat-topped where a
Gaussian is peaked -- a change of kind, on the evidence above, and not one to
make blind at the end of an iteration.

**What it actually is: two defects, in different places, with different causes.**
Localising the error in cross-curve distance separates them, and pooling them
was what made the earlier readings contradictory.

*Inside 40 px of the ridge* the glow basis cannot reach the reference's shape.
The effective cross-curve widths of the glow strokes step 5.8 px (`arc_glow1`)
to 20.6 px (`arc_glow2`), a factor of 3.5, and the best achievable residual
peaks inside that step and changes sign across it. Adding one stroke in the gap
raises the best achievable accuracy there -- the profile-only non-negative fit,
scored on the same grid as everything else -- from 1.08%/0.49% to 0.32%/0.19%
(left/right), and its oscillatory part from 0.711%/0.253% to 0.196%/0.165%.
Three candidate widths between sigma_eff 10 and 12.5 px all do it; the shipped
one is width 20, blur 8, inset 10. Position matters as much as width: the same
effective width at inset 14 instead of 6-10 is markedly worse. That is the
evidence for `arc_glow1c` -- one blurred stroke on the existing Bezier path, six
numbers, no new geometry.

It is **not in the shipped model.** The capacity it buys is real and so is the
measurement, but capacity is what the basis *could* reach and the fit never
reached it: adding the layer and re-fitting moved the achieved ridge excess from
1.82x to 1.81x on the left curve and 1.21x to 1.23x on the right, while the
reconstruction as a whole measured worse (D22). The layer waits for a search
that can exploit it against the corrected objective and the corrected builder
(D23), and this entry is the record of what it would buy if one does.

*Beyond 40 px* the basis can reach the reference's profile to 0.89%/0.97%, but
not while the rest of the image is fitted. The profile-only optimum gets there
by using 13 of 29 layers and wrecking everything else: global MAE 1.90 -> 8.20,
frame 1.30 -> 7.48, centre 90 px 7.53 -> 35.16, between the curves 4.34 ->
24.86. So that bound is not a target. The lobe's pedestal comes from field,
exterior and flare layers that are pinned by their duties elsewhere, and what
remains in the interior is the price of a shared basis, not a fitting failure.
It is stated here rather than hidden because it is the honest limit of this
model: driving the interior to its bound would take a different decomposition,
not a better fit.

**Rejected on measurement: a lobe-localised field component.** The obvious way
to give the interior its own freedom is a soft radial gradient centred in each
lobe. It improves the global metrics -- MAE 1.9849 -> 1.9619, SSIM 0.9720 ->
0.9730 -- and makes the region it was added for *worse*: the right lobe's
coherent profile error goes 4.32% -> 4.86% and its ridge 4.16% -> 5.06%
(measured on the grid in use at the time; the ordering is what matters and it is
unambiguous). It is not in the model. This is the clearest case in the project of
a change that a global metric endorses and the measurement of the actual defect
rejects.

**Also rejected on measurement: replacing `field_grad`'s profile table.** Its
table has a pronounced non-monotonic dip, and the lobes sit at u = 0.47-0.82 of
its radius -- right across it -- so it was a plausible source of contour
structure. Replacing it with a monotone power law or a monotone table leaves the
coherent structure identical (0.763/0.531 counts against 0.763/0.533 shipped)
and costs real accuracy: MAE 2.0280 and 2.0552 against 1.9908. The dip had
already survived an evidence test on fit quality alone (residual 1.246 against
1.297 for the best power law and 1.780 for flat); it now survives one on
structure too.

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
of the visible contour structure stop density can account for at all: 0.14
counts rms. The rest is the genuine curvature of the overlapping smooth
gradients. Rendered in arc-aligned coordinates and stretched to +-1.5 counts,
the render shows several overlapping families of smooth contours -- one per
radial gradient centre -- where the reference at the same stretch shows
incoherent JPEG blocking. That is a real difference in *kind*, and it is why a
modest excess reads as strongly as it does: structure of the same amplitude is
buried under 0.7-0.9 counts of grain in the reference and is naked in the
render. It is not a reason to accept the excess, and not a reason to add grain.

**Where the excess actually is, and three ways of mismeasuring it.** Localised
in cross-curve distance on a grid where every along-curve average is taken over
the same 481 stations, the render's excess coherent structure sits entirely in
the 26 px strip beside the ridge: at sigma 3 it is 1.81x the reference's on the
left curve and 1.23x on the right, falling to 0.96x and 0.93x by sigma 12. From
40 px outwards -- the whole open lobe, which is what the complaint describes --
the render runs 0.68x to 1.04x, at or below the reference, and its *total*
cross-curve amplitude there is a third of the reference's. Cell by cell in
(distance x along-curve angle) the same thing: 0.9-2.7x in the ridge strip, and
0.03-0.7x everywhere beyond it, on both curves in every band.

Getting that localisation wrong is easy, and it was got wrong three times before
it was got right, each time in a way that inverted a conclusion:

* *Partial along-curve averages.* Accepting any sampling row with 60 of 481
  stations inside the region let rows averaged over short unrepresentative arc
  segments dominate: they put the reference's coherent amplitude at 0.508 counts
  and the render's at 0.764, an apparent 1.5x excess over the whole lobe, where
  on fully populated rows the same statistic gives 0.116 and 0.082 -- the render
  *below* the reference. Six rows out of 287 were carrying the conclusion. The
  region is now the frame interior split at the mirror axis, where all 481
  stations are fully inside.
* *Edge-biased smoothing.* A `mode="same"` convolution pads with zeros, so the
  nine rows nearest each end of the cross-curve run are meaningless. Trimming
  them removes the ridge strip, which is exactly where the excess is; that is
  how a per-band measurement came to read 0.32-0.87x and suggest the defect was
  one of *persistence* along the curve rather than amplitude. It is not: with
  edge-normalised smoothing the per-band and whole-arc figures agree to 6%.
* *Pooling the two regions.* One number for the lobe is dominated by the ridge
  strip, because that is where the amplitudes are, and reads as though the whole
  lobe were over-structured. `band_report` reports them separately.

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

## D22. Iteration 3's model changes did not improve the reconstruction

**The measurement.** Rendered at 1024 px against `reference.png`, every state
iteration 3 produced is worse than the iteration-2 baseline:

| state | layers | MAE | SSIM | flare r<110 | worst channel |
|---|---|---|---|---|---|
| iteration 2 (committed) | 29 | **1.9411** | **0.9731** | **7.602** | **105** |
| iteration 3, flare rebuild | 33 | 1.9818 | 0.9723 | 8.600 | 108 |
| + `arc_glow1c` | 34 | 1.9899 | 0.9728 | 8.498 | 110 |
| + one shapes sweep | 34 | 1.9661 | 0.9726 | 8.239 | 112 |
| + the streak primitive and a flare sweep | 34 | 1.9794 | 0.9724 | 8.310 | 112 |

The regional and targeted numbers agree: the glow profile's rms relative error
goes 4.08% -> 4.59%, the cell figure 5.19% -> 6.02%, both lobes' MAE up, and on
the arc-masked streak measurement the thin-line error goes 4.98 -> 5.72 counts.
Only the frame band, the bright pixels and the interior corners improved.

This is recorded as a decision rather than left in a commit message because the
conclusion has to survive the iteration: a change is not an improvement because
it is newer or better argued, and the artwork that ships is the one that
measures best.

**The flare rebuild was already a regression before this iteration's work
started.** At 33 layers it rendered 1.9818 against 1.9411, with the flare's own
region 8.600 against 7.602 -- the region it was rebuilt to fix. Its individual
measurements were sound (the streak comb's satellites, the six thin spokes at
their measured angles); what went wrong was downstream of them.

**One cause is identified and fixed.** `flare_cells` masked the curve ridges by
13 px. The ridges cross the streak row 14.5 px east and 65.5 px west of the
flare centre and the curve's glow reaches far past that, so a third of the comb
cells were scoring curve glow and calling it the comb -- and the flare search
optimised toward it. The signature is unambiguous: with the margin at 13 the
search drove the streak's west side to 9.6/20.1/26.7 counts where the reference
has 5.2/11.8/19.4, and its east side down to 6.2 where the reference has 15.9,
which is the *opposite* of what the same lines measured with the ridges properly
masked ask for. The margin is now 30 px, which is what the measurement needs to
come out clean, and it drops 9 comb and 17 sector cells.

**The other cause is search, not model.** The baseline's parameters accumulated
many sweeps of every spec across iteration 2. Iteration 3 changed the objective
twice over (the squared-weight correction, then the floor and exponent of D20)
and the shapes have had one sweep against the result. A colour-only re-fit of
the *baseline* under the corrected objective already costs it 0.03 of MAE, which
is the size of the whole regression: the parameters are not converged for the
objective they are now being scored against.

**What is not claimed.** That the model changes are wrong. `arc_glow1c` raises
the ridge strip's achievable accuracy 3.4x/2.6x (D19) and the streak's per-side
falloff is measured with the ridges masked (D21); both are better-founded than
what they replace. What is claimed is only that the reconstruction they produce
has not yet been optimised well enough to beat the one they replace, and until
it is, it does not ship.

## D23. The stop rewrite was the regression; the filter region was the fix

**How the iteration-3 regression decomposed.** D22 recorded that every
iteration-3 state rendered worse than the iteration-2 baseline and named two
suspected causes, both in the parameters. Both were wrong about where most of it
was. Rendering the *same* iteration-2 parameters through each builder separates
the code from the fit, and the answer is a 2x2:

| gradient stops | filter region | MAE | SSIM | flare r<110 | file |
|---|---|---|---|---|---|
| measured stations, verbatim | frame bbox +-4 px | 1.9411 | 0.9731 | 7.602 | 72.3 KB |
| **measured stations, verbatim** | **scaled to the blur** | **1.9352** | **0.9734** | **7.602** | **72.2 KB** |
| PCHIP, adaptively resampled | frame bbox +-4 px | 1.9763 | 0.9721 | 7.693 | 79.7 KB |
| PCHIP, adaptively resampled | scaled to the blur | 1.9594 | 0.9725 | 7.693 | 79.6 KB |

So of the changes made to the builder during iteration 3, one was a genuine
improvement and the other a genuine regression, and pooling them hid both:

* **The filter region was wrong and its correction helps.** It had been clamped
  to the frame's bounding box plus 4 px *regardless of the blur width*, with a
  comment asserting that was lossless because filtering precedes clipping. A
  filter region clips the filter's SOURCE, so a sigma-76 haze was being built
  from a truncated source. Scaling the region to the blur's own padding is
  worth -0.0059 of MAE and +0.0003 of SSIM on identical parameters.
* **The adaptive PCHIP stops were a regression: +0.0242 of MAE, -0.0009 of
  SSIM and 7.4 KB.** They were added while testing whether stop interpolation
  caused the lobe banding, which it does not (D19), and then kept on the
  argument that a smooth interpolant represents the intended profile more
  faithfully than straight segments between knots.

**Why the smooth interpolant is the wrong choice here, not merely a costly one.**
The knots are not control points for a curve someone designed; for the tapers
and the field table they are a MEASUREMENT, station by station along each arc.
Linear interpolation between measured stations is the minimal assumption. A
monotone cubic through them asserts curvature in between that nothing measured
-- and the change shipped a smoothing pass with it, a 7-point window over the
measured alphas, which discards measured detail outright. The amplitudes were
then fitted against the linear reading and are correct for it. Both are
reverted; the machinery is removed rather than left unexercised, and this entry
is the record of what it cost.

**The consequence for the baseline.** Iteration 2's parameters, built with the
corrected filter region and the measured stations emitted verbatim, render at
**MAE 1.9352, SSIM 0.9734, flare 7.602, worst channel 105, 72.2 KB** -- better
than the iteration-2 commit on the global metrics, identical in the flare, and
slightly smaller, with no parameter changed. That is the baseline this iteration
proceeds from, and it is a *code* improvement: the previous numbers were held
back by a truncated filter source.

**What this says about the rest of the iteration-3 regression.** With 0.0183 of
the 0.0438 attributable to the builder, the remainder is the parameters -- and
they were searched against an objective that changed twice underneath them. It
does not establish that the model additions are wrong, and it does not establish
that they are right. They stay out until a search against the corrected
objective and the corrected builder puts them ahead of this baseline.

## D24. The central light's horizontal lines are three features, not one

**Evidence.** The reference carries three distinct horizontal lines through and
below the flare core. Their centres, from a shared-centre three-Gaussian fit and
cross-checked model-free against `L(y) - 0.5*[L(y-k) + L(y+k)]`, with every
window masked to more than 30 px from either curve ridge:

| line | dy from the core row | reach | shape |
|---|---|---|---|
| A | **-0.283 +- 0.037** | 300 px W, 240 px E | FWHM 4.64 +- 0.10 px |
| B | **+6.740 +- 0.055** | dies past abs(dx) 130 | short |
| C | **+19.329 +- 0.065** | 300 px W, 240 px E | faint, and NOT decaying from the core |

The masking is not a detail. The ridges cross the streak row 65.5 px west and
14.5 px east of the core, so the windows at dx +15..+40 and -75..-40 lie
entirely inside a curve's core: an unmasked measurement there reads the curve,
which is how earlier work came to describe this family as a west-displaced
symmetric streak (D21).

**Line A passes THROUGH the core, not below it.** Its centre is 0.28 px above
the stated core row, so the "prominent line below the bright point" of the
report is this streak; only B and C are below.

**Line C cannot be emitted from the core at all.** It rises from an inner
cut-off near abs(dx) 80, peaks at 5.6 counts around abs(dx) 110-170, then falls
-- reaching 240 px east and 300 px west. Neither an exponential (log-rms
0.27-0.36) nor a power law (0.30-0.40) fits it. Any primitive whose amplitude
decays monotonically outward is the wrong shape, whatever its parameters, so it
gets an explicit non-monotone knot table, which `profile_stops` emits verbatim.

**Refuted and therefore not built:** a line at dy +12 (an inverse-variance stack
of ten far bins reads 0.000 at +11.2 and 0.105 at +12.2, below 1 sigma -- the
earlier suggestion came from the 21-px median envelope overshooting in the
trough between B and C); slab-shaped cross-sections (a generalised Gaussian of
exponent 4 fits worse than Gaussian or Lorentzian in every bin); and the earlier
satellite positions +6.5 and +18.5 (+19.329 is 12 sigma from +18.5, which
matters for a 5-px feature).

**What the baseline had.** Three streak layers all at dy ~ 0, stacked on the
core row with sigma_y 3.56, 2.45 and 10.85 -- which is why the rendered line A
measures 9.6 px FWHM against 4.64, and why B and C were absent outright: line C
read -0.11 to +0.15 counts across 390 masked columns where the reference reads
3.0-4.8.

**A mapping error worth recording.** The measurement says the main streak's east
side follows a power law of index 2.10 -- meaning amplitude proportional to
abs(dx)^-2.1. The builder's `pow` profile emits `(1 - u)^k`, which is a
different function entirely, and substituting one for the other put 2-3x too
much light along the east side from abs(dx) 70 outward (12.4 counts at +70
against a reference 6.97). Both sides are now explicit tables of the measured
amplitudes, which is also the minimal assumption between measured points (D23).
The innermost east knot is held flat rather than extrapolated to a spike,
because the right curve's ridge masks abs(dx) < 40 there and a spike inward of
it would be invented, not measured.

**Four representations were built and measured.** The line amplitudes below are
the model-free row difference of `tools/line_report.py`, rms over the 14 masked
`dx` bins, against the reference:

| representation of line A | line A | line B | line C | total | MAE |
|---|---|---|---|---|---|
| baseline (no B, no C, one wide streak) | 6.38 | 10.53 | 3.08 | 20.00 | 1.9352 |
| east `(1-u)^2.10` | 8.93 | 7.18 | 1.44 | 17.55 | 1.9496 |
| both sides sparse measured tables | 4.84 | 7.40 | 1.40 | 13.64 | 1.9386 |
| **west exponential, east measured table** | **3.30** | 8.05 | 1.42 | **12.77** | 1.9367 |
| west dense log-interpolated table | 5.49 | 7.18 | 1.41 | 14.08 | 1.9401 |

Two of those are my own errors, and both were caught by measurement rather than
by argument:

* The measurement says the east side follows a power law of index 2.10, meaning
  amplitude proportional to `abs(dx)^-2.1`. The builder's `pow` profile emits
  `(1 - u)^k`. Substituting one for the other put 2-3x too much light along the
  east side from `abs(dx)` 70 outward -- 12.4 counts at +70 against a reference
  6.97 -- and made line A *worse* than the baseline that lacked two of the three
  lines entirely.
* A dense table log-interpolated between the measured points flattens the
  near-core profile, and then the fit cannot reach the peak: 18.11 counts at
  `dx` -36 against a reference 34.95. The reason is that 34.95 is a BIN MEAN over
  `abs(dx)` 17-36, a range across which the profile falls steeply, so it
  under-represents the peak and a table anchored on it is too flat. The
  exponential law's own curvature is the better reading of the same data.

**Shipped:** line A's west as the exponential law (e-folding 64.7 px), its east
as the measured table, line B as an exponential of e-folding 37.4 px at
dy +6.740, and line C as the non-monotone table at dy +19.329.

**What it costs and what it buys.** The line-structure error falls 36%, from
20.00 to 12.77, and line C goes from absent -- `-0.11` to `+0.15` counts across
390 masked columns where the reference reads 3.0-4.8 -- to within about a count
on both sides. Against that: whole-image MAE rises 0.0015 (0.08%), SSIM is
unchanged at 0.9734, the worst single-channel error *improves* from 105 to 104
and the fraction of pixels off by more than 2 improves from 35.80% to 35.66%,
while the flare region's own MAE rises 0.42 (7.6016 to 8.0178). That regional
cost is the open item: the bloom, halos and rays underneath the lines have not
been re-searched since the lines changed, and the flare geometry search is the
next step, not a reason to reject the decomposition.

## D25. Fitting a new flare component without discarding the validated colours

**The problem.** Introducing a layer needs a photometric fit, and a full re-fit
of every layer under the current objective measures *worse* than the colour
solution iteration 2 already has: same geometry, full re-fit, MAE 1.9480 against
1.9352. So a full re-fit would trade a validated solution for the objective's
own optimum and, worse, would hide whether the new layer helped -- the
comparison would confound the layer with the re-fit.

**The decision.** Fit only the layers the change touches, with
`FP.fit(free=...)`, and leave every other layer's colour exactly as it was
(`tools/fit_only.py` in the scratch tooling drives it; the same `free` mechanism
the optimiser uses per family). Every flare result in D24 is measured this way:
the eleven `flare_*` layers are free and the nineteen others are frozen at
iteration 2's values, so the reported change is the change the flare model made.

**Why this is not just convenience.** It is the same requirement as the
geometry-trial fix in this iteration's optimiser work: a comparison is only
about the thing being changed if everything else is held equal. A full re-fit on
each side of the comparison changes nineteen layers that the flare model has
nothing to do with.

**What it does not settle.** That the current objective's optimum is worse on
the unweighted metrics than iteration 2's is itself unexplained, and it is the
open question behind D22. Iteration 2's colours were fitted under the
squared-weight bug, so they minimise a quartic-weighted objective; that they
also give lower MAE and higher SSIM than the corrected objective's optimum is a
fact about this artwork that neither objective was designed to optimise. It is
recorded here as a thing to explain rather than a thing to exploit.
