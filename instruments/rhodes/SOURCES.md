# Rhodes (tine electric piano) reference sources

## The MK8 sourcing problem (gate decision, 2026-07-11, --auto)

The target instrument is the **Rhodes MK8** (2021 reissue). No
license-clean MK8 multisample exists: the only MK8 sample set is the
official commercial **Rhodes V8 plugin** (30 000 samples, proprietary,
EULA forbids extraction/analysis; the 14-day trial's terms do not permit
derivative parameter fitting). Search also covered Pianobook (mRhodes —
custom "free to use in music" license, recorded through a specific amp
chain), Cymatics free packs (loops/one-shots, no note×velocity grid),
Discord GM soundfont (CC0-claimed but unverifiable provenance, single
layer, looped), FreePats/Iowa MIS/Philharmonia/VCSL (no tine EP at all).

**Decision (koto-precedent substitution):** calibrate the tine-EP model
on the **jRhodes3d** sampling of a **1977 Rhodes Mark I Stage 73** — the
same tine + tonebar + electromagnetic pickup mechanism as the MK8 (the
MK8 is a re-engineered Mark I-family instrument; its sound-production
physics are identical, with different voicing/pickup positioning). The
instrument ships as `rhodes / mk1`; if a licensed MK8 reference becomes
available, only re-calibration is needed. Documented here, in the DEVLOG,
and in `docs/instruments/rhodes.md`.

## jRhodes3d (primary reference)

- Instrument: 1977 Rhodes Mark I Stage 73 (bought new 1978), sampled by
  Jeffrey Learman ("jlearman").
- Source: https://github.com/sfzinstruments/jlearman.jRhodes3d
  (master; fetched 2026-07-11).
- License: samples **CC BY-NC 4.0** (LICENSE file: "The jRhodes samples
  are licensed under CC BY-NC 4.0 … Credit must be given to the creator;
  Only noncommercial use of the work is permitted. Contact
  jjlearman@gmail.com for commercial licensing options."); control files
  and example clips **CC0**.
- License-gate reasoning: the bar is *legal to analyze* — CC BY-NC
  permits download, analysis, and derivative works (with attribution,
  noncommercial). Only fitted parameters (measured mode frequencies,
  decay rates, level tables — facts about the instrument) ship; no
  samples enter git or any artifact. Attribution: samples by Jeffrey
  Learman, CC BY-NC 4.0. **Caveat for commercial distribution of the
  bank:** if the parameter table were ever deemed an adaptation of the
  recording, NC would bind; upgrade path is a permission request to
  jjlearman@gmail.com. Permissive alternatives were all rejected on
  quality/provenance (above), so the tie-breaker rule does not apply.
- What is used: the 67 mono FLAC samples (up to 5 velocity layers,
  every ~4th white key E1..E7-ish range), key/velocity map parsed from
  `jRhodes3d-mono-no-xfade.sfz` (CC0). Stereo/vibrato variants unused
  (the vibrato is a post-effect; the mono set is the raw harp signal).
- Recording chain: direct from the harp connector (no microphone, no
  room) into a preamp, **with the author's preferred EQ** ("treble boost
  and low-mid scoop to emphasize bell tones and upper-velocity bark" —
  README). This EQ is a fixed linear filter: it is absorbed into the
  calibrated per-note excitation/level tables exactly like a microphone
  response would be. The model therefore reproduces "jRhodes voicing",
  not a flat harp signal — same class of decision as the piano's
  recording-chain findings (see memory/DEVLOG).
- Normalized into `reference/rhodes/samples/{Note}{Octave}v{layer}.flac`
  (gitignored); layer→velocity map in `instruments/rhodes/calibrate.py`.
- Re-download: `git clone https://github.com/sfzinstruments/jlearman.jRhodes3d`
  into `reference/rhodes/raw/`, then `python -m instruments.rhodes.normalize_raw`.

## Rejected candidates (full audit)

| candidate | verdict |
|---|---|
| Rhodes V8 plugin (official MK8) | Commercial, EULA-bound; trial does not license analysis. |
| Pianobook "mRhodes" | Custom license ("use in music"); analysis/derivative status unclear; amp+room in chain. |
| Discord GM sampleset (CC0-claimed) | Provenance unverifiable (likely ripped hardware ROMs); 1 layer, looped. |
| Cymatics "Free Pack Rhodes" | Loops/one-shots, no grid; marketing license, no derivative clarity. |
| FreePats, Iowa MIS, Philharmonia, VCSL, VSCO2-CE | No tine electric piano. |

## Research literature

See `research/research-brief.md`.
