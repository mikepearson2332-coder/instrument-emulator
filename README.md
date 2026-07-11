# instrument-model — sample-free instrument synthesis

A growing bank of algorithmically generated instruments (currently: grand
piano) — see `docs/ROADMAP.md` for the library architecture and plan.

The piano renders realistic notes and chords from **note + MIDI velocity**
alone: no audio samples at runtime, no internet. The only shipped data is a
~0.5 MB parameter table (`instruments/piano/params/grand.json`) fitted offline
against the Salamander Grand Piano V3 recordings (Yamaha C5, CC-BY 3.0,
https://github.com/sfzinstruments/SalamanderGrandPiano) — the same
"physics + calibrated modal tables" architecture Pianoteq's patent
(US7915515B2) describes.

## Usage

```
python piano.py C4 --vel 100                    # single note -> note.wav
python piano.py "C4 E4 G4" --vel 90 --dur 5     # chord
python piano.py 60 64 67 --vel 80 --play        # MIDI numbers, play on Windows
python piano.py A0 --vel 127 --release 2.5      # key release at 2.5 s
```

Requires: Python 3.10+, numpy, scipy, soundfile.

## Sound model

Per note (interpolated across 30 calibrated keys × 4 velocity layers):

- **Inharmonic partials** `f_n = n·f0·√(1+B·n²)` — B measured per key
  (2.2e-4 at A0 → 1.4e-2 at C8), Railsback stretch tuning (−16¢ … +99¢).
- **Two-stage decay** per partial (prompt sound + aftersound), fitted with
  noise-floor-validated envelopes.
- **Unison detuning**: 2–3 string copies with unequal weights → realistic
  beating without full cancellation.
- **Attack thump**: calibrated band-filtered noise burst (hammer/key noise).
- **Resonance bed**: broadband sympathetic/soundboard noise floor per band.
- **Sympathetic lines**: 17 fixed body/frame resonators (81–1583 Hz) shared
  by every key — measured from the reference instrument.
- **Velocity** interpolates per-partial amplitudes in log domain between
  calibrated layers, reproducing the measured brightness growth.
- **Release**: frequency-dependent damper fade; keys above F#6 undamped.

## Pipeline

```
scripts/analyze_reference.py   FLAC -> per-note JSON (partials, decays, profiles)
scripts/measure_symp.py        global sympathetic line extraction
python -m instruments.piano.calibrate   JSONs -> instruments/piano/params/grand.json
scripts/evaluate.py [--save]   render + score all 120 notes vs reference
scripts/summarize_eval.py      score table by register
scripts/diagnose.py NAME       spectrogram/envelope/spectrum comparison PNG
```

Benchmark metrics per note: partial tuning error (cents), per-partial decay
log-error, log-spectral distance (0–0.5 s and 0.5–2.5 s), RMS-envelope error
(dB), spectral-centroid ratio. Composite score: lower = closer to reference.

## Current benchmark results (120 notes: 30 pitches × 4 velocities)

Composite score by register (iterated from a 1.475 mean baseline to 1.192):

| register | mean score | envelope err | spectral dist (early/mid) |
|---|---|---|---|
| A0–A1 | 0.92 | 2.8 dB | 7.5 / 6.7 dB |
| C2–A2 | 1.11 | 4.0 dB | 7.9 / 7.8 dB |
| C3–A3 | 1.05 | 3.8 dB | 7.8 / 8.7 dB |
| C4–A4 | 1.06 | 5.4 dB | 9.3 / 11.0 dB |
| C5–A5 | 1.12 | 6.6 dB | 10.7 / 10.9 dB |
| C6–A6 | 1.36 | 6.3 dB | 13.2 / 11.1 dB |
| C7–C8 | 1.68 | 6.1 dB | 13.9 / 11.9 dB |

Mean partial-tuning error 5.5 cents (mid-range ~1 c; the top octave figure is
dominated by the real instrument's 15–30-cent unison splits, which make
"partial frequency" ambiguous). Listening demos in `output/demo/` including
synth-vs-reference A/B pairs (`ab_*.wav`: synth first, then the Salamander
sample).

## Documentation map

- `CLAUDE.md` — pipeline commands, iteration loop, gotchas (start here).
- `docs/ROADMAP.md` — library architecture and multi-instrument plan.
- `docs/library.md` — developer reference: runtime crates, lab framework,
  quality system, verification methodology.
- `docs/instruments/piano.md` — how the piano is modeled and calibrated.
- `.claude/skills/instrument-dev/` — the workflow for adding instruments.
- `instruments/piano/DEVLOG.md` — iteration history, failed approaches, bug
  post-mortems, ranked next steps.
- `instruments/piano/research/research-brief.md` — the physics: equations,
  parameter tables, literature citations (companion PDFs alongside).
- `instruments/piano/SOURCES.md` — reference sample provenance and license.
- `output/demo/` — listening demos incl. synth-vs-reference A/B pairs.

## References

See `instruments/piano/research/research-brief.md` (with equations,
parameter tables, citations):
Bank/Zambon/Fontana TASLP 2010 modal piano; Rauhala & Välimäki dispersion
filters; Bensa et al. JASA 2003 loss model; Weinreich coupled strings;
Stulov hammer model; Conklin strike points; Pianoteq patent US7915515B2.
