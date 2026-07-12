# Library reference — how instrument-model works

Audience: developers using or extending the runtime. For the project plan
see `ROADMAP.md`; for per-instrument sound models see `instruments/`.

## Two tiers

**The lab** (Python: `lab/` + `instruments/<name>/`) measures reference
recordings and fits parameter tables. Offline, accuracy-first, never
shipped. **The runtime** (Rust: `core/`) loads parameter tables and renders
audio in real time or offline. The only artifact crossing the boundary is
`instruments/<name>/params/*.json` (~0.5 MB per instrument).

```
reference/<name>/samples (gitignored; provenance in instruments/<name>/SOURCES.md)
   → instruments/<name>/analysis.py  → reference/<name>/analysis/*.json
   → instruments/<name>/calibrate.py → instruments/<name>/params/<variant>.json
   → core/ engine renders from the table          ← the shipped part
   → scripts/evaluate.py scores renders vs reference (lab/evalharness.py)
```

## Runtime (core/) — Rust workspace

### `core/engine` — pure DSP, no devices/threads/OS deps

| module | contents |
|---|---|
| `params` | serde schema for parameter tables (`Table::from_json`). Optional `config` block switches piano semantics → generic modal family: per-partial `fr` frequency ratios (freq = fr·f0, for bar/block mode series), `thump_tau_bands` (per-band click decay), `attack_s` onset ramp, `release_fade_s`/`release_remnant`/`undamped_above` damper behavior (`null` fade = no dampers), `gain_db` bank loudness normalization (see below), `engine: "sustained"` selects engine family 2 (see `sustained`). Absent config = exact piano behavior |
| `sustained` | engine family 2 (continuous excitation): harmonic bank with shared vibrato LFO, per-harmonic slow stochastic FM/AM (64-sample-hop one-pole nodes, analytic stationary gain), 12-band steady noise bed with its own 0.2 s-window STFT calibration, smoothstep rise → undulating sustain → two-stage release on note-off. Reference implementation: `lab/sustained.py` |
| `interp` | key/velocity interpolation → `NoteParams` (deterministic; float-exact vs the Python reference; `fr` log-interpolated like amplitudes) |
| `voice` | `Voice`: streaming render of one note. All per-sample math is recurrences: complex rotators for oscillators, decay-factor states for envelopes. Piano tables get unison beating/split strings; config tables get one plain rotator per partial + shared onset ramp. Components below −140 dBFS are culled per buffer. `Quality {max_partials, noise, max_symp_lines}` prunes at note-on by A-weighted energy salience — tables are never modified |
| `stream` | `StreamSynth`: `note_on/note_off/set_pedal/all_notes_off/render(buf)`, voice culling. The real-time API |
| `synth` | `Piano`: table loading, noise-band calibration, offline `synth_note`/`synth_chord` (thin wrappers over `Voice`) |
| `bench` | host throughput measurement (`run`) and `pick_max_partials(polyphony, cpu_fraction)` |
| `filters` | Butterworth bandpass design + `sosfilt` (matches scipy's transfer function) |
| `stft` | scipy-convention STFT band metric used for self-consistent noise calibration — see "measurement conventions" below |
| `rng` | xoshiro256++ / Marsaglia-polar normals. NOT numpy-compatible: renders match the Python lab statistically, not sample-wise |

### `core/io` — device layer (native only)

`Live`: cpal/WASAPI output stream owning a `StreamSynth` on the audio
thread; control threads enqueue `Event`s (notes, pedal, quality, gain) via
mpsc; meters (voices, DSP load, peak) come back through atomics; soft-clip
master gain; midir MIDI-in (note on/off + CC64 sustain). The audio callback
never takes locks or touches Python.

### `core/python` — PyO3 binding (`instrument_core.pyd`, abi3-py312)

Classes: `Piano` (offline render, `note_params_json`, `set_quality`,
`benchmark_json`, `pick_max_partials`), `StreamSynth` (streaming, no
devices), `Live` (audio+MIDI devices; thread-bound — call from one thread).
Audio buffers are returned as raw little-endian f64 bytes; wrap with
`np.frombuffer`. `instruments/piano/synth_rs.py` provides the ergonomic
wrappers.

Build: `scripts/build_core.ps1` (cargo build --release + stage
`core/dist/instrument_core.pyd`). Requires rustup (aarch64-pc-windows-msvc)
and VS Build Tools ARM64. Tests: `cargo test --release --manifest-path
core/Cargo.toml -p engine`.

Planned bindings (not yet built): C ABI, WASM/npm (`engine` is
device-free specifically so it can compile to WASM and run in an
AudioWorklet).

## Bank loudness normalization

Reference recordings arrive at arbitrary levels, so raw tables render
at wildly different loudness (measured spread: 32 dB). `config.gain_db`
normalizes each instrument to the piano's A-weighted RMS at velocity 96
(median over three register points): applied at the parameter level
(linear on amplitudes, additive on dB profiles) identically in both
engines, so parity checks and per-instrument benchmarks (which
gain-match per note) are unaffected. Measure with
`scripts/measure_bank_loudness.py`; values live in each instrument's
calibrate config so recalibration preserves them. The piano table has
no config block (absent config IS the piano semantics switch) and is
the 0 dB anchor.

## Quality / performance

The quality knob is runtime pruning, not table variants: partials sorted by
A-weighted energy salience at note-on, sympathetic lines by level, then
truncated to the `Quality` budget. Measured on the piano (v11 subset):
pruning to 32 partials is quality-free; 24 → +0.06 composite, 16 → +0.12.
`engine::bench` measures per-partial (~7.4 ns/sample on the dev ARM64) and
fixed per-voice (~273 ns/sample) costs; the fixed cost (53 symp rotators +
noise bands) dominates at high polyphony — the known next lever is a shared
global sympathetic bank (see piano DEVLOG). Reference numbers, one ARM64
core: 16 full-quality voices at 2.3x realtime; 64 voices at the p24_s12
preset at 1.3x.

## Lab (lab/) — shared measurement framework

| module | contents |
|---|---|
| `notes` | note-name/MIDI/frequency conversions |
| `audio` | `load_mono`, `find_onset` |
| `partials` | `find_partials` (inharmonic-string series), `partial_envelope` (complex demodulation with null-placing windows), `fit_double_decay` (robust piecewise-dB), `envelope_window` |
| `metrics` | `band_spectrogram` (60 log bands), `lsd_slice` |
| `evalharness` | `EvalCase` + `run_eval(cases, synth, compare_fn, score_fn)` |

Per-instrument modules supply the analysis recipe, calibration, `compare()`
metric set and composite weights — weights are never shared between
instruments.

## Verification methodology (applies to every port/refactor)

1. **Exact** where deterministic: parameter interpolation, filter transfer
   functions, measurement conventions — unit-tested against reference
   values printed by probe scripts (`scripts/probe_stft_conventions.py`).
2. **Statistical** where stochastic: renders use random phases/noise, so
   engines/seeds are compared against a *null distribution* (same engine,
   different seed). A change passes if its eval-score delta profile is
   indistinguishable from the null (piano null: mean ±0.009, per-note std
   0.143).
3. **Byte-compare** for refactors: moved code must reproduce analysis
   JSONs, `grand.json`, and `eval.json` bit-for-bit.

**Measurement conventions warning:** any measurement the synth calibrates
its own output against (e.g. noise-band levels) must reproduce the analysis
stack's exact conventions — scipy STFT: periodic hann, `1/win.sum()`
scaling, zero boundary extension, t=0 first frame, onesided without
doubling. Constant offsets do NOT cancel; they bias output levels directly.

## Adding an instrument

Use the `instrument-dev` skill (`.claude/skills/instrument-dev/SKILL.md`) —
it codifies the full workflow: licensed reference acquisition → research
brief → benchmark design → implement (candidates compete) → iterate →
Rust port + testbed registration + docs. The testbed
(`testbed/piano_testbed.py`) discovers instruments automatically from
`instruments/*/params/*.json`.
