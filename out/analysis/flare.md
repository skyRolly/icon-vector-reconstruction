# The central light source — core, streak, rays, bloom

Component: the flare only. Full numbers in `out/analysis/flare.json`.
All coordinates are **pixel-index** (integer = pixel centre), the same frame as
`docs/stage1_findings.md`. **SVG user space = pixel-index + 0.5** (I did not re-derive
this; taken from the arc-geometry agent's calibration render).

Diagnostics: `flare_R_log.png`, `flare_zoom_R_g1.png`, `flare_hp3_G.png`, `flare_hp4_G.png`,
`flare_ray_GL.png`, `flare_ray_GR.png`, `flare_dblstreak_L/R.png`, `flare_test_blurcal.png`.

---

## 0. Read this first: three things that change the picture

1. **Use the R channel as the flare's channel.** On clean rows (y = 250, 300, 350, 400, 650,
   700, 750) each arc's *white* cross-section falls from ~200 at the core to 10–20 at
   |u| = 6–12 px and to the 2–5 LSB noise floor by |u| = 16 px. The cyan field has linear
   R/G ≈ 0.01–0.05 (8-bit R = 1–3). So **any 8-bit R > 10 more than 20 px from an arc ridge is
   flare light, and nothing else.** G and B are clipped at 255 over the whole box
   x ∈ [468, 560], y ∈ [500, 528], so every colour/amplitude claim inside that box is R-only.

2. **The flare's centre is not where the bright pixels are.** The streak+wings are symmetric
   about **x = 508.7 ± 2.5, y = 512.2 ± 0.3**. The brightest pixel (543, 514), the whole
   lum ≥ 250 patch and the two right-hand ray ridges all belong to a **separate compact
   element centred at (534.5, 514.3)** — 26 px further right (section 4).

3. **Both renderers blur in gamma space.** One SVG, three identical `feGaussianBlur`s tagged
   `linearRGB` / `sRGB` / default: resvg returns byte-identical output for all three
   (8-bit flux conserved exactly, linear flux 0.81 of nominal); chromium the same.
   `color-interpolation-filters` is ignored by both. The reference's decomposition only closes
   in *linear* light, so **do not plug my linear amplitudes into the SVG** — fit against the
   8-bit tables (`8_recommended_svg.eight_bit_targets`).

---

## 1. Centre

| quantity | value | σ | method |
|---|---|---|---|
| **flare centre x** | **508.7** | 2.5 | symmetric-exponential fit of the y-integrated linear-G streak flux over \|d\| ∈ [45,140] (187 samples, both wings at once): x_c = 508.75, L = 30.31 px, rms(lnF) = 0.156 |
| **flare centre y** | **512.2** | 0.3 | per-column parabolic peak of the streak; left wing (x 240–450) 512.404 ± 0.292, right wing (x 556–756) 511.855 ± 1.73; global line y = 513.027 − 0.00179·x |
| streak tilt | −0.103° | — | right end 0.44 px higher over 500 px; treat as horizontal |

Cross-checks on x: 511.5 (log-ratio match, |d| 60–120), 510.5 (|d| 80–160), 506.0 (|d| 100–200),
509.0 (white component R − 0.03G), 506–510 (wing matching of the 8-bit R cut at y = 512).
Left/right e-folding lengths are 29.9 vs 27.4 px — equal to 5%, so the two wings really are the
same object. The 2.5 px spread is model error (how the broad component is split between the
streak and the arcs' field), not noise.

**Offsets**

| reference point | Δx | Δy |
|---|---|---|
| canvas centre (512, 512) | −3.3 | +0.2 |
| **frame centre (508.5, 512.5)** | **+0.2** | **−0.3** |
| arcs' mirror axis x = 504.53 | +4.2 | — |
| arcs' own symmetry axis y = 514.85 | — | −2.65 |
| waist mid-height y = 517.3 | — | −5.1 |

The flare sits on the **frame** centre, to well inside its own error bar. It is 4.2 px right of
the arcs' mirror axis and 2.6–5.1 px above the waist. If the lead wants one anchor: use the
frame centre.

## 2. The saturated core

| threshold | total px | on arc core (\|u\| ≤ 4.5) | off-arc (\|u\| > 8) | off-arc bbox | centroid |
|---|---|---|---|---|---|
| lum ≥ 250 | 232 | 202 | 26 | x 527–536, y 511–514 | (531.9, 512.8) |
| lum ≥ 245 | 961 | 888 | 60 | x 525–536, y 510–516 | (531.3, 512.8) |

**There is no saturated core at the flare centre.** At (508.7, 512.2) lum = 224
(R 157, G 229, B 235) and nothing within 15 px reaches 245. Every lum ≥ 245 pixel is either on
an arc core or inside that little patch 22.6 px to the right.

Radial R profile from (531, 513) in 12 directions is tabulated in the JSON. Averaging the four
directions that clear both the arcs and the streak (θ = 90, 120, 240, 270):

```
r     0    2    4    6    8   10   13   16   20   25   30   40
R   242  232  213  194  173  154  130  105   78   48   18    4
```

Those four directions agree with each other to ±8 LSB out to r = 16 and ±14 out to r = 25, so
the core is **circular to ~5 % for r ≤ 16 px** and **stops being circular at r ≈ 16–20 px**,
where θ = 180 is still at 162 while the vertical directions are at 78–88 — the streak takes
over. Half-maximum radius: 13.2 px vertically (FWHM 26.4), ~23 px along +x, > 40 px along −x.
In **linear** light the vertical cut is a clean Gaussian, σ_y = 9.0–10.4 px for x ∈ [504, 530];
in 8-bit the same curve looks much flatter (gamma). The true peak is **unrecoverable** (R hits
254 in exactly one pixel, G and B are clipped everywhere in the patch).

## 3. The horizontal streak

* Ridge at y = 512.2, horizontal.
* **Transverse shape Gaussian, FWHM 4.8–5.4 px (x 370–450) and 4.5–6.3 px (x 556–666)**, i.e.
  σ_y = 2.2 px, **constant** with distance — it does not widen. (The apparent widening on the
  right is a second line leaking into the window, see below.)
* **Length**: flux ∝ exp(−|x−508.75| / 30.31) from |d| = 45 out to |d| ≈ 190; detected extent
  x ≈ 290 … 715, i.e. −219 / +206 px. **It does not reach the frame** (frame stroke centre-lines
  at x = 65.98 / 951.09) — it stops ~225 px short at each end. Stage 1's "almost the full width
  of the frame" is the visual impression of the low-level cyan field, not the streak.
* **Symmetric** left/right: e-folding 29.9 vs 27.4 px; amplitude ratio L/R = 1.0–1.3 at
  |d| = 60–100.
* **Colour** (linear, from the unclipped wings): R/G = 0.01–0.05 (mean 0.03, and R is on its
  1–3 LSB floor so this is an upper bound), B/G = 1.06–1.28 (mean 1.15) →
  **#2DF0FF** as a single colour (anything #00F0FF…#3CF0FF fits). But the colour **changes with
  radius**: R/G climbs 0.03 (|d| > 85) → 0.19 (|d| = 72) → 0.55 (|d| = 61) → > 0.9 inside
  |d| = 40. Deep cyan wings, pale core. Two layers (long cyan + short pale) reproduce it; one
  colour does not. The white sub-component W = linR − 0.03·linG is non-zero only for
  x ∈ [432, 588] — ±78 px about x = 510, best symmetry centre 509.0.
* **Secondary parallel lines (real, but not from a point source).** A second line at
  **y = 519.7 ± 0.4** exists for x ∈ [550, 690] at 0.85× the main amplitude at x = 560–600,
  falling to 0.5× by x = 700 — and is *absent* on the left (only a 0.30× shoulder at
  y = 518–520 for x ∈ [414, 450]). A third faint line at **y = 531.5 ± 0.7** spans x ≈ 300–760
  at 5–10 LSB (8-bit G) with a nearly flat x-profile. Control experiment: a synthetic bright
  thin line (peak 134 over background) written to JPEG at q = 75/85/92/96 with 4:2:0 chroma
  produces < 0.5 LSB of ringing at ±8 px, so at 28–37 LSB these are *not* compression ghosts.
  But two exactly-horizontal lines 8.1 px apart cannot both pass through one centre, and
  line 3's flat x-profile is not flare-like — they are probably artefacts of whatever produced
  the reference (XMP says Picasa). **Recommendation: model one streak.** Optionally add line 2
  as an independent thin cyan streak on the right half only.

A 55-row per-x table (peak, y-integrated flux, ridge y, vertical FWHM, per channel, linear and
8-bit) is in `3_horizontal_streak.profile_table`.

## 4. The second compact element — the thing that actually looks like the star

Not asked for, but it dominates the region and the lead must draw it.

* Centre **(534.5 ± 2, 514.3 ± 1.0)** — 9.7 px inside the right arc's apex (544.19), 26 px right
  of the flare centre.
* Carries every off-arc lum ≥ 245 pixel.
* From D = R − mirror(R about the arcs' axis 504.53) (which cancels the mirror-symmetric arcs
  exactly): at x = 532, D = 6/19/53/92/119/153/**170**/154/165/150/124/96/68/42/18/5 for
  y = 486…546 step 4 → **FWHM 35.5 px centred y = 514.8**; horizontally D peaks at x = 531
  (152–158) and falls to 20 by x = 510 and 7 by x = 585.
* Up/down symmetric to 10–20 % (D = 44/84/118/150/165 up vs 60/89/117/143/158 down at
  r = 20/16/12/8/4) — a round blob, not a lobe hugging the arc.
* Colour (linear, 6 points where G is still unclipped): dR/dG = 0.32 (spread 0.21–0.42),
  dB/dG = 1.05 → ≈ **#96E8EE**, a pale cyan, much whiter than the streak but not neutral.
* Its *y*-centre (514.8) equals the arcs' own symmetry axis (514.85), not the streak's 512.2;
  but the two right-hand ray ridges converge on it. **So it is either a second brighter "glint"
  of the flare placed on the right arc's apex, or an extra inner glow lobe of the right arc.**
  The reference cannot decide. Draw it as its own radial layer (section 6) — that reproduces the
  pixels either way. **Flag it to the arc-glow agent so it is not double-counted.**

## 5. Rays / spikes

Traced on the arc-subtracted residual (high-pass along the arc in arc-following (u, y)
coordinates, mean of G and B), sub-pixel transverse peak per row, then a straight-line fit
x = a + b·y. These are faint: 3–5 LSB above local backgrounds of 50–120, i.e. 3–10 % contrast.

| ray | line x = a + b·y | outward θ (0 = +x, y down) | fit rms | traced | FWHM | ang. width | peak | crosses y = 512.2 at x |
|---|---|---|---|---|---|---|---|---|
| dn-right | −250.53 + 1.53318·y | 33.1° | 1.92 px | x 547–672 | 17 px | 9.7° | 4.7 | **534.8** |
| up-right | 1004.66 − 0.91137·y | 312.3° | 1.60 px | x 549–613 | 15 px | 8.6° | 2.86 | **537.9** |
| up-left | −70.686 + 1.10346·y | 222.2° | 1.04 px | x 371–448 | 13 px | 7.4° | 3.84 | 494.5 |
| up-left B (marginal) | −149.81 + 1.1898·y | 220.0° | 2.74 px | y 458–498 | — | — | 3.5 | — |

* **Count 3 (+1 companion). No vertical pair.** The inter-arc strip x 470–540 has 8-bit R = 0–5
  for y < 484 and y > 548 — no vertical spike at all.
* **No ray below the streak on the left** (residual ±1.5 LSB over x 180–450, y 520–660).
* **Not symmetric, and the diagonal set is neither 4-fold nor 6-fold.** The two right-hand rays
  converge at (536.7, 513.5) — on the compact element of section 4, not on the streak centre.
* Falloff along dn-right: amplitude 5.7/9.9/10.7/7.1/9.1/5.2/3.5/3.2/2.6/1.7 at y = 528…600 step
  8 → peak at r ≈ 40–60 then exponential with scale ≈ 55 px.
* Caveat: everything that looked like a ray on first inspection near the arcs *was* the arcs' own
  glow. These three survived removal of a glow model that is smooth along the arc, and
  dn-right is also visible as a raw local maximum (x = 610–629 column mean peaks at y = 566,
  G = 60.05, where the fitted line predicts 567.7).

## 6. The bloom — and the arcs/flare split

**The bloom is not radial.** Vertical Gaussian σ_y = 9.0–10.4 px in white (R) and 21–26 px in
cyan (G) near the centre, against a horizontal e-folding of ≈ 30 px. Axis ratio ≈ 3–4 : 1.
There is **zero white beyond |Δy| = 45 px** on the vertical line x = 504 (8-bit R = 1–3 for
y < 484 and y > 548); cyan is detectable there to |Δy| ≈ 90 px and horizontally to |Δx| ≈ 210 px.

Vertical Gaussian fits (linear, streak bands excluded; amplitude, σ_y):

| x | 420 | 450 | 470 | 487 | 495 | 504 | 512 | 522 | 530 | 540 | 560 | 580 | 610 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| white R | — | — | .014 / 19.6 | — | .019 / 10.8 | **.128 / 10.4** | .356 / 9.3 | .636 / 9.0 | .443 / 10.2 | .281 / 12.8 | .089 / 13.5 | — | — |
| cyan G | .023 / 30.1 | .079 / 21.9 | — | .192 / 23.8 | — | **.357 / 25.9** | — | .637 / 21.2 | — | — | .182 / 16.9 | .095 / 28.8 | .024 / 25.9 |

**Form**: along x = 504, linear R with the streak bands excluded is a Gaussian, σ = 9.2 px,
peak 0.20, centred y = 514.3 — checked at r = 6/14/18/22/26 px, all implying A = 0.194–0.208.
Exponential and power-law fits are clearly worse (ln-residual rms 0.47 / 0.70 vs 0.29–0.53 for
the Gaussian).

**Decomposition, to avoid double-counting with the arc-glow agent**

* **White (R) is 100 % flare.** The arcs contribute nothing above the noise floor beyond
  |u| = 16 px, and on the line x = 504 R is at the floor for y < 484 / y > 548. Don't let the
  arc model claim any R beyond |u| = 16.
* **Cyan (G) on the vertical line x = 504** (arc pedestal 0.0499 linear, from y = 443/592):
  flare share 81 % at y = 496, 89 % at 504, **93 % at 512**, 92 % at 516, 87 % at 524, 83 % at
  532, 81 % at 540.
* **Cyan (G) on the horizontal centre line y = 512** (pedestal = mean of linear G at
  (x, 443) and (x, 592)): flare share 38 % at x = 300, 40 % at 340, 43 % at 380, 49 % at 400,
  53 % at 420, 54 % at 440 — and 64 % at 570, 65 % at 590, 57 % at 610, 50 % at 630, 43 % at
  650, 37 % at 690. Roughly **50/50 at |d| = 60–120 px and 40/60 (flare/arcs) beyond
  |d| = 150 px**. (x = 460 and 550 are unusable: the pedestal rows contain an arc core.)

## 7. Recommended SVG

Full layer spec with geometry, colours, opacities, sigmas and the numeric check is in
`8_recommended_svg`. Summary:

| layer | geometry | paint | blur |
|---|---|---|---|
| `streak-cyan` | rect x 258 → 760, centre (509.2, 512.7) SVG, height 4 | `#2DF0FF`, horizontal `linearGradient` with opacity stops following exp(−\|d\|/30.3): 0.001, 0.006, 0.031, 0.15, 0.55, 1.0, 0.55, 0.15, 0.031, 0.006, 0.001 | `stdDeviation="0 2.0"` → **verified FWHM 5.46 px** |
| `streak-white` | same centre, half-length 78 px (x 431…587) | `#D8F6FA`, gradient exp(−\|d\|/24) | same |
| `bloom-cyan` | ellipse at (509.2, 514.5) | `#2DF0FF` | `stdDeviation="40 24"` |
| `bloom-pale` | ellipse at (509.2, 514.5) | `#A8EEF4` | `stdDeviation="30 9"` |
| `glint` | circle r = 6 at (535.0, 514.8) | `#F2FEFF`, must clip to white over x 525–547, y 508–518 | `stdDeviation="11"` → FWHM ≈ 30 |
| `spikes` ×3 | rect L 150 × H 16, rotated 33.1° and 312.3° about (535.5, 514.0), 222.2° about (495.0, 512.7) | `#7FE8F5` at opacity 0.06–0.10, gradient peaking at 30 % of the length | `stdDeviation="0 5"` in the rotated frame |

**Renderer calibration (measured, resvg @1024)** — rect height / stdDeviation → rendered 8-bit
FWHM: (1, 1.5) → 3.32; (1, 2.0) → 4.87; (1, 2.2) → 5.82; (2, 2.0) → 4.78; **(4, 2.0) → 5.46**;
(4, 2.2) → 6.19; (6, 1.8) → 6.37; (1, 4.0) → 11.33; (12, 9.0) → 23.50.
Rule: σ_rendered ≈ √(stdDeviation² + h²/12) for stdDeviation ≤ 3, +10–20 % above that.
**Gotcha**: with a 1–4 px tall rect, percentage filter regions (`y="-500%" height="1100%"`) give
only ±5…20 px and truncate the blur — use `filterUnits="userSpaceOnUse"` with explicit bounds on
every flare filter.

**Not faithfully reproducible**

* The reference is additive in *linear* light; both renderers blur and composite in *gamma*
  space. Exact photometry is therefore impossible — fit the 8-bit targets with
  `screen` / `plus-lighter` and accept a residual in the wings.
* The colour ramp along the streak (deep cyan wings → pale core) *can* be done in one shape by
  putting both colour and opacity stops in the same `linearGradient` — that is the cheapest
  faithful approximation and is what I recommend.
* The right-only second line at y = 519.7 has no single-primitive equivalent (add a clipped rect
  if wanted).
* The rays are not concentric with the streak, so no rotational starburst primitive works —
  three individually placed rotated rects are needed.
* The true peak radiance of the core and of the glint is unrecoverable (G, B clipped
  everywhere in the patch); any model that clips to white over x 525–547, y 508–518 matches.
