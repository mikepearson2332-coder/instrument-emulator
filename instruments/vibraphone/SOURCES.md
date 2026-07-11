# Vibraphone reference sources

## University of Iowa Musical Instrument Samples (MIS) — Vibraphone

- Instrument: vibraphone, performer Andrew Thierauf, recorded 2013-06-10
  in an **anechoic chamber** (Earthworks QTC40 at 5 ft) — no room tail to
  untangle from bar decay. 24-bit / 44.1 kHz stereo AIFF.
- Source: https://theremin.music.uiowa.edu/MISvibraphone.html
  (files under `sound files/MIS/Percussion/Vibraphone/`).
- License: site-wide statement (https://theremin.music.uiowa.edu/MIS.html):
  recordings are "freely available on this website and may be downloaded
  and used for any projects, without restrictions." Analysis and fitted
  parameter tables unambiguously permitted.
- What is used:
  - `Vibraphone.sustain.{pp,mf,ff}.{C3B3,C4B4,C5B5,C6F6}.aif` — struck,
    motor off, ringing undamped: the calibration set.
  - `Vibraphone.dampen.mf.*.aif` — pedal-damped strikes: measures the
    damper fade time for release modeling (not part of the eval grid).
- Multi-note range files are split on onsets and pitch-identified into
  `reference/vibraphone/samples/{Note}{Octave}v{layer}.flac` with
  layer→velocity map in `instruments/vibraphone/calibrate.py`
  (pp→1, mf→2, ff→3). Raw range files kept in
  `reference/vibraphone/raw/` (both gitignored).
- Re-download: `curl -L "https://theremin.music.uiowa.edu/sound%20files/MIS/Percussion/Vibraphone/<file>"`,
  then re-run the splitter (`python -m instruments.vibraphone.split_raw`).
- Quality notes: anechoic recording means no reverb bed (bed profile
  expected near silent); vibrato motor off in sustain takes; some takes
  may include mallet prep noise — the splitter gates on onset level.

## Alternative considered

VCSL vibraphone (CC0): per-note files but only 2 velocities per mallet
type, mixed hard/soft mallets, minor-third grid. Iowa MIS wins on
chromatic coverage × 3 consistent dynamics and the anechoic room.

## Research literature

See `research/research-brief.md`.
