# Development log — vibraphone model

Run in `--auto` mode (2026-07-11): checkpoint gates are logged decisions.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**Source chosen: University of Iowa MIS vibraphone** (see SOURCES.md).
License: "may be downloaded and used for any projects, without
restrictions" (site-wide MIS statement).

- Coverage: chromatic **C3–F6 (42 keys, 4-octave instrument) × 3
  dynamics** (sustain pp/mf/ff), anechoic chamber, 24-bit/44.1 kHz
  stereo. Plus `dampen.mf` takes for damper-fade measurement.
- The instrument is tuned ≈ **A442** (+10 c systematic) — kept, like the
  piano's stretch tuning.
- Multi-note range files split by HF-flux onset detection
  (`split_raw.py`): mallet attacks carry broadband HF that the ring
  lacks; full-band level gating cannot separate notes that ring into the
  next strike, and pp attacks needed adaptive threshold loosening with a
  2.5 s minimum-ring guard against mid-ring false onsets.
- Result: v2 (mf) 42/42, v3 (ff) 42/42, v1 (pp) 39/42 — **pp missing for
  E4, G#4, C#6** (imputed at calibration from mf scaled by the global
  pp/mf ratio; logged in gate 2).
- Alternative considered: VCSL vibraphone (CC0) — per-note files but
  2 velocities per mallet type with mixed hard/soft mallets and a
  minor-third grid; Iowa wins on chromatic × 3 consistent dynamics and
  the anechoic room.

## Gate 2 — benchmark design (auto-decision 2026-07-11)

Metrics (`benchmark.py`): f0_cents + mode_cents (tuned instrument — the
1:4:10 bar tuning is the identity), decay_logerr (time-to-−40 dB of the
demodulated fundamental — robust to fast/slow stage splits), env_db
(10 ms RMS over 6 s, ref-masked at −45 dB), band-LSD 0–0.5 / 0.5–4 s at
floor −35 dB and fmin 90 Hz, level-gated centroid ratio. No round robins
exist → the noise floor is the seed-to-seed synth null
(mean Δ 0.004, per-note std 0.048). Eval grid: 42 keys × 3 dynamics,
renders capped at 8 s.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 0.863 | baseline (per-layer mode detection, lab/modal.py renderer) |
| 2 | 0.923 | ✗ ff-anchored mode measurement alone made pp WORSE (junk fits at fixed freqs: tau=60 s noise "decays") |
| 3 | 0.905 | + junk-fit filters (snr≥5, tau sanity), per-key pp mode inheritance scaled by the fundamental pp/mf ratio, reject fits whose envelope peaks in the back half (D5/B5 pp segments carry trailing handling noise) |
| 4 | 0.866 | + 60 Hz order-4 high-pass: anechoic chamber recordings carry infrasound rumble up to **26 dB above the note** on pp takes — corrupted peak/RMS calibration and flooded the low LSD bands. v2 0.58, v3 0.49, but pp exposed the next layer of the recording chain |
| 5 | 0.536 | benchmark hardening: LSD floor −35 dB, env mask −45 dB, level-gated centroid (integrated hiss over 60k bins dragged pp reference "brightness" to 14 kHz) |
| 6 | **0.464** | HP steepened to order-6 @ 80 Hz (order-4 left 43 Hz rumble at −30 dB rel peak — above the LSD floor), benchmark fmin 90 Hz. v1 0.693 · v2 0.349 · v3 0.365. CURRENT |

Rust engine: **0.477** (inside the seed null). note_params parity via the
shared interp path (verified on woodblock to 2e-16; same code).

## What failed / lessons

- **Anechoic ≠ clean**: the chamber kills the room but the recording
  chain contributes infrasound rumble (2–45 Hz, huge on pp takes) and
  broadband hiss (~30 dB SNR at pp). Every pp-layer "model failure" in
  iterations 1–4 was actually the benchmark scoring the recording chain.
  High-pass both sides identically; gate every metric near the
  reference's noise floor.
- **Fixed-frequency measurement needs junk filters**: measuring the ff
  mode list in soft takes reads noise where a mode didn't speak; filter
  by SNR and decay sanity, then inherit the missing modes from mf with
  per-key fundamental scaling (spectral shape preserved, level right).
- **Damper fade measured, not guessed**: 75 ms median exponential fade
  fit on the MIS `dampen` articulation → `config.release_fade_s`.

## Gate 3 — ship (auto-decision 2026-07-11)

- Rust eval 0.477 vs Python 0.464/0.468 (seeds) — inside null.
- Quality sweep (v2 subset): full 0.427 · p5 0.430 · p3 0.447 · p2 0.375
  · no-noise 0.454 — vibes voices are already tiny (≤10 modes); pruning
  is essentially free, noise (mallet thud) is mild at mf.
- Damper functional (StreamSynth): ring −47 dB within 0.5 s of note-off,
  voice culled. Pedal holds notes (engine pedal path shared with piano).
- Demos: `output/demo/vibraphone/` A/B renders (C4 mf, G3 ff, C5 pp,
  F6 mf) + phrase with releases.
- Testbed: appears as `vibraphone / vibes` via params discovery.

## Data flow

```
reference/vibraphone/raw/*.aif        (Iowa MIS, gitignored)
  └─ python -m instruments.vibraphone.split_raw  → reference/vibraphone/samples/*.flac
       └─ python -m instruments.vibraphone.analyze → reference/vibraphone/analysis/*.json
            └─ python -m instruments.vibraphone.calibrate → instruments/vibraphone/params/vibes.json
                 └─ lab/modal.py (ModalSynth) ← instruments/vibraphone/synth.py
                 └─ core/engine ← instruments/vibraphone/synth_rs.py
                      └─ python -m instruments.vibraphone.evaluate [--engine=rust]
```
