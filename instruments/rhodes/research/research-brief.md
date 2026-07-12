# Rhodes (tine electric piano) — research brief

Working engineering brief for the sample-free Rhodes model (`rhodes / mk1`,
reference: jRhodes3d 1977 Mark I Stage 73 — see `../SOURCES.md`).
Compiled 2026-07-11 from the papers in this directory (all open-access PDFs
downloaded here; paywalled items cited with abstracts) plus standard beam /
electromagnetics results.

---

## 1. Signal chain overview

```
key → hammer (neoprene tip) → tine (steel cantilever, ~sinusoidal after ~10 ms)
        ⇅ coupled at clamp                                  |
      tonebar (brass/cast-iron "second prong", energy store)|
                                                            v
              electromagnetic pickup  = memoryless nonlinearity Φ(x) + d/dt
                                                            |
              passive coil/cable electrical filter (R-L-C)  → output jack
```

Two decisive experimental facts anchor everything below:

1. **The tine motion itself is almost a pure decaying sinusoid.** High-speed
   camera tracking (38 kHz frame rate) of a struck tine shows that after an
   extremely short transient (waveform steady after **10–14 ms**) the tip
   moves sinusoidally at f0 with *no measurable higher modes*
   [Münster & Pfeifle 2014, §3.1–3.2; Pfeifle & Münster 2017].
2. **Virtually all harmonic content of the output is created by the pickup
   nonlinearity**, not by the string-like source. The voltage behind the
   pickup is strongly distorted even while the camera sees a sine
   [Münster & Pfeifle 2014 Fig. 9; Pfeifle 2017 Fig. 3]. Timbre = f(tine
   amplitude, tine rest position in the field) — hence velocity-dependent
   and decay-time-varying spectrum.

This is the best possible news for a modal engine: the source is one mode;
the spectrum is a *waveshaped* version of it (see §7).

---

## 2. Tine (generator)

### Geometry / materials
- Spring-steel wire ("piano wire", high-carbon), **diameter 1.5 mm**
  (Shear 2011 thesis; the 1961 patent specifies 0.075 in ≈ 1.9 mm — varies
  by era), cylindrical except a thickening at the base on later tines.
- **Lengths 18–157 mm** across the keyboard; shrunk (liquid nitrogen) into an
  aluminium block → near-ideal clamped-free (cantilever) boundary.
- f0 range: **27 Hz–4.2 kHz (88-key)**, **41 Hz–2.6 kHz (73-key)**
  [Shear & Wright 2011]. Our Stage 73 reference: E1..E7 region.
- Tip displacement up to **50 mm** for the longest tines, <1 mm for the
  shortest [Shear & Wright 2011] — low notes are *deep* into the pickup
  nonlinearity, high notes barely leave the linear zone. This single fact
  explains why "growl/bark" lives in the bass register.

### Modal structure
Euler–Bernoulli clamped-free beam: ρ ∂²u/∂t² + EI ∂⁴u/∂x⁴ = f, with
cos(kL)·cosh(kL) = −1 → k_nL = 1.8751, 4.6941, 7.8548, 10.9955, …

- Frequency ratios of a *uniform* cantilever: f_n/f_1 = (k_nL/k_1L)² =
  **1 : 6.267 : 17.55 : 34.39 : …** — strongly inharmonic, "bell-like".
- f1 for a round wire of radius r: f1 = (1.8751²/4π)·(r/L²)·√(E/ϱ).
- **Tuning spring**: a small coil spring wrapped around the *free end*;
  sliding it changes tip mass loading → f0. Patent: springs sit "relatively
  close to the free ends … in order that variations in spring locations
  will alter the fundamental frequencies and not the harmonics"
  [US 2,972,922]. Tip mass lowers f1 more than f2, f3 → measured overtone
  ratios sit *above* the uniform-beam 6.27/17.55 and vary per note. Do not
  hardcode 6.267; fit per note from the attack transient.
- Pfeifle 2017 models the tine as a **shear beam** (Traill-Nash & Collar):
  shear correction improves both f0 and higher-partial accuracy over plain
  Euler–Bernoulli; also adds two transverse polarizations coupled by a
  Kirchhoff-like large-deflection term (Eq. 2–3 of the paper). Vertical
  (hammer-direction) polarization dominates; horizontal is weakly excited.
- **Higher tine modes only matter in the first ~10 ms.** They are visible
  in the attack (with the tonebar ring) and then gone (camera sees pure
  f0). Gabrielli et al. 2020 (JASA, SLDV measurements) mapped which
  inharmonic attack modes are *perceptually relevant* across the keyboard
  and matched synthesis to recordings — attack-only inharmonic partials +
  pickup intermodulation.

### Decay
- Measured Q of tine/tonebar systems, midrange [Shear 2011 thesis, Table 5.1]:
  B3 (246.9 Hz) Q=1101, C4 (261.6) Q=1238, D♭4 (277.1) Q=1040,
  D4 (293.7) Q=1156, E♭4 (311.1) Q=1520.
  → amplitude time constant τ = Q/(πf) ≈ **1.3–1.6 s** midrange,
  i.e. T60 ≈ 6.9·τ ≈ **9–11 s**.
- Patent design goal: "initial percussive effect followed by relatively
  rapid decay and then limited dwell, **longer at the lower pitches**"
  [US 2,972,922]. Expect τ to grow toward the bass (calibrate per note).
- Note the *output* harmonics decay faster than the tine itself (§7).

---

## 3. Tonebar (asymmetric tuning fork)

- A stiff brass bar (cast iron in the 1961 patent; brass in production
  Mark I/II; sometimes twisted 90° = "twisted tonebar") mounted parallel to
  the tine, joined rigidly through the aluminium clamp block — the "second
  prong" of Rhodes' patented asymmetric tuning fork. Patent mass ratio:
  tonebar ≈ **10–25× the tine mass** [US 2,972,922].
- **It is NOT tuned to the tine.** Measured lowest eigenfrequencies differ
  from the sounding note by hundreds to >1400 cents, discrepancy growing
  with pitch [Münster & Pfeifle 2014, Table 1]: e.g. bar #33: tonebar
  f0 = 105 Hz vs output 263 Hz; bar #68: 222 Hz vs 1969 Hz.
- After the strike the tonebar is *enslaved*: it vibrates exactly at the
  tine frequency, perfectly in phase or anti-phase (synergetics /
  generator–resonator coupling). Its own eigenfrequencies appear **only in
  the attack transient**.
- Roles for the model:
  1. **Sustain/efficiency**: energy reservoir; feeds energy back to the
     tine (patent's stated purpose; low-Q "flat resonance curve" material
     chosen deliberately). Its effect is already inside the measured
     per-note decay rates — no separate mechanism needed.
  2. **Attack timbre**: adds the metallic "glockenspiel" ring
     (its transverse + longitudinal modes; longitudinal waves in the bar
     transfer into transverse tine motion through the T-joint) — model as
     a handful of fast-decaying inharmonic attack partials.
  3. **Beating**: because tine and tonebar eigenfrequencies are unrelated,
     slight frequency proximity between an attack partial and a pickup
     harmonic produces audible early beating on some notes — a per-note
     measured effect, not a systematic law.

---

## 4. Electromagnetic pickup (the timbre-maker)

### Physics
Coil around a permanent magnet with a shaped (wedge/frustum) pole tip,
mounted **coaxially with the tine**, tip ~1 mm-scale from the tine tip; the
tine vibrates transversely across the field concentrated at the tip edge
(different geometry from a guitar pickup, same physics). Faraday:

  u(t) = −N dΦ/dt = −N (∂Φ/∂x) · ẋ(t)

Flux vs tip position (Falaize & Hélie 2015, Eq. 4, after Horton & Moore
2009 / McDonald 2007 magnetic-dipole treatment):

  Φ_c(q) = ( a_c + Δμ·a_b / (q + l_p)² ) · Φ_0,  Δμ = (μrel−1)/(μrel+1)

i.e. an inverse-square-like law in the tine–pickup distance. FEM of the
actual Rhodes tip [Pfeifle & Münster, DAGA 2017] shows the field magnitude
across the tine's swing path is an approximate **bell curve** centered on
the pole edge; Pfeifle 2017 §5.4 computes it from a magnetic-charge line
integral (Eq. 6–8).

### Consequences (all measured)
- **Voicing / asymmetric placement**: tine rest position relative to the
  bell curve sets the odd/even balance. Perfectly centered → symmetric
  Φ(x) → output at **2·f0** (fundamental and odd harmonics cancel; the
  strong second harmonic is the classic Rhodes "bell"); shifted off-center
  → asymmetric transfer → fundamental returns and a full harmonic series
  appears [DAGA 2017; Shear & Wright 2011 Fig. 2 (196 Hz tine, on-axis vs
  5 mm above); patent: pickup edge deliberately "somewhat off-center …
  permits accurate adjustment of the fundamental-overtone relationships"].
  Factory voicing ≈ slightly off-center: strong 1st + prominent 2nd
  ("bell") + decreasing tail.
- **Amplitude-dependent spectrum**: for x(t) = x_rest + a·sin(2πf0t), a
  Taylor expansion of Φ gives harmonic n scaling ≈ aⁿ (small a): softer
  strike → almost pure fundamental+bell; harder strike → harmonics rise
  much faster than the fundamental. Measured: >20 harmonics from a 2 mm
  sinusoid at 3 mm gap on a guitar pickup [Novak et al. 2018 Fig. 5].
- **Bark / growl**: at high velocity in the low register the swing becomes
  comparable to the gap (Falaize sim: displacement ≈ 6 % of gap → linear;
  ≈ 70 % of gap → heavily distorted waveform). This is overdrive of the
  position-to-flux curve — spectrally rich, buzzy, still *harmonic* (all
  partials at n·f0). No new mechanism needed beyond the static Φ(x).
- **Static (memoryless) nonlinearity is experimentally verified**:
  ∫u dt vs x(t) collapses onto a single frequency-independent,
  gap-independent curve (offset only) [Novak et al. 2018 §3]. Their
  3-parameter empirical fit for the whole curve:
  Φ(x) = A·[ (x+L_eq)/∛(r_eq²+(x+L_eq)²) − x/∛(r_eq²+x²) ].
  Paiva/Pakarinen/Välimäki (JAES 2012) established the block structure
  used everywhere since: **static NL → d/dt → linear filter**.
- **Electrical filter**: the coil (Rhodes pickups ≈ 170 Ω DC [Shear 2011],
  ~thousands of turns, split into two opposite-phase hum-cancelling
  sections) + cable + input impedance form a resonant lowpass (Falaize use
  an RLC with fc = 500 Hz as an idealization; the real harp of paralleled
  pickups + passive tone circuit is gentler). For our purposes this is a
  fixed linear EQ absorbed into calibration — the jRhodes reference
  already includes the sampler's preferred EQ (see SOURCES.md).

---

## 5. Hammer, damper, mechanical noises

- **Hammer**: simplified single action (key drives hammer directly, no
  escapement-repetition assembly like a grand); **neoprene tip** on Mark
  I/II (originals: felt, size/felting graded by register — "large, thickly
  felted" in the bass, "sharp, thinly felted" in the treble [US 2,972,922]).
- Standard piano-hammer contact model applies (Hunt & Crossley / Stulov):
  F = k_h·c^β + λ_h·c^β·ċ (c = tip compression). Falaize & Hélie simulate
  with m_h = 5 g, β = 2, k_h = 1e6 N/m, strike point 2.35 cm from the clamp
  on a 7.83 cm A4-tine (≈ 30 % of length) — illustrative, not measured.
- Measured average **hammer–tine contact time 6.42 ms** (high-speed camera,
  7532 fps) [Münster & Pfeifle 2014 §3.1.1]. Long contact relative to
  high-note periods → strong lowpass on the excitation of higher tine
  modes in the treble (another reason attack inharmonicity matters most in
  the low/mid range).
- Harder strike ⇒ (a) larger a ⇒ pickup harmonics bloom (dominant effect),
  (b) slightly shorter/stiffer contact ⇒ more energy into the brief
  inharmonic attack modes. Velocity affects timbre far more than loudness
  [Münster & Pfeifle 2014 §1.0.2].
- **Damper**: individual felt damper pressing the tine *from below*;
  key release brings felt against a possibly large-amplitude tine →
  key-off thump/buzz: a short noise burst + fast forced decay. Not treated
  quantitatively anywhere in the literature — measure from the reference
  samples' release tails (same approach as the piano damper cliff).
- Other noises in real recordings: key/keybed thump on attack (low-freq
  knock preceding tone), hammer return click, damper felt scrape at very
  low amplitudes. jRhodes3d is direct-from-harp: expect key thump and
  action noise to be present but no room.

---

## 6. Known synthesis approaches

| approach | source | notes |
|---|---|---|
| FDTD shear-beam tine (2 polarizations, large-deflection coupling) + precomputed magnetic-field map, real-time on FPGA | Pfeifle DAFx-17 (downloaded) | most complete physical model; validates the "field-map waveshaper" view |
| Port-Hamiltonian: modal Euler–Bernoulli beam + Hunt-Crossley hammer + Φ(q)=(a+k/(q+l)²)Φ0 pickup + RLC, passivity-preserving integration | Falaize & Hélie DAFx-15 (downloaded) + JSV 2017 (paywalled; HAL manuscript exists) | equations directly reusable; demonstrates linear→bark transition (6 %→70 % of gap) |
| Hammer-driven simple harmonic oscillator + static field transfer function (MATLAB) | Münster & Pfeifle ISMA 2014 (downloaded) | "astonishingly very good" with *one mode* + waveshaper — strongest support for our modal architecture |
| Measured attack-mode map + pickup intermodulation, psychoacoustically pruned; synthesis matched to recordings | Gabrielli, Cantarini, Castellini, Squartini, JASA 148(5):3052–3064, 2020, doi:10.1121/10.0002002 (paywalled; companion audio: github.com/LOGUNIVPM/rhodes-companion-files) | keyboard-wide mode distribution; treat attack partials as note-dependent extras |
| Static-NL → d/dt → filter pickup block model (guitar; direct prior art) | Paiva, Pakarinen & Välimäki, JAES 60(10):768–782, 2012 (paywalled); Novak et al. DAFx-18 (downloaded); Horton & Moore, Am. J. Phys. 77(2):144–150, 2009 (paywalled); Remaggi et al. DAFx-12 clavinet pickup | memoryless waveshaper validated experimentally; 3-param empirical Φ(x) available |
| Commercial modal (Pianoteq family) | Modartt patent US 7,915,515 B2 covers velocity-dependent modal synthesis generally; no EP-specific patent found — their electric pianos ship as products, methods unpublished | our engine is the same family; no additional patent surface identified for tine EPs beyond expired Rhodes patents (US 2,972,922 expired 1978) |

---

## 7. Implications for OUR modal engine (sum of decaying sinusoids)

The Rhodes is close to a *best case* for the existing engine:

1. **Steady-state partials are exact harmonics of f0** (n·f0), because they
   are generated by a time-invariant memoryless nonlinearity acting on a
   single decaying sinusoid — not by beam modes. Mode-ratio config (`fr`)
   should be harmonic for the sustain partials; the beam inharmonicity
   (6.27·f0 etc.) belongs only to a few fast-decaying *attack* partials.
2. **Per-partial exponential decay is structurally correct, not just a
   fit.** If harmonic n's amplitude ∝ a(t)ⁿ (leading Taylor order) and the
   tine decays as a(t) = a0·e^(−σt), then harmonic n decays exponentially
   at rate ≈ **n·σ** — still a single exponential. A static modal fit per
   note *per velocity layer* therefore captures both the velocity-dependent
   spectrum and the "harmonics die faster" decay *exactly* in the
   small-signal regime. Expect fitted decay rates ≈ proportional to
   harmonic index; use that as a sanity check on calibration output.
3. **Where the static fit is only approximate**: at high velocity / low
   notes (bark), higher Taylor orders contribute (harmonic n also gets
   a^(n+2), …), so the *early* decay of high harmonics is faster than one
   exponential and the first few hundred ms are the error hotspot. If eval
   flags this: options are (a) two-stage decay (fast+slow) per partial —
   already supported by the engine's click/attack machinery, (b) a true
   waveshaper stage Φ(x) driven by one internal sinusoid, calibrated from
   Novak's 3-param form — a bigger engine change; try (a) first.
4. **Velocity layers**: jRhodes3d has up to 5 layers — enough to sample the
   aⁿ blooming. Interpolation between layers in level space should follow
   ~n·(dB change of fundamental) per harmonic; validate against layers.
5. **Attack extras per note**: 1–3 inharmonic fast partials (tine mode 2
   near ~6–7·f0 shifted by the tuning spring; tonebar ring at unrelated
   frequency, most audible mid/low register) + key thump noise band.
   Gone within tens of ms; fit like the piano's click bands.
6. **Beating**: some notes show early beating where an attack partial lies
   near a pickup harmonic; static per-note fit picks this up automatically
   if partial frequencies are fitted freely in the attack window.
7. **Release**: felt damper from below → short key-off thump + forced fast
   decay; keys in the top octave(s) — check whether the Stage 73 damper
   reach matters like piano's undamped top (it has dampers throughout,
   but high tines decay fast anyway). Measure release tails per register.
8. **Recording chain**: reference includes sampler's EQ ("treble boost,
   low-mid scoop … emphasize bell tones and upper-velocity bark") —
   absorbed into per-note level tables exactly like the piano's chain
   (known trap, see memory: recording-chain benchmark).

### Expected difficulties (ranked)
1. **Bark at high-velocity low notes** — non-exponential early decay +
   dense harmonics; may need two-stage decays or a waveshaper stage.
2. **Attack transient identity** — the 10 ms glockenspiel ring + thump is
   most of the "Rhodes-ness" at note onset; too clean = electric organ.
3. **Bell (2nd-harmonic) level vs register/velocity** — voicing-dependent;
   the reference instrument's per-note voicing is irregular (real
   instrument, hand-adjusted); expect noisy per-note tables, resist
   smoothing across notes too aggressively.
4. **Key-off thump** modeling from only 5-layer samples (release recorded?
   check sfz for release samples — if absent, synthesize plausibly).
5. **Tremolo/vibrato**: none — mono set is raw harp (post-effect excluded).

---

## 8. Quantitative cheat sheet

| quantity | value | source |
|---|---|---|
| tine diameter | 1.5 mm (patent: 1.9 mm) | Shear 2011; US2972922 |
| tine lengths | 18–157 mm | Shear 2011 |
| f0 range (73-key) | 41 Hz–2.6 kHz | Shear & Wright 2011 |
| tip swing, longest tine | up to 50 mm | Shear & Wright 2011 |
| pickup gap scale | ~1 mm (sim), few mm real | Falaize 2015 |
| linear regime | swing ≲ ~6 % of gap | Falaize 2015 §7.2 |
| bark regime | swing ≳ ~70 % of gap | Falaize 2015 §7.2 |
| cantilever ratios (uniform) | 1 : 6.267 : 17.55 : 34.39 | k_nL = 1.8751, 4.6941, 7.8548, 10.9955 |
| transient → pure sine | 10–14 ms | Münster & Pfeifle 2014 |
| hammer contact time | 6.42 ms avg | Münster & Pfeifle 2014 |
| midrange Q (B3–E♭4) | 1040–1520 → τ ≈ 1.3–1.6 s, T60 ≈ 9–11 s | Shear 2011 Table 5.1 |
| tonebar vs note freq | −hundreds to −1400+ cents, unrelated | Münster & Pfeifle 2014 Table 1 |
| tonebar/tine mass ratio | 10–25× | US2972922 |
| pickup DC resistance | ≈ 170 Ω | Shear & Wright 2011 |
| centered voicing | output = 2·f0 (bell) | DAGA 2017; Shear & Wright 2011 |
| harmonic scaling (small a) | harmonic n ∝ aⁿ ⇒ decay rate ≈ n·σ | Taylor of Φ(x); Novak 2018 |
| harmonics at large swing | >20 measurable | Novak 2018 Fig. 5 |

---

## 9. Sources

### Downloaded (this directory)
| file | citation | URL |
|---|---|---|
| `Pfeifle_2017_DAFx17_realtime_Wurlitzer_Rhodes_model.pdf` | F. Pfeifle, "Real-Time Physical Model of a Wurlitzer and Rhodes Electric Piano," Proc. DAFx-17, Edinburgh, 2017 | http://www.dafx17.eca.ed.ac.uk/papers/DAFx17_paper_79.pdf |
| `Muenster_Bader_2014_ISMA_nonlinear_Rhodes_sound_production.pdf` | M. Münster, F. Pfeifle, "Non-Linear Behaviour in Sound Production of the Rhodes Piano," Proc. ISMA 2014, Le Mans, pp. 247–252 (note: authors are Münster & Pfeifle, filename kept from initial lead) | http://www.conforg.fr/isma2014/cdrom/data/articles/000062.pdf |
| `Muenster_Pfeifle_2017_DAGA_tone_production_Wurlitzer_Rhodes.pdf` | F. Pfeifle, M. Münster, "Tone Production of the Wurlitzer and Rhodes E-Pianos," DAGA 2017, Kiel, pp. 556–559 (4-page version of the Springer chapter) | https://pub.dega-akustik.de/DAGA_2017/data/articles/000210.pdf |
| `Falaize_Helie_2015_DAFx_electromechanical_piano_portHamiltonian.pdf` | A. Falaize, T. Hélie, "Guaranteed-Passive Simulation of an Electro-Mechanical Piano: A Port-Hamiltonian Approach," Proc. DAFx-15, Trondheim, 2015 | https://www.dafx.de/paper-archive/2015/DAFx-15_submission_33.pdf |
| `Novak_2018_DAFx_guitar_pickup_nonlinearity.pdf` | A. Novak, B. Lihoreau, P. Lotton, E. Brasseur, L. Simon, "Experimental Study of Guitar Pickup Nonlinearity," Proc. DAFx-18, Aveiro, 2018 | https://www.dafx.de/paper-archive/2018/papers/DAFx2018_paper_39.pdf |
| `Shear_Wright_2011_NIME_electromagnetically_sustained_Rhodes.pdf` | G. Shear, M. Wright, "The Electromagnetically Sustained Rhodes Piano," Proc. NIME 2011, Oslo | https://mat.ucsb.edu/Publications/Shear_Wright_NIME_2011.pdf |
| `Shear_2011_MSthesis_electromagnetically_sustained_Rhodes.pdf` | G. Shear, "The Electromagnetically Sustained Rhodes Piano," M.S. thesis, MAT, UC Santa Barbara, Dec 2011 (Q measurements Table 5.1) | https://www.mat.ucsb.edu/Masters/GregShearMasters2011_12_5.pdf |
| `Rhodes_patent_US2972922_1961_asymmetric_tuning_fork.pdf` | H. B. Rhodes, "Electrical musical instrument in the nature of a piano," US Patent 2,972,922, filed 1959-03-09, granted 1961-02-28 (expired) | https://patentimages.storage.googleapis.com/63/b1/6e/d6dc6724464a17/US2972922.pdf |

### Paywalled / not downloaded (citation + where)
- **Falaize & Hélie**, "Passive simulation of the nonlinear port-Hamiltonian
  modeling of a Rhodes Piano," *J. Sound Vib.* 390:289–309, 2017,
  doi:10.1016/j.jsv.2016.11.008. Journal version of the DAFx-15 paper with
  the refined Rhodes pickup axis geometry. Open manuscript exists on HAL
  (hal-01390534, `JSV_Rhodes_manuscript_round_2.pdf`) but HAL's
  bot-challenge blocked scripted download — grab manually via browser if
  needed; the DAFx-15 paper covers the same model.
- **Gabrielli, Cantarini, Castellini, Squartini**, "The Rhodes electric
  piano: Analysis and simulation of the inharmonic overtones," *JASA*
  148(5):3052–3064, 2020, doi:10.1121/10.0002002. Abstract: spectral
  analysis at pickup output + psychoacoustic pruning; SLDV on the
  asymmetric tuning fork comparing assembly modes vs component modes;
  numerical model of pickup intermodulation; synthesized-vs-recorded match;
  map of significant resonant modes across the keyboard. Companion audio:
  https://github.com/LOGUNIVPM/rhodes-companion-files
- **Pfeifle & Münster**, "Tone Production of the Wurlitzer and Rhodes
  E-Pianos," in A. Schneider (ed.), *Studies in Musical Acoustics and
  Psychoacoustics*, Current Research in Systematic Musicology vol. 4,
  Springer, 2017, pp. 75–107, doi:10.1007/978-3-319-47292-8_3. Full
  high-speed-camera + FEM study; the DAGA 2017 PDF above is the open
  4-page summary.
- **Paiva, Pakarinen, Välimäki**, "Acoustics and Modeling of Pickups,"
  *J. Audio Eng. Soc.* 60(10):768–782, 2012. The pickup block-model
  (static NL → derivative → filter) + impedance measurements.
- **Horton & Moore**, "Modeling the magnetic pickup of an electric guitar,"
  *Am. J. Phys.* 77(2):144–150, 2009, doi:10.1119/1.2990663.
  Magnetic-charge surface model; used by Pfeifle for the Rhodes field map.
- **Münster, Pfeifle, Weinrich, Keil**, "Nonlinearities and
  self-organization in the sound production of the Rhodes piano," *JASA*
  136(4):2164, 2014 (ASA meeting abstract of the ISMA work).
- **T. Wendland**, "Klang und Akustik des Fender Rhodes E-Pianos,"
  Magisterarbeit, TU Berlin, 2009 (German; advisor S. Weinzierl). Referenced
  by Pfeifle as the earliest focused tine-vibration study; no public PDF
  found.
- **Remaggi, Gabrielli, de Paiva, Välimäki, Squartini**, "A pickup model
  for the clavinet," Proc. DAFx-12, 2012 — related NL-pickup prior art.
- Related Rhodes patents (Google Patents, all expired): US 4,338,848 "Piano
  Action" (1982); US 4,342,246 "Multiple Voice Electric Piano" (1982);
  US 4,373,418 "Tuning Fork Mounting Assembly" (1983); US 3,644,656 "Tone
  generator with vibratory bars"; US 3,418,417 "Electric piano
  incorporating multicomponent tuning forks" (non-Rhodes).
