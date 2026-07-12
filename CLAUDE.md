# instrument-model — sample-free instrument bank

Goal: a bank of algorithmically generated instruments — given note/chord +
MIDI velocity, render realistic audio with **no audio samples at runtime**,
only small fitted parameter tables (`instruments/<name>/params/*.json`).
Each instrument is developed against a reference benchmark (samples or
soundfonts) via research → implement → evaluate iteration. Architecture and
phased plan: `docs/ROADMAP.md`. Currently implemented: **piano** (calibrated
modal synthesis, same family as Pianoteq, patent US7915515B2; benchmarked
against Salamander Grand Piano V3, Yamaha C5), **woodblock** (VCSL),
**vibraphone** (Iowa MIS), **koto-family long zither** (VCSL đàn tranh —
see `instruments/koto/SOURCES.md` for the reference-substitution decision),
**rhodes** (tine EP; MK8 target calibrated on jRhodes3d Mark I, CC BY-NC —
substitution documented in `instruments/rhodes/SOURCES.md`), **jamblock**
(plastic jam block, CC0 Freesound previews; single-dynamic reference,
velocity layers modeled from woodblock deltas), **strings** (bowed string
sections vln/vla/vc/cb, VSCO-2-CE CC0 — the first **engine family 2**
instrument: sustained stochastic harmonic bank, `config.engine:
"sustained"`, reference renderer `lab/sustained.py`, Rust
`core/engine/src/sustained.rs`).
Modal (non-piano) instruments run on the same Rust engine via the table
`config` block (`fr` mode ratios, release styles, per-band click decay);
per-instrument pipelines are
`python -m instruments.<name>.{analyze,calibrate,evaluate}`.

New instruments: use the `instrument-dev` skill
(`.claude/skills/instrument-dev/SKILL.md`) — reference acquisition with
license gate, research brief, benchmark design, implement, iterate, ship
with Rust port. Developer reference for the runtime/lab: `docs/library.md`.

Layout: `instruments/<name>/` = per-instrument lab code + params + DEVLOG +
research; `reference/<name>/` = reference samples + analysis (samples are
gitignored, see `instruments/<name>/SOURCES.md` to re-download); `lab/` =
shared framework (notes/audio/partials/metrics/evalharness — the
instrument-agnostic measurement half); `core/` = Rust runtime —
`core/engine` is the pure-DSP crate (port of the Python synth, verified
against it), `core/python` the PyO3 binding. Build with
`scripts/build_core.ps1` (needs rustup + VS Build Tools ARM64, installed).
`instruments/piano/synth_rs.py` wraps the native module with the same
interface as `synth.Piano`.

Read `instruments/piano/DEVLOG.md` before changing the piano model — it
records which approaches already failed and why.
`instruments/piano/research/research-brief.md` has the physics/equations.

## Commands (piano)

```
python testbed/piano_testbed.py                   # live testbed GUI (audio via core/io)
python piano.py "C4 E4 G4" --vel 90 --dur 5 [--play] [--release 1.5]   # offline CLI
python scripts/analyze_reference.py [NAMEv#...]   # FLAC -> reference/piano/analysis/*.json
python scripts/measure_symp.py                    # global sympathetic lines -> reference/piano/symp.json
python -m instruments.piano.calibrate             # JSONs+symp -> instruments/piano/params/grand.json
python scripts/evaluate.py [--save] [NAMEv#...]   # render+score vs reference -> output/eval.json
python scripts/evaluate.py --engine=rust          # same via Rust core -> output/eval_rust.json
python scripts/summarize_eval.py                  # score table by register
scripts/build_core.ps1                            # cargo build + stage core/dist/instrument_core.pyd
python scripts/compare_engines.py                 # Rust-vs-Python parity smoke test
python scripts/compare_eval_runs.py               # eval.json vs eval_rust.json deltas
python scripts/bench_core.py                      # throughput + streaming + host benchmark
python scripts/quality_sweep.py                   # score vs quality level -> output/quality_sweep.json
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
- The Rust engine is a verified port of `synth.py`: `note_params` matches to
  float precision; renders differ in noise/phase realization (different PRNG),
  so waveforms are compared statistically, not sample-exact. Until the Python
  synth is retired, model changes must be mirrored in
  `core/engine/src/synth.rs` and re-verified (`compare_engines.py` + eval).
