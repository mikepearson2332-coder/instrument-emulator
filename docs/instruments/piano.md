# Piano — sound model and calibration

Grand piano, benchmarked against the Salamander Grand Piano V3 recordings
(Yamaha C5, CC-BY 3.0 — provenance in `instruments/piano/SOURCES.md`).
Architecture: calibrated modal synthesis, the family described by
Pianoteq's patent US7915515B2. Iteration history and failed approaches:
`instruments/piano/DEVLOG.md`. Physics and literature:
`instruments/piano/research/research-brief.md`.

## Sound model (per note)

Rendered by `core/engine` from `params/grand.json` (~520 KiB, 30 keys × 4
velocity layers), interpolated to arbitrary key/velocity:

- **Inharmonic partials** `f_n = n·f0·√(1+B·n²)`; B measured per key
  (2.2e-4 at A0 → 1.4e-2 at C8). The instrument's Railsback stretch
  (−16 c at A0 … +99 c at C8 vs equal temperament) lives in the measured
  per-key `f0`, interpolated in cents-deviation space between keys.
- **Two-stage decay** per partial: `a₁e^{-t/τ₁} + a₂e^{-t/τ₂}` (prompt
  sound + aftersound), fitted with noise-floor-validated envelopes.
- **Unison behavior**, two regimes: below MIDI 76, the measured envelope
  already contains string decoherence, so detune is rendered as
  level-preserving multiplicative *beating* (mean gain 1) — splitting the
  envelope across detuned copies would double-count the level drop. From
  MIDI 76 up, unison splits are tens of cents (resolved spectral lines):
  2–3 detuned string copies with random unequal weights are rendered
  explicitly.
- **Attack thump**: per-band filtered-noise burst (τ = 20 ms), calibrated
  so the synth's own STFT band metric reproduces the measured attack dB.
- **Resonance bed**: broadband sustained noise floor per band with
  measured T60s, same self-consistent calibration.
- **Sympathetic / body lines**: 53 fixed resonators (81 Hz – 2.5 kHz)
  shared by all keys, each with measured frequency, T60, and per-key
  excitation dB (some are 50 Hz-hum harmonics of the recording — they are
  part of matching the reference).
- **Velocity** interpolates per-partial amplitudes in log domain between
  calibrated layers (vel 8/48/88/127), reproducing measured brightness
  growth.
- **Release**: exponential damper fade (120 ms below C4, 60 ms above) with
  a soft body remnant (max of fade and 0.02·e^{-t}); keys above MIDI 88
  have no dampers. Sympathetic lines are not damped by key release.

## Calibration pipeline

```
scripts/analyze_reference.py   FLAC → per-note JSON: f0, B, per-partial
                               (freq, amp, two-stage decay fit), bed/thump
                               band profiles, release-cliff position
scripts/measure_symp.py        global sympathetic lines (excludes note
                               partials using the analysis JSONs)
python -m instruments.piano.calibrate   JSONs + symp → params/grand.json
```

Measurement notes that took iteration to get right (details in DEVLOG):
decay fits truncate before the key-release damper cliff; per-partial
envelopes use moving-average windows whose spectral nulls land exactly on
neighboring partials (and on the mid-way noise probes used for validity
masking); above ~1.2 kHz f0 is pinned to a spectral probe because unison
detuning makes the free (f0, B) fit mislock; the robust piecewise-dB decay
fit beat nonlinear least-squares (which chases attack noise).

## Benchmark

`instruments/piano/benchmark.py`: partial tuning (cents), per-partial slow
decay log-error, log-spectral distance early (0–0.5 s) / mid (0.5–2.5 s),
RMS-envelope error (dB), spectral-centroid ratio; composite weights are
piano-specific. Grid: 30 pitches × 4 velocities = 120 notes.

**Composite mean 1.192** (Python reference, 2026-07-11; from a 1.475 first
baseline). Rust engine: 1.189–1.195 across runs — statistically
indistinguishable from a seed change (null: mean ±0.009, per-note std
0.143). Register means: bass 0.92 · low 1.11 · mid 1.05/1.06 · high
1.12/1.36 · top 1.68.

## Known limitations

- Top two octaves score worst (1.36/1.68): real unison splits of 10–30
  cents make partial frequency genuinely ambiguous, and sparse partials
  limit both measurement and the benchmark's meaning there.
- Single fixed microphone perspective (the reference's); no soundboard IR
  or stereo image — the resonance bed and symp lines stand in for body
  response.
- No una corda / sostenuto; sustain pedal is binary (no half-pedaling).
- Longitudinal string modes and phantom partials are not modeled
  (candidate future work; see DEVLOG ranked next steps).
