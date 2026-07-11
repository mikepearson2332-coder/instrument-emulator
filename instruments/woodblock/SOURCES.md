# Woodblock reference sources

## Versilian Community Sample Library (VCSL) — Woodblock

- Instrument: woodblock ("wood click"), struck with stick, recorded by
  Versilian Studios LLC (Sam Gossner et al.).
- Source: https://github.com/sgossner/VCSL
  (`Idiophones/Struck Idiophones/Woodblock/`, master commit
  `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e`, fetched 2026-07-11).
- License: **CC0 1.0 Universal** (public domain dedication; LICENSE file at
  repo root). No attribution required; analysis and derivative parameter
  tables unambiguously permitted.
- What is used: all 10 `wood_click*` WAV files — dynamics pp (3 round
  robins), mp (2 recordings incl. `wood_click2`), f (2 round robins), ff
  (1), plus `wood_click3_vl1/vl2`. Normalized into
  `reference/woodblock/samples/` (gitignored) with a deterministic naming
  scheme; see `calibrate.py` for the layer→velocity map.
- Re-download: `curl -L https://raw.githubusercontent.com/sgossner/VCSL/master/Idiophones/Struck%20Idiophones/Woodblock/<file>.wav`
  or clone the repo; `scripts/fetch_reference.py woodblock` re-fetches the
  exact set.
- Quality notes: single woodblock instrument (`wood_click2`/`wood_click3`
  turned out to be alternate takes/blocks — see DEVLOG for measured
  spectra); mono-compatible stereo, mid-close position, low room tone.
  Woodblock is unpitched: the model maps one calibrated block across the
  keyboard by transposing the fitted modes.

## Research literature

See `research/research-brief.md`.
