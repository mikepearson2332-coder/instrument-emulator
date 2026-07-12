# Plastic jam block reference sources

## Gate decision (2026-07-11, --auto)

Target: plastic jam block (LP Jam Block / Meinl "granite block" family —
hard-plastic modern woodblock). No multi-dynamic multisample exists
anywhere license-clean (VCSL, VSCO2-CE, FreePats, Iowa MIS, Philharmonia
all audited: zero jam block content). Three independent CC0 Freesound
recordings of genuine LP/Meinl-style plastic blocks cover 6 distinct
blocks at ONE dynamic each — adopted with two documented compromises:

1. **Single dynamic layer.** Velocity response cannot be fitted from
   this reference. Playable velocity layers are *modeled by analogy*
   from the VCSL woodblock's measured pp→ff behavior (same modal family,
   same engine config) and are excluded from the benchmark, which scores
   only the recorded dynamic.
2. **HQ preview transcodes.** Freesound original-quality downloads
   require an authenticated account (bot-gated; not automated, per
   policy — same call as the koto's Musical Artifacts audit). The
   publicly served HQ previews (Ogg Vorbis ~192 kbps / MP3 128 kbps,
   from the 44.1 kHz/16-bit originals) are used instead. For a 1.4 s
   percussive hit with modes at 0.8–6 kHz this is a usable but lossy
   reference — benchmark floors are kept shallow (−35 dB) so codec
   noise is never scored. **Upgrade path:** log into Freesound, download
   the 7 original WAVs into `reference/jamblock/raw/`, re-run the
   pipeline (naming below); nothing else changes.

## ashboy34 — "Granite Blocks" pack (primary, 5 blocks)

- Source: https://freesound.org/people/ashboy34/packs/30699/
  (fetched 2026-07-11, HQ previews via cdn.freesound.org).
- License: **CC0 1.0** (verified per file).
- What is used: the 5 `*dry.wav` takes (no added reverb) —
  smallest/small/medium/medlarge/large granite blocks, single hits,
  stereo 44.1 kHz/16-bit originals, ~1.4 s each:
  | id | file | role |
  |---|---|---|
  | 544883 | smallgranitedry | block 5 (highest) |
  | 544881 | smallergranitedry | block 4 |
  | 544879 | mediumgranitedry | block 3 |
  | 544877 | medlargegranitedry | block 2 |
  | 544875 | largegranitedry | block 1 (lowest) |
  (`*wet` takes rejected: added reverb.) Preview URLs:
  `https://cdn.freesound.org/previews/544/{id}_249377-hq.ogg`.
- The 5 blocks anchor 5 pitches; the model interpolates between them
  and transposes beyond, giving a playable keyboard-mapped block family
  (richer than the single-anchor woodblock).

## Sajmund — LP Jam Block hit (validation, 1 block)

- Source: https://freesound.org/people/Sajmund/sounds/132417/
  ("Percussion clave like hit" — LP red Jam Block, medium pitch,
  Vic Firth 7A stick; Edirol R-09 field recording, some room).
- License: **CC0 1.0** (verified).
- Preview: `https://cdn.freesound.org/previews/132/132417_2412414-hq.mp3`
  (48 kHz original). Used as a timbre sanity check of the genuine LP
  branded instrument against the calibrated granite-block model —
  never scored, never calibrated against (room + handheld chain).

## Rejected candidates

| candidate | verdict |
|---|---|
| Sassaby "Wood Block" 533093 (LP Jamblock, CC0) | 0.5 s truncated tail; uploader says pack content "made **or sourced**" — weakest provenance; dropped. |
| GR3AVE5Y "Granite Blocks" pack (CC0) | Rhythm passages, not isolated hits; segmentation-only backup. |
| Sadiquecat percussion one-shots | Re-processed (reverb/compression) derivative of ashboy34's material. |
| VCSL/VSCO2-CE/FreePats/Iowa/Philharmonia | No jam block family content at all. |

## Research literature

Modal percussion physics as the woodblock
(`instruments/woodblock/research/research-brief.md`): rectangular
hard-plastic shell with slit → few strong wall/cavity modes, fast
decay, dominant "clack". Plastic (vs wood): higher Q on the main mode,
more pronounced pitch, slightly longer ring. No jam-block-specific
literature exists; the woodblock brief plus measured spectra carry the
model.
