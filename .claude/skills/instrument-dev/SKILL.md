---
name: instrument-dev
description: Develop a new sample-free instrument emulator for the instrument-model bank — find licensed reference samples/soundfonts online, research the instrument's sound-modeling literature, implement and calibrate a model against the reference, iterate until benchmark scores plateau, port to the Rust engine, and register it in the testbed. Use when the user asks to add/develop/model a new instrument (e.g. "/instrument-dev vibraphone", "add a guitar to the bank", "model a woodblock").
---

# Developing a new instrument emulator

You are adding an instrument to a bank of algorithmically generated
instruments: **no audio samples at runtime** — only a small fitted parameter
table rendered by the Rust engine (`core/`). The piano
(`instruments/piano/`, `docs/instruments/piano.md`) is the worked example of
everything below; read `docs/ROADMAP.md` for the architecture and
`docs/library.md` for the runtime/lab APIs before starting.

## Modes

- **Default (checkpointed):** pause and ask the user to confirm at the three
  gates marked ⛔ below. Iterate freely between them.
- **`--auto`:** run end-to-end without pausing; every ⛔ becomes a logged
  decision in the DEVLOG with your reasoning. Use only when the user
  explicitly passed `--auto`.

## Non-negotiable conventions

- Directory layout: lab code + params + docs per instrument in
  `instruments/<name>/`; reference data in `reference/<name>/` (samples
  gitignored — never commit audio); shared framework in `lab/`.
- Keep `instruments/<name>/DEVLOG.md` from day one. Every failed approach
  gets an entry with *why* it failed. Before changing the model mid-project,
  re-read your own DEVLOG.
- Environment: Windows ARM64, Python 3.12, numpy/scipy/soundfile/matplotlib,
  **no librosa/numba**; PowerShell — write scripts, never `python -c`.
- Long runs (analysis, evaluation) go in background; delete stale derived
  JSONs after analysis-code changes or you'll evaluate against
  mixed-version data.

## Step 1 — Reference acquisition ⛔

Find reference recordings covering the instrument's **full pitch range at
multiple dynamics** (isolated notes, minimal room/FX; long decays included).
Good hunting grounds: sfzinstruments/GitHub, FreePats/zenvoid, Versilian
VSCO/VCSL Community Edition, University of Iowa MIS, Philharmonia samples,
polyphone soundfont archive. Quality soundfonts (.sf2/.sfz) are acceptable —
extract their samples into the grid.

**License gate (hard):**
1. BEFORE downloading, record in `instruments/<name>/SOURCES.md`: source
   URL, author, exact license text/name, what will be used. The bar is
   *legal to analyze*: any lawful source qualifies since only fitted
   parameters ship — but permissive (CC0/CC-BY) wins ties, and any source
   whose terms forbid analysis or derivatives is rejected.
2. Samples never enter git regardless of license (`.gitignore` covers
   `reference/*/samples/`). Document the re-download path in SOURCES.md.

Normalize into `reference/<name>/samples/` as a note × dynamic grid with a
deterministic naming scheme (piano: `{Note}{Octave}v{layer}.flac`). Define
the layer→velocity map in the instrument's calibrate module.

⛔ Checkpoint: present source, license, coverage (pitch × dynamics grid),
and any quality concerns. Get confirmation before building on it.

## Step 2 — Research brief

Gather the modeling literature: physics of the instrument's sound
production, modal/synthesis approaches, published parameter values. Search
for papers/theses/patents (Pianoteq-style patents are prior art worth
reading); download PDFs into `instruments/<name>/research/` and extract
text for searchability. Write `research/research-brief.md`: the equations,
what determines pitch/timbre/decay, known synthesis approaches with
citations, and expected difficulties. Do this BEFORE implementing.

## Step 3 — Benchmark design ⛔

Adapt the evaluation harness (`lab/evalharness.py`) to the instrument:

- Write `instruments/<name>/benchmark.py`: a `compare()` building on
  `lab.metrics` (band spectrogram, LSD) plus instrument-appropriate
  structure metrics, and a `composite_score()` with **instrument-specific
  weights**. The piano's weights encode piano truths — never copy them
  blindly. Weight what the ear cares about for THIS instrument (e.g.
  attack transient fidelity for percussion, mode tuning for bells).
- Choose the eval grid from the reference coverage. Establish the metric's
  noise floor early: score the reference against itself with small
  perturbations, and (once a model exists) measure seed-to-seed nulls —
  synthesis uses random phases/noise, so all render comparisons are
  statistical. Judge changes against the null, not absolute thresholds.

⛔ Checkpoint: present metric set, weights rationale, and eval grid.

## Step 4 — Implement

- **Engine family:** if the sound is a sum of decaying resonances
  (struck/plucked strings, mallets, bells, drums, percussion), it fits the
  modal family — reuse `lab/partials.py` measurement machinery and target
  the existing engine (`core/engine`). Harmonic-series instruments use
  `find_partials`; non-string mode series (bars, bells, membranes) need
  their own mode finder but reuse `partial_envelope`/`fit_double_decay`.
  If the instrument needs *continuous excitation* (bowed/wind/brass), STOP
  and discuss with the user — that engine family doesn't exist yet.
- Write per-instrument `analysis.py` (measurement) and `calibrate.py`
  (JSON parameter table into `instruments/<name>/params/`). Start from the
  piano's structure; expect the analysis to be where most iteration
  happens (measurement bugs masquerade as model deficiencies).
- Prototype rendering in Python first (numpy, offline) as the executable
  reference implementation.
- **If multiple modeling approaches are plausible, implement the
  candidates and let benchmark scores + listening choose.** Record the
  loser and why in the DEVLOG.

## Step 5 — Iterate

The loop (order matters): edit analysis and/or synth → if analysis changed,
delete stale derived JSONs and re-analyze → recalibrate → evaluate →
`summarize` by register/dynamic → diagnose the worst cells (comparison
plots; the piano's probe6 mute-one-component pattern attributes
discrepancies fast) → refine. Keep a score-history table in the DEVLOG.
Listen regularly (`output/demo/` A/B renders vs reference) — the composite
score is a proxy, ears are the judge. Stop when scores plateau AND
listening demos pass across the full range.

## Step 6 — Ship ⛔

An instrument is done when it plays in the real-time engine:

1. Port the Python model to `core/engine` (new engine code or new params
   consumed by existing modal code). Verify by the established
   methodology: deterministic paths (param interpolation) match to float
   precision; stochastic renders judged against a seed-to-seed null of the
   Python model; full-grid eval score within the null of the Python
   model's score. See the piano DEVLOG phase-2/3 entries for the traps
   (scipy STFT conventions, RNG realization vs distribution, envelope
   nulls for slow beats).
2. Quality integration: partials must carry salience ordering (A-weighted
   energy) so `Quality.max_partials` prunes gracefully; run a quality
   sweep and record it.
3. Register in the testbed: params JSON in `instruments/<name>/params/`
   makes it appear in the instrument dropdown automatically; verify it
   plays.
4. Write `docs/instruments/<name>.md` (sound model, calibration approach,
   verification results, known limitations) and finalize SOURCES.md +
   DEVLOG.
5. Commit + push (conventions: imperative summary, gates documented in
   the body).

⛔ Checkpoint: present final scores vs null, quality sweep, listening
demos, and the docs. Get sign-off.

## Lessons already paid for (do not relearn)

- **Self-calibrating measurements must reproduce the analysis stack's
  conventions exactly.** The piano's noise calibration measures its own
  output through a scipy-convention STFT; a constant dB offset does NOT
  cancel. Pin conventions empirically (probe script printing reference
  values) before porting any measurement.
- **Nonlinear least-squares decay refinement** on real recordings chases
  attack noise and inflates amplitudes — the robust piecewise-dB fit won.
- **f0 is genuinely ambiguous** where unisons/mode-splits exceed ~10
  cents; pin to a spectral probe instead of free-fitting.
- **Never compare stochastic renders sample-wise or with absolute
  thresholds** — establish the null first.
- **Analysis-stale-data**: evaluators silently mixing old and new analysis
  JSONs produce nonsense comparisons; timestamps guard it, deletion is
  safer.
