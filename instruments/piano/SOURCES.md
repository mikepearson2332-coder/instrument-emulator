# Piano reference sources

## Salamander Grand Piano V3 (benchmark samples)

- Instrument: Yamaha C5 grand, recorded by Alexander Holm.
- Source: https://github.com/sfzinstruments/SalamanderGrandPiano
  (also mirrored at https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html)
- License: **CC-BY 3.0** (attribution: Alexander Holm).
- Subset used: 30 pitches A0..C8 in minor thirds × velocity layers
  {1, 6, 11, 16} → `reference/piano/samples/{Note}{Octave}v{layer}.flac`
  (120 files, ~171 MB, gitignored — re-download from the source above).
- Layer→velocity map: `LAYER_TO_VEL = {1:8, 6:48, 11:88, 16:127}`
  (`instruments/piano/calibrate.py`).
- Known recording artifacts (see CLAUDE.md gotchas): key-release damper
  cliff, resonance bed, ~50 fixed sympathetic lines incl. 50 Hz-hum
  harmonics, top-octave unison detuning 15–30 cents.

## Research literature

See `research/research-brief.md` for the annotated bibliography; PDFs and
extracted text in `research/`.
