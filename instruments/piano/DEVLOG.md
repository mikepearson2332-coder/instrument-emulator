# Development log — piano model iterations

All scores are the composite benchmark (lower = closer to reference), mean
over 120 notes (30 pitches × velocity layers 1/6/11/16). Metrics per note:
partial-tuning cents, decay log-error, log-spectral distance early (0–0.5 s)
and mid (0.5–2.5 s), RMS-envelope dB error, spectral-centroid ratio.
Composite weighting in `pianomodel/benchmark.py::composite_score`.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 1.475 | first full baseline (modal synth + thump + bed) |
| 2–3 | — | analysis fixes (see below), partial runs |
| 4 | 1.224 | + t0-extrapolated fits, nearest-freq pc metric, n≤3 unmasked |
| 5 | 1.206 | + treble demod window fix, 53-line symp forest, detune ramp |
| 6 | 1.466 | ✗ REGRESSION: nonlinear curve_fit decay refinement |
| 7 | 1.449 | ✗ still bad with refinement restricted to n≤3 |
| 8 | 1.206 | reverted refinement — recovered iter-5 state exactly |
| 9 | 1.215 | multiplicative beating (mid up, top down — mixed) |
| 10 | **1.192** | kept multiplicative beating, reverted weight norm. CURRENT |
| 11 | 1.189/1.190 (py/rust) | + 1.5 ms partial onset ramp — user-ear finding from live testbed playing: random start phases (±0.25 rad) sum to a step of 6–14% of peak at t=0, an audible click the benchmark never flagged (the reference has a hammer attack in the same place). Scores unchanged within null. |

Register means at iter 10: bass A0–A1 0.92 · C2–A2 1.11 · C3–A3 1.05 ·
C4–A4 1.06 · C5–A5 1.12 · C6–A6 1.36 · C7–C8 1.68.

## What failed and must not be retried naively

- **Nonlinear sum-of-two-exponentials refinement of decay fits**
  (`_refine_double_decay` in analysis.py, currently dead code behind
  `refine=False`): systematically inflates amplitudes by chasing attack-noise
  bumps and beat dips; brightened treble (centroid ratio 1.03→1.31) and
  darkened mids. The piecewise two-line dB fit with breakpoint search is the
  keeper.
- **Splitting the measured envelope across detuned unison strings** (below
  midi 76): the measured envelope *already contains* the real strings'
  decoherence, so splitting double-counts it (~4.4 dB mid-decay deficit).
  Multiplicative beating `env·(1+m·cos(2πΔf t))` preserves level. Explicit
  detuned splitting is still used for midi ≥ 76 where splits (10–30 c) are
  resolved spectral lines. Normalize split weights by `sum` (amplitude), NOT
  by `sqrt(sum²)` — power norm overshoots the coherent attack and skews the
  benchmark's gain normalization (iter 9→10 lesson).

## Bugs found on the way (all fixed, don't reintroduce)

1. Inharmonicity fit collapse: harmonic-window search biases B low by 10×
   (C4 2.6e-5 vs true 2.9e-4). Fix: progressive partial extension refitting
   (f0, B) as n grows + outlier rejection.
2. Two-line decay fit extrapolating the late segment's intercept to t=0 →
   amplitudes of 1e13+. Fix: accelerating (dB-concave) decay falls back to
   single-line; amplitudes capped.
3. Envelope fits inflating buried partials ~30 dB: the demodulator reads the
   broadband noise floor. Fix: co-located noise probe (demod halfway between
   partials with a window whose spectral nulls land on multiples of
   spacing/2) + pointwise validity mask (n ≥ 4 only — masking n ≤ 3 destroys
   soft-note fundamentals).
4. Treble amplitude collapse (−28 dB at C8): unisons split ±25–35 Hz landed
   exactly on the demod window's first null. Fix: `_envelope_window` uses a
   wide-passband k for f0 > 800 Hz (nulls stay on spacing/2 multiples for any
   integer k).
5. Fits anchored at the masked-envelope peak (t≈0.3 s) treated as t=0
   amplitudes. Fix: extrapolate each stage to t=0 along its own decay,
   max 3 e-foldings.
6. Release cliff (damper) inside the fit region corrupted slow-decay
   estimates. Fix: `find_release` truncation; release time stored in JSON and
   used by evaluate.py so the synth releases at the same moment.
7. Top-octave f0: with ≤4 partials the free (f0,B) fit wanders ±60 c. Fix:
   pin f0 to a ±8% spectral-peak probe (all keys with f0_nominal > 1200 Hz),
   fit B alone; calibrate uses cluster-consensus across layers with the
   keyboard trend only as fallback.
8. `partial_cents` metric mislocking (e.g. flagging the 80.7 Hz sympathetic
   line as D#1's partial 2). Fix: nearest-frequency matching, pairs > 60 c
   discarded.

## Model components (pianomodel/synth.py)

partials (inharmonic, two-stage decay, phase-coherent start) → unison beating
(multiplicative < midi 76, split strings ≥ 76, detune ramps ×(1+0.7·(midi−76)))
→ per-band thump (τ=20 ms) + resonance bed (per-band t60, anchor-compensated)
→ damper release (none above midi 89) → 53 sympathetic lines (global bank in
table, per-note levels, not damped by release). Band-noise levels are
empirically self-calibrated at Piano() init against the same STFT-median
metric the analysis uses — never convert analytically.

## Known weaknesses / next steps (in value order)

1. **Attack transient**: synth attacks are cleaner/softer than the real
   hammer. Next step per literature: Stulov/Hunt-Crossley hammer force pulse
   shaping the partial onset phases+amps, or a measured attack-residual
   band profile at finer time resolution (<10 ms frames).
2. **Top octave (C7–C8, score ~1.7)**: unison splits are 15–30 c and each
   layer's "f0" is ambiguous; could model 2–3 explicit strings per note with
   per-string f0 measured via peak splitting (esprit/music-style) instead of
   a single f0+detune heuristic.
3. **Real-time playback**: modal synth streams naturally (per-partial phasor
   recursion); port synth_note to a block-based generator + sounddevice.
4. **Sustain pedal / chord sympathetic coupling**: route bridge sum into
   other keys' secondary resonators (Bank TASLP 2010 §sympathetic; region
   gain matrix). Currently chords are simple sums.
5. Hum lines (100/300/400/500 Hz) are faithful to the recording but not the
   instrument — consider a `--clean` flag that drops them.

## Data flow

```
reference/piano/samples/*.flac  (120, gitignored-size data, CC-BY Salamander)
  └─ scripts/analyze_reference.py → reference/piano/analysis/*.json  (per-note fits)
       └─ scripts/measure_symp.py → reference/piano/symp.json         (global lines)
            └─ instruments/piano/calibrate.py → instruments/piano/params/grand.json  (ship this)
                 └─ instruments/piano/synth.py (Piano) ← piano.py CLI
                 └─ core/engine (Rust port) ← instruments/piano/synth_rs.py
                      └─ scripts/evaluate.py ↔ instruments/piano/benchmark.py → output/eval.json
```

`reference/analysis/*.json` are derived artifacts — safe to delete, ~1 min/8
notes to rebuild. `grand.json` is the only file the app needs at runtime.

## Phase 2 (2026-07-11): Rust port of the synth (`core/engine`)

The synth was ported 1:1 to Rust (`core/engine/src/synth.rs` + interp.rs /
filters.rs / stft.rs) for the real-time runtime; `instruments/piano/synth_rs.py`
wraps it with the `Piano` interface via PyO3 (`core/python`).

Verification (three levels):
1. **Exact**: `note_params` (all interpolation) matches Python to ≤4e-15 rel
   across 128 on/off-grid key×velocity combos (`compare_engines.py`).
   Butterworth SOS + sosfilt + STFT band metric match scipy reference values
   to <1e-6 rel (unit tests in the crates, constants from
   `scripts/probe_stft_conventions.py`).
2. **Statistical**: renders use a different PRNG (xoshiro256++/Box-Muller vs
   numpy PCG64/ziggurat), so waveforms differ in noise/phase realization.
   Python-vs-Python seed nulls show up to ~5-6 dB per-window envelope
   deviation where unison beat periods exceed the render (the random beat
   phase sets the fundamental's level); the Rust engine sits inside that null.
3. **Benchmark**: full 120-note eval — Rust mean **1.189** vs Python 1.192
   (Δ −0.003), 62/120 notes worse (coin flip), per-note Δ std 0.150.
   Null (Python seed 4321 vs 1234, same engine): Δ +0.0087, std 0.143,
   max mover ±0.41 — the Rust engine is statistically indistinguishable
   from a seed change.

Throughput (ARM64, release+LTO, offline whole-note renders): Rust ≈ numpy at
~12.5x realtime — both are `sin()`-per-sample bound. Real-time polyphony
headroom comes from phase-3 recursive resonators, not from the language swap.
Engine init (band-noise calibration via its own STFT) ~150 ms.

Traps for future porters:
- The band-noise calibration must reproduce *scipy's* STFT conventions
  (periodic hann, /win.sum(), boundary zero-extension, t=0 first frame,
  onesided without doubling) — a constant dB offset does NOT cancel: it biases
  synthesized noise directly (analysis measured the reference with scipy).
- scipy's zpk2sos section grouping differs from the natural per-pole-pair
  grouping; overall transfer function is identical — test impulse responses,
  not coefficients.
- Envelope smoke tests must be judged against a multi-seed Python null, not
  absolute thresholds (slow unison beats make single-window deviations of
  several dB legitimate).

## Phase 3 (2026-07-11): streaming voices, recursive resonators, quality system

`core/engine/src/voice.rs` replaces every per-sample transcendental with a
recurrence (complex rotators for sin/cos, decay-factor states for
exponentials). `synth_note` is now a thin offline wrapper over the streaming
Voice; `StreamSynth` (stream.rs) is the real-time API (note_on/off, pedal,
buffer render, voice culling). Tests: recurrence vs closed form <1e-9;
buffered streaming == one-shot bit-exact (noise off); pedal/release/culling
functional (`probe_stream.py`). Eval gate at full quality: **1.195** vs
Python 1.192 — inside the seed null.

Quality = runtime pruning, table unchanged (calibration never re-runs):
partials sorted by A-weighted energy salience, symp lines by level, then
truncated to `Quality {max_partials, noise, max_symp_lines}`.
Sweep (v11 subset, 30 notes): full 1.219 · p48 1.206 · p32 1.199 (pruning to
32 is FREE) · p24 1.275 · p16 1.341 · p8 1.575 · p24+symp12 1.398 ·
p16+symp8+no-noise 1.883 (4x cheaper).

Performance (one ARM64 core, release+LTO): offline 35x realtime/note (was
12.6x direct-eval). Streaming: 16 full-quality voices 2.3x realtime; 64
voices at p24_s12 1.3x. Host bench (`engine::bench`): 7.4 ns per
partial-sample, 273 ns fixed per voice-sample. **The fixed per-voice cost
(53 symp rotators + 10 noise bands) dominates at high polyphony** —
`pick_max_partials` is honest about this (64 voices @ 50% core -> 0 spare
partials). Next lever: a *shared global sympathetic bank* (physically one
soundboard, not one per voice) + folding noise bands; would cut the fixed
cost by ~10x at large polyphony. Dead components (env < -140 dB) are culled
per buffer, so ringing voices get cheaper as they fade.

Also: normals via Marsaglia polar (no trig); noise realization differs
per draw-order between offline and streaming paths — statistical only.

## Probes

`scripts/probe*.py` are one-off debugging probes kept as worked examples:
probe (synth param dump), probe2 (spectral vs envelope amplitude cross-check),
probe3 (direct FFT f0 peaks), probe4 (analysis JSON dump), probe5 (sustained
line peaks), probe6 (per-component band-level decomposition). probe6's
mute-one-component pattern is the fastest way to attribute a spectral
discrepancy to partials/thump/bed/symp.
