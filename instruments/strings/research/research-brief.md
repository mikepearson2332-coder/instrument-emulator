# Research brief — bowed string ensemble (section sustains)

Status 2026-07-11: written inline from standard literature (the PDF-
gathering research agent was cut short by session limits; citations
below are to well-known published work, verify page-level details
before leaning on exact numbers). Purpose: feed the **engine-family
decision** — the modal engine cannot sustain, so this instrument needs
engine family 2 (continuous excitation), and the cheapest family that
sounds like a section should win.

## Physics — single bowed string

- Steady bowing produces **Helmholtz motion**: a single corner
  circulating the string; string-velocity at the bow is a stick-slip
  square-ish wave, bridge force a **sawtooth** → harmonic amplitudes
  ≈ 1/n with no cutoff up to the "Helmholtz corner" rounding
  (Cremer, *The Physics of the Violin*; Woodhouse 2014 review "The
  acoustics of the violin", open access, Acta Acustica). Partials are
  EXACTLY harmonic (stiffness inharmonicity is enslaved by the
  periodic stick-slip, unlike plucked/struck strings).
- The **body filter** shapes 1/n into the violin sound: main air
  resonance ~275 Hz (A0), main wood/corpus ~450–550 Hz, "bridge hill"
  ~2–3 kHz, then rolloff. Per-instrument formants are fixed linear
  filters → in a calibrated table they are absorbed into measured
  per-note harmonic amplitudes exactly like the piano's soundboard.
- **Bow noise**: the stick-slip is jittery; ~pitch-synchronous noise
  concentrated around the harmonics (heard as "breathy scratch",
  −25…−40 dB under the harmonic at mf) plus broadband attack scratch
  before Helmholtz motion locks in (~50–300 ms transients; sections
  smear this).
- **Vibrato**: 5–7 Hz, ±10–25 cents, with correlated amplitude
  modulation via the body-resonance slopes (McIntyre & Woodhouse;
  Meyer, *Acoustics and the Performance of Music*).
- MSW/waveguide simulation (McIntyre-Schumacher-Woodhouse 1983; Smith,
  *Physical Audio Signal Processing*, bowed-string chapter; Serafin
  PhD 2004) gives playable solo strings, but per-player-per-voice cost
  and control complexity are high, and solo realism is NOT the target.

## What makes it an ENSEMBLE

(Chorus-effect literature; Meyer on orchestral sections; sampling
practice.) A section differs from a solo player by:

1. **Pitch spread**: players sit within ±5–15 cents of each other,
   slowly wandering (random-walk, sub-Hz).
2. **Vibrato decorrelation**: same nominal rate, independent phases &
   slightly different rates → per-harmonic amplitude/frequency
   micro-modulation that never repeats; deep solo vibrato averages
   into a gentle shimmer.
3. **Onset asynchrony**: bow starts spread over ~30–100 ms; attack
   scratch averages into a soft swell (section sustains have 100–300 ms
   rise, no individual scratch).
4. **Incoherent summation**: N players add power-wise; the comb/beat
   structure of any pair is masked; residual slow (~0.1–2 Hz) level
   undulation is characteristic.
5. Room: sections are recorded/heard with ambience; the VSCO2-CE
   reference has real room decay on release (recording-chain-in-
   benchmark, as with the đàn tranh).

The percept "string section" is dominated by (1)+(2)+(4): a fused,
shimmering, non-periodic-modulated harmonic spectrum with slow
envelope undulation, soft onsets, and long releases into room tail.

## Candidate engine families

### A. Waveguide per player (MSW × N)
N delay-line + friction-curve voices per section note (N≈4–12), plus
body filter. Cost: high (per player per voice); control (bow
force/speed schedules) is an unsolved calibration problem from
section recordings. Realism ceiling high for SOLO; overkill and
under-calibratable for sections. REJECT for this target.

### B. Source-filter / additive "stochastic harmonic bank" (RECOMMEND)
Per note: H harmonic oscillators (H ≈ 30–50) with
- amplitudes from the measured section spectrum (table, per note ×
  dynamic — body formants baked in),
- per-harmonic slow **stochastic AM/FM**: each harmonic's frequency =
  n·f0·(1 + ensemble drift_n(t)) where drift_n is a low-rate (0.1–3 Hz
  bandlimited) random process ~±5–10 cents, plus a shared vibrato LFO
  (5–6 Hz, depth per dynamic) with per-harmonic AM coupling;
  amplitude = table envelope × (1 + slow noise ~1–3 dB rms),
- pitch-locked noise band around each harmonic (or 2–3 broad noise
  bands shaped by the harmonic comb) for bow breath,
- global ADSR-ish sustain envelope measured from reference (rise
  100–300 ms, sustain undulation, release ~0.3–1 s + room tail as a
  second slower stage).
This is *the modal voice with three additions*: (i) sustain (envelope
does not decay while note held), (ii) per-partial slow random FM/AM
generators, (iii) a vibrato LFO. The engine's existing complex-rotator
per partial + per-buffer parameter update (rotator angle nudged by
drift) covers it; noise bands already exist. Cost ≈ same order as a
piano voice (40 rotators + bands) + per-buffer PRNG smoothing. This is
the classic SMS sinusoids+noise decomposition (Serra & Smith 1990)
specialized to ensemble sustains.

### C. Sample-morph / wavetable of measured frames
Cheapest CPU but it IS a disguised sample player (stores spectral
frames) — against the project's no-samples-at-runtime spirit; poor
note-length flexibility without the stochastic layer anyway. REJECT.

## Calibration plan (for family B)

From each VSCO2-CE section sustain: harmonic amplitude table (median
steady-state spectrum), sustain envelope shape (rise time, undulation
depth/rate via envelope spectrum <5 Hz), vibrato rate/depth (demod FM
of harmonics 3–6), ensemble spread (linewidth of harmonics in a long
FFT: the n-th harmonic's width grows ∝ n·detune-spread — fit cents
spread from linewidth vs n), bow-noise level (inter-harmonic floor),
release two-stage fade (damped string + room tail). All fit existing
lab machinery (partial_envelope, band metrics) plus a new linewidth
measurement.

## Expected difficulties

- Perceptual metric: LSD/envelope metrics won't capture "shimmer
  realism"; need a modulation-spectrum metric (envelope-modulation
  energy 0.1–5 Hz per band) in the benchmark.
- Random FM realization ≠ reference realization: all comparisons
  statistical (seed nulls), like noise.
- Solo contrabass reference is not a section; either accept solo-bass
  timbre or synthesize a pseudo-section (stack detuned renders) and
  say so.
- Release into room tail: config release machinery may need a second
  stage (fade + longer low-level tail).

## Engine-family decision (input to gate)

Family B ("sustained stochastic harmonic bank") is the recommendation:
it reuses ~80% of the modal voice, adds sustained envelopes + slow
random modulators + vibrato LFO, calibrates directly from section
recordings, and its CPU cost fits the existing budget. Family A
(waveguide) should wait for a SOLO bowed-string instrument where its
strengths matter.
