# Instrument bank — architecture & roadmap

Status: **draft for review** (2026-07-11). Decisions agreed in discussion; phase
ordering and details open to change.

## Vision

A bank of algorithmically generated instruments — no audio samples at runtime,
only small fitted parameter tables — usable as a library from other projects
(JavaScript included), rendering realistic instrument audio both in real time
and offline. Each instrument is developed the way the piano was: find a
reference benchmark, research the physics/modeling literature, implement,
iterate against the reference until scores converge.

## Two-tier architecture

### Tier 1 — the lab (Python, per instrument)

What exists today for piano, generalized. Offline, accuracy-first, never
shipped. Per instrument it produces one artifact: a parameter table
(`instruments/<name>/params/<name>.json`, ~0.1–1 MB).

- reference acquisition (samples / soundfonts, with recorded provenance + license)
- analysis (partial tracking, decay fitting, excitation spectra…)
- calibration (fit parameter tables)
- evaluation (render with the *runtime* engine, score vs reference)
- diagnostics & listening demos

### Tier 2 — the runtime (Rust core)

The shippable library. Loads parameter tables, renders audio in real time
(callback-buffer streaming) or offline (arbitrary-length render). One
implementation, three faces:

| Binding | Mechanism | Consumer |
|---|---|---|
| C ABI | `#[no_mangle] extern "C"` | C/C++, C#, anything FFI |
| WASM + npm package | `wasm-bindgen` / `wasm-pack` | Browsers (AudioWorklet), Node.js |
| Python | PyO3 wheel | The lab itself + Python consumers |

The lab evaluates through the Python binding, so the engine that gets scored
is byte-identical to the engine that ships. `pianomodel/synth.py` remains as
the executable spec during the port, then becomes reference-only.

**Engine families.** The core hosts multiple engine families behind one
voice/render API. Family 1 (modal: banks of exponentially decaying resonators
+ excitation model + coupling/resonance bed) covers piano, percussion,
mallets/bells, plucked strings. Family 2 (continuous excitation:
waveguide/source-filter for bowed strings, winds, brass) is deferred until
family 1 is mature. Each instrument declares `engine + param table` in a
bank manifest.

## Quality ↔ performance calibration

Modal synthesis has a natural quality axis: resonators per voice. Design:

- Parameter tables store modes sorted by perceptual salience (masking-aware,
  not just amplitude), so truncation at any prefix is the quality knob.
- Named quality levels select mode budgets + feature toggles (sympathetic
  resonance, soundboard IR, phantom partials).
- `benchmark` API: measure resonators/sec on the host, then solve for the
  best quality level given a target polyphony and CPU budget (e.g. "64 voices
  in ≤30 % of one core"). Callable at app startup or offline.
- Graceful degradation under load: drop least-salient modes first, never
  glitch the buffer.

## Repo restructure (target shape)

```
instrument-model/
  core/               # Rust workspace: engine families, bank loader, C ABI, WASM, PyO3
  lab/                # Python: shared analysis/calibration/eval framework
  instruments/
    piano/            # per-instrument: lab code, params/, docs, DEVLOG
    percussion/
    ...
  reference/          # per-instrument reference sets (gitignored samples + analysis JSONs)
  testbed/            # GUI app
  docs/
    library.md        # developer reference for the runtime API
    instruments/      # one modeling doc per instrument
  scripts/            # thin entry points (analyze/calibrate/evaluate --instrument X)
```

## Testbed

Small GUI app (Python + tkinter now — already available; the runtime core does
the audio, so the GUI tech is disposable). Features: instrument selector,
on-screen keyboard (mouse + computer-keyboard mapping), velocity control,
MIDI-file playback, voice/CPU meter, quality-level switch. Live MIDI-in wired
behind the same event path, activated when a controller is available.

## Instrument-dev skill

Codifies the piano workflow so new instruments follow it:

1. **Reference**: find high-quality samples or soundfonts online; verify
   license; record provenance in `instruments/<name>/SOURCES.md`; download and
   normalize into the reference layout (note × velocity grid).
2. **Research**: gather modeling literature (papers, theses, patents) into
   `instruments/<name>/research/`; write a research brief (physics, equations,
   known approaches, expected difficulties).
3. **Implement**: pick/extend an engine family; write analysis + calibration
   for the instrument; if multiple modeling approaches are plausible,
   implement candidates and let the eval scores choose.
4. **Iterate**: evaluate across the full pitch × velocity range; diagnose the
   worst cells; refine; keep a DEVLOG of what failed and why (the piano
   DEVLOG convention).
5. **Done when**: scores plateau across the range and listening demos pass;
   write `docs/instruments/<name>.md`.

Evaluation harness is shared; metric weights are per-instrument (the piano
composite encodes piano-specific structure and must not be blindly reused).

## Phases

1. **Restructure** to the layout above; piano lab code moves, nothing changes
   behavior. Gate: `evaluate.py` reproduces mean **1.192** exactly.
2. **Rust core + piano port** (largest step). Install Rust (ARM64 MSVC
   toolchain); implement modal engine family; port piano synth; PyO3 binding.
   Gate: Rust render matches Python render (near-sample-exact), eval score
   equal or better; real-time headroom measured.
3. **Quality/perf system**: salience-sorted modes, quality levels, host
   benchmark + auto-preset.
4. **Testbed GUI** (needs `sounddevice` for output — install and verify on
   ARM64; fallback: WASAPI via a small Rust audio thread, which we may prefer
   anyway).
5. **Skill + harness generalization**: extract instrument-agnostic
   analysis/calibrate/evaluate framework; author the skill; write
   `docs/library.md` and `docs/instruments/piano.md` (from DEVLOG + research
   brief).
6. **Instrument 2: unpitched percussion** (woodblock, claves, …) — smallest
   possible exercise of the whole pipeline end-to-end via the skill.
7. **Instrument 3: mallets/bells**, then **plucked strings**. WASM/npm and
   C-ABI packaging polish somewhere alongside 6–7, once the API stops moving.

## Environment notes / risks

- Machine is Windows 11 ARM64. Rust supports `aarch64-pc-windows-msvc` with
  host tools; needs VS Build Tools (ARM64) + rustup. Not yet installed.
- `sounddevice` / `python-rtmidi` not installed; ARM64 wheel availability to
  be verified in phase 4. Mitigation: do audio I/O in Rust (cpal/WASAPI) and
  keep Python GUI as control surface only.
- Soundfont licenses vary wildly — the skill treats license verification as a
  hard gate, and every reference set gets a SOURCES.md.
- Real-time constraint may surface model features that are cheap offline but
  expensive per-buffer (e.g. long soundboard IRs → replace with cheap
  recursive reverb calibrated to match). Expect some quality/architecture
  negotiation during the piano port.
