# instrument-model — sample-free instrument bank

Goal: a bank of algorithmically generated instruments — given note/chord +
MIDI velocity, render realistic audio with **no audio samples at runtime**,
only small fitted parameter tables (`instruments/<name>/params/*.json`).
Each instrument is developed against a reference benchmark (samples or
soundfonts) via research → implement → evaluate iteration. Architecture and
phased plan: `docs/ROADMAP.md`. Currently implemented: **piano** (calibrated
modal synthesis, same family as Pianoteq, patent US7915515B2; benchmarked
against Salamander Grand Piano V3, Yamaha C5).

Layout: `instruments/<name>/` = per-instrument lab code + params + DEVLOG +
research; `reference/<name>/` = reference samples + analysis (samples are
gitignored, see `instruments/<name>/SOURCES.md` to re-download); `lab/` =
shared framework (placeholder until phase 5); `core/` = Rust runtime
(phase 2, not started).

Read `instruments/piano/DEVLOG.md` before changing the piano model — it
records which approaches already failed and why.
`instruments/piano/research/research-brief.md` has the physics/equations.

## Commands (piano)

```
python piano.py "C4 E4 G4" --vel 90 --dur 5 [--play] [--release 1.5]   # the app
python scripts/analyze_reference.py [NAMEv#...]   # FLAC -> reference/piano/analysis/*.json
python scripts/measure_symp.py                    # global sympathetic lines -> reference/piano/symp.json
python -m instruments.piano.calibrate             # JSONs+symp -> instruments/piano/params/grand.json
python scripts/evaluate.py [--save] [NAMEv#...]   # render+score vs reference -> output/eval.json
python scripts/summarize_eval.py                  # score table by register
python scripts/diagnose.py C4v11 ...              # comparison PNGs -> output/diag/
python scripts/demo.py                            # listening demos -> output/demo/
```

## Full iteration loop (order matters)

1. Edit `instruments/piano/analysis.py` (measurement) and/or
   `instruments/piano/synth.py` (rendering).
2. If analysis changed: `Remove-Item reference/piano/analysis/*.json` then
   re-run `analyze_reference.py` (~12 min) and `measure_symp.py` (~6 min; it
   reads the analysis JSONs to exclude note partials).
3. `python -m instruments.piano.calibrate` (seconds).
4. `python scripts/evaluate.py --save` (~12 min) + `summarize_eval.py`.
   Composite score: lower = better. Current best mean: **1.192** (2026-07-11).
5. Synth-only changes skip step 2-3: just evaluate.

`analyze_reference.py` skips JSONs newer than their FLAC — delete stale JSONs
after analysis-code edits or you'll evaluate against mixed-version data.

## Key facts / gotchas

- Reference: `reference/piano/samples/{Note}{Octave}v{1|6|11|16}.flac`,
  30 pitches A0..C8 in minor thirds. Layer→velocity map `LAYER_TO_VEL =
  {1:8, 6:48, 11:88, 16:127}` in `instruments/piano/calibrate.py`.
- Samples contain a key-release damper cliff (detected, decay fits truncated
  before it), a broadband resonance bed, ~50 fixed sympathetic lines
  (81 Hz–2.5 kHz; some are 50 Hz-hum harmonics of the recording), and
  top-octave unisons detuned 15–30 cents (f0 is genuinely ambiguous there).
- This piano's stretch tuning runs −16 c (A0) to +99 c (C8) vs equal
  temperament; C8's B ≈ 1.4e-2. Both are real, not bugs.
- Windows on ARM64, Python 3.12: numpy/scipy/soundfile/matplotlib installed;
  no librosa/numba. PowerShell quoting: use scripts, not `python -c`.
- Keys above MIDI 89 have no dampers (release does nothing there) — modeled.
- Evaluation metric weights are piano-specific; new instruments get their own
  (shared harness arrives with `lab/` in phase 5).
