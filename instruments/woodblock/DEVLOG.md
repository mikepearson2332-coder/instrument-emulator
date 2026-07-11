# Development log — woodblock model

Run in `--auto` mode (2026-07-11): checkpoint gates are logged decisions,
not pauses.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**Source chosen: VCSL woodblock (CC0 1.0).** See SOURCES.md.

- Coverage: one woodblock ("wood_click") × 4 dynamics (pp/mp/f/ff) with
  round robins at pp (3) and f (2). Woodblock is unpitched, so a single
  block is the full "pitch range"; the model transposes the fitted modes
  across the keyboard from a nominal anchor key.
- Measured (probe over the raw files): dominant mode cluster
  1.27–1.44 kHz, secondary content ~3.1 kHz; ring to −60 dB 290–470 ms
  (mostly room tail; the mode itself decays much faster). 44.1 kHz stereo.
- Anchor: dominant peak ≈ 1370 Hz ≈ F6 → the block is mapped at MIDI 89,
  files named `F6v{1..4}.flac`, extra round robins kept as `_alt` files
  for measurement-noise/null estimation only.
- **Excluded**: `wood_click2_mp` (spectrum dominated by 2.85 kHz — a
  different block or rim strike; only one dynamic, can't calibrate a
  layer stack from it) and `wood_click3_vl1/2` (same pitch region but
  visibly different spectral shape/decay — likely another block). Mixing
  blocks would smear the mode fits. Logged here per the license-gate
  protocol; both remain in `reference/woodblock/raw/` (gitignored).
- Alternatives considered: Philharmonia percussion (license less
  permissive, similar coverage), Freesound packs (per-file license audit
  needed). VCSL wins on license + recording consistency.

## Gate 2 — benchmark design (auto-decision 2026-07-11)

Metrics (`benchmark.py`): attack_db (1 ms-hop RMS env, first 50 ms),
env_db (2 ms hop, 350 ms), mode_cents (top-4 ref modes, nearest match),
decay_logerr (fast tau of top-2 modes), lsd_early 0–0.15 s / lsd_mid
0.15–0.4 s at **floor −35 dB** (pp takes bottom out at the recording noise
floor ~30 dB under the peak band; the piano's −75 dB floor scores tape
hiss), centroid ratio (60 ms). Weights lean on attack + short-time
envelope — the percept is the click.

Noise floor measured, not assumed: **take-vs-take null mean 1.315**
(std 0.65; pp round robins differ hugely — atk up to 26 dB between takes),
seed-to-seed synth null ±0.06 at the mean. Eval grid: 4 dynamic layers of
the single block; extra round robins are the null set.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 2.546 | first full baseline (modes + thump/bed via lab/modal.py) |
| 2 | — | amp caps (t0-extrapolation exploded: synth peak 3.97 vs ref 0.256), 1.5 ms partial onset ramp (instant-on sines splattered −57 dB broadband into every band), ≥2-bin thump bands (40–115 Hz bands have only 2 STFT bins → were dropped) |
| 3 | 1.582 | + mode-cluster merge (min sep 10%: a tau=8 ms mode is ~100 Hz wide; 6% picking split one resonance into 2–3 sines that double-counted, coherent sum 0.62 vs real 0.26), late-slope bed t60 |
| 4 | 1.211 | + per-band click decay `thump_tau_bands` (reference broadband decays 5–10× slower than the fixed 10 ms thump — early room reflections at 60–150 ms were 20 dB undershot) |
| 5 | 1.012 | benchmark floor −35 dB (stop scoring tape hiss). Below the take null (1.315). |
| 6 | **1.362** (rust 1.290) | ✓-by-ear, ✗-by-score: user-ear finding — the model read as a "toy snare". Root cause: the noise model faithfully reproduced the **VCSL room's early reflections** (noise only 3–5 dB under the modes from 20–200 ms, taus 40–100 ms). Fix: per-mode skirt guards in the thump/bed measurement, click taus capped at 20 ms, bed dropped entirely. The score WORSENS because the benchmark compares against the roomy recording — fidelity-to-instrument beat fidelity-to-recording (same call as the piano's hum lines). CURRENT |

Seeds at iter 5: 1234/4321/777 → 1.012 / 1.034 / 1.139. Iter 6 sits at the
take-null (1.32); the residual gap to the reference is the room itself.

## What failed / lessons

- **t=0 amplitude extrapolation is explosive for percussion**: tau_fast
  (7–10 ms) ≈ demod anchor time, so the piano's 3-e-folding cap allows 20×
  inflation. Fixed by capping a_fast ≤ 2.2 × measured envelope peak
  (a_slow ≤ 1.1×).
- **Peak-picking slices wide resonances**: everything within 10% at these
  taus is one mode group; the 60-band spectrogram can't resolve sub-band
  structure anyway. One sine per group, energy read once by a
  wide-passband (~6 ms) demod window.
- **Fixed thump tau can't cover 60–150 ms**: the click's broadband tail is
  early room response with tau ≈ 40–60 ms, band-dependent. Now measured
  per band and stored in `config.thump_tau_bands`.
- pp reference takes have ~30 dB SNR — any metric with a deep floor
  scores the recording chain, not the model.

## Gate 3 — ship (auto-decision 2026-07-11)

Engine generalization (`core/engine`): `Table.config` block switches the
modal family from piano semantics to generic behavior — per-partial `fr`
frequency ratios (non-string mode series), `PartialKind::Plain` (no unison
beating), shared partial onset ramp, per-band `thump_tau_bands`,
`ReleaseStyle::{Piano, Fade, NoDampers}`. Absent config = byte-identical
piano behavior.

Verification:
- Piano gate: full 120-note Rust eval after the changes = **1.195**, equal
  to the phase-3 gate value; `compare_engines.py` note_params ≤ 3.6e-15.
- Woodblock note_params Python↔Rust ≤ 1.9e-16 rel (incl. `fr`).
- Woodblock Rust eval **1.022** vs Python seeds 1.012/1.034/1.139 —
  inside the seed null.
- Quality sweep: full 1.028 = p2, p1 1.073, no-noise 1.89 (the click is
  the instrument — noise must never be pruned for percussion).
- Testbed: `woodblock / block` appears via params discovery; StreamSynth
  renders, note-off is a no-op (no dampers), voices cull after decay.

## Data flow

```
reference/woodblock/samples/F6v{1..4}[.alt*].flac   (VCSL CC0, gitignored)
  └─ python -m instruments.woodblock.analyze  → reference/woodblock/analysis/*.json
       └─ python -m instruments.woodblock.calibrate → instruments/woodblock/params/block.json
            └─ lab/modal.py (ModalSynth) ← instruments/woodblock/synth.py
                 └─ python -m instruments.woodblock.evaluate [--null|--engine=rust]
```

