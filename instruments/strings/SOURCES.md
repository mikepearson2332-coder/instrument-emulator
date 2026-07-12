# Bowed string ensemble reference sources

## Gate decision (2026-07-11, --auto)

Target: orchestral bowed string section sustains (ensemble sound).
Continuous-excitation instrument — engine family 2 (see ROADMAP) does
not exist yet; reference + research proceed, implementation gated on
the engine-family decision (see DEVLOG).

## VSCO-2-CE — string section sustains (primary reference)

- Source: https://github.com/sgossner/VSCO-2-CE (master, fetched
  2026-07-11). Versilian Studios Chamber Orchestra 2 Community Edition,
  Sam Gossner & Simon Dalzell et al.
- License: **CC0 1.0 Universal** (repo LICENSE). Analysis and derivative
  parameter tables unambiguously permitted.
- What is used (all unlooped WAV 44.1 kHz, natural bow attack + release):
  - `Strings/Violin Section/susVib` — 22 files: 11 pitches × 2 dynamics
  - `Strings/Viola Section/susvib` — 26 files: 13 × 2
  - `Strings/Cello Section/susvib` — 27 files: 13 × 2 (+1 RR)
  - `Strings/Solo Contrabass/SusVib` + `SusNV` — 26 + 28 files (no bass
    *section* exists in VSCO2-CE; contrabass covered solo)
  - Section `trem`/`pizz`/`spic` folders kept in raw for later
    articulation work, not part of the sustain benchmark.
- Filename octave convention is ~1 octave below sounding pitch (per
  VCSL/koto precedent) — pitch is verified by f0 detection during
  normalization, names are not trusted.
- Quality notes: real chamber-sized sections in a room (ambience is in
  the recording — same recording-chain-in-benchmark situation as the
  đàn tranh); 2 dynamics = usable velocity axis.
- Re-download: raw.githubusercontent.com per-file (see
  `instruments/strings/fetch_raw.py` manifest), or clone the repo.

## University of Iowa MIS — solo strings (physics substrate, secondary)

- Source: https://theremin.music.uiowa.edu/MIS.html (violin, viola,
  cello, double bass — chromatic, pp/mf/ff, arco vib + non-vib,
  anechoic; pre-2012 mono 44.1/16).
- License: "may be downloaded and used for any projects, without
  restrictions" (site statement; same basis as the vibraphone).
- Role: if the ensemble is modeled as a sum of decorrelated single-player
  processes, Iowa provides clean anechoic per-player measurements
  (Helmholtz spectrum, vibrato, bow noise) that the roomy VSCO2 sections
  cannot. Not downloaded yet — deferred until the engine-family decision.

## Rejected candidates (full audit)

| candidate | verdict |
|---|---|
| Sonatina Symphonic Orchestra (peastman/sso) | CC Sampling Plus 1.0 (retired) would pass, but README admits samples compiled from sources incl. a commercial sampler ROM ("The Complete K2000") and unknown-origin soundfonts — chain of title too weak for fitted tables. Listening cross-check only. |
| Philharmonia | Solo only, MP3-only distribution, bespoke license. |
| Virtual Playing Orchestra | Compilation of SSO/NBO/VSCO2; NBO parts CC BY-SA (copyleft); go to sources directly. |
| FreePats | String sections are synthesized (ZynAddSubFX) — not a real reference. |
| VCSL | No violin-family bowed content (bowed psaltery only). |

## Research literature

See `research/research-brief.md`.
