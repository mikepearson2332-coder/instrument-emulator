# Koto (long-zither) reference sources

## The koto sourcing problem (gate decision, 2026-07-11, --auto)

No license-clean, adequately-sampled **true koto** reference could be
found. The search, in full:

| candidate | verdict |
|---|---|
| Unreal Instruments "13 Strings KOTO" (≈500 samples, C3–C6, 2 RR — by far the best koto multisample) | **REJECTED at the license gate.** Site terms (About page, JP): 「音源内のデータを許可無く加工、二次配布する事を禁止します」 — unauthorized *modification/processing* (加工) of the sound data is prohibited. Fitting parameters is analysis/derivation; without written permission this fails the gate. Contact: via unreal-instruments.wixsite.com — a future permission request is the upgrade path. |
| Musical Artifacts sf2s (yk_koto CC-BY-3, MFA/UI Koto CC-BY-3, DASS "Koto") | File downloads sit behind an active bot-check (not automated around, per policy); uploader-declared licenses have unverifiable provenance (UI Koto is plausibly an Unreal Instruments repack); DASS is actually a guzheng. |
| FluidR3 GM (MIT, Frank Wen) | Legitimate license and a real koto preset — but only **3 samples** (C5/F#5/F#6), 0.2–0.4 s, truncated + looped, one dynamic. Fails coverage. Kept in `reference/koto/raw/` as a timbre sanity check. |
| Berklee/OLPC volumes, OpenPathMusic (CC-BY), FreePats, Iowa MIS, Philharmonia, VSCO2-CE | No koto at all. |
| Freesound | Only synthesized "koto" tones and full compositions under mixed licenses. |

**Decision:** calibrate the koto-family long-zither model on the
**VCSL Đàn Tranh** (CC0) — the koto's closest relative with a clean
license: both are East-Asian long zithers descended from the Chinese
zheng, with movable bridges and plectrum-plucked strings; the đàn tranh
is somewhat brighter (steel strings vs koto's tetron/silk). The
instrument ships as `koto / tranh` and this substitution is documented
here, in the DEVLOG, and in `docs/instruments/koto.md`. If a properly
licensed koto multisample becomes available, only re-calibration is
needed — the model and pipeline are instrument-family-generic.

## VCSL — Đàn Tranh (primary reference)

- Source: https://github.com/sgossner/VCSL
  (`Chordophones/Zithers/Dan Tranh/Normal/`, master commit
  `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e`, fetched 2026-07-11).
- License: **CC0 1.0 Universal** (repo LICENSE).
- What is used: the 48 `Normal` (plucked) takes — 16 pitches in the
  instrument's pentatonic-ish sampling grid × dynamics mf/f/ff (one B2 mf
  named `b2_mf_1.wav`). Vibrato/tremolo/gliss articulations not used.
- Normalized into `reference/koto/samples/{Note}{Octave}v{1|2|3}.flac`
  (mf/f/ff → v1/v2/v3), pitch-verified during normalization (VCSL names
  may be octave-shifted; f0 detection decides).
- Re-download: raw.githubusercontent.com URLs as above.

## FluidR3 GM (secondary, timbre sanity only)

- Source: https://ftp.osuosl.org/pub/musescore/soundfont/fluid-soundfont.tar.gz
- License: **MIT** (Frank Wen, see bundled readme).
- Used only to compare mode structure/brightness of true-koto plucks
  against the calibrated model — never scored, never calibrated against.

## Research literature

See `research/research-brief.md`.
