# Development log — plastic jam block model

Run in `--auto` mode (2026-07-11): checkpoint gates are logged decisions,
not pauses.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**Source: 5 CC0 Freesound "granite block" hits (ashboy34) + LP Jam Block
validation hit (Sajmund).** Full audit + the two documented compromises
(single dynamic; HQ-preview transcodes because original downloads are
login-gated) in SOURCES.md, including the original-WAV upgrade path.

- Anchors measured, not name-derived (`scripts/probe_jamblock.py`) —
  "small" vs "smaller" do NOT order by pitch: E5 649.7 Hz (large),
  F#5 732.1 (medium), G5 765.4 (smallgranite), C6 1056.8 (smaller).
  largegranite and medlargegranite share a ~648 Hz dominant → medlarge
  became `E5v1_alt1`, the take-vs-take null set (woodblock pattern).
- Character confirms hard plastic: ring-to-−40 dB 58–132 ms, dominant
  mode + siblings 5–8 % away, strong ~2× overtone, sub-300 Hz strike
  thud in some takes.

## Gate 2 — benchmark design (auto-decision 2026-07-11)

**The woodblock benchmark verbatim** (`instruments/woodblock/benchmark`):
same struck-block percept → same metric set and weights (attack +
short-time envelope dominate, floor −35 dB). Adopting rather than
re-deriving is the design decision; the composite is comparable across
the two blocks by construction. Null: E5 primary vs alt = **0.753** —
a deliberately generous floor (different physical block, same dominant
mode). Synth seed-to-seed spread at the mean: ±0.015 (Python),
overlapping Rust seeds 0.991–1.053. Eval grid: the 4 recorded cells
(vel 96); derived velocity layers are excluded from scoring.

## Velocity layers (modeled, not measured)

The reference has one dynamic. Playable soft (vel 20) / loud (vel 127)
layers are derived at calibration time from the **VCSL woodblock's**
measured pp→ff deltas (same modal family): per-pair level + spectral
tilt (dB/oct fit over partial ratios) + per-band thump deltas, applied
to each block's measured layer. `calibrate.py::_layer_delta`. Honest
label: velocity response is an analogy, not a fit.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 1.256 | baseline via woodblock pipeline (mode finder + thump/bed, bed dropped per woodblock room lesson) |
| 2 | 1.254 | tighter mode separation (5.5 % / 40 Hz vs woodblock's 10 % / 100 Hz — jam block sibling modes are distinct ~30 Hz-wide resonances 5–8 % apart); little score change but honest structure |
| 3 | 1.095 | codec-floor guards: Vorbis noise floor was minting tau=100 s "no decay" tails and −60 dB junk modes (t2 capped 0.3 s, junk dropped); thump band taus capped 12 ms (measured slopes flatten on the codec floor; mid-time bands were +10..+29 dB) |
| 4 | 1.031 | thump −6 dB codec compensation (noise-fill around the transient inflates inter-mode bins; mute-one-component attribution + band diag) |
| 5 | **1.019** (rust 0.991–1.053 across seeds) | unmask near-dominant modes (`unmask_rel=0.5`): E5's real −3 dB sibling at 577 Hz was SNR-masked because its noise probe sat inside the 650 Hz skirt. CURRENT |

Python seeds at iter 5: 1234/4321/777/99 → 1.019 / 1.001 / 1.003 / 0.995.
F#5 sits at the null (0.745 vs 0.753); E5 worst at 1.25 (its 3.6 s file
is mostly codec tail; centroid residual 1.47). The remaining gap to the
null is codec + single-take variance, not model structure — plateau.

## What failed / lessons

- **Lossy-preview references poison three separate measurements** the
  same way (a flattening noise floor): decay tails ("no decay"
  sentinels), per-band click taus, and inter-mode thump levels. Guards +
  a fixed −6 dB thump compensation fixed scoring; original WAVs are the
  real fix (SOURCES.md).
- **One separation rule does not fit all blocks**: the woodblock's 10 %
  mode-merge slices jam block sibling modes that are genuinely distinct.
  `find_modes` is now parameterized (woodblock defaults byte-identical —
  regression gate re-run: 1.362, unchanged).
- **Noise probes fail between close siblings** — probe midway between
  two modes 6 % apart sits in both skirts; near-dominant modes are now
  exempt from SNR masking (`unmask_rel`).

## Gate 3 — ship (auto-decision 2026-07-11)

- No engine changes needed (generic modal config: `fr` ratios, per-band
  click decay, `release_fade_s: null`).
- **Rust parity**: note_params ≤ 4.9e-16 rel; eval seeds overlap Python's.
- **StreamSynth smoke test caught a real engine bug**: B = 0 tables
  (first in the bank) made the Rust B-interpolation NaN (`ln(0)`,
  missing the Python floor/clamp) → NaN salience → panic in the voice
  sort. Fixed in `interp.rs` (mirrors Python exactly; B > 0 tables
  unaffected) + `voice.rs` sort hardened with `total_cmp`. Piano gate
  re-verified after the fix (see rhodes DEVLOG — shared fix).
- Quality: prune to 2 modes costs +0.03 (score 1.049) — the click noise
  is the percept and must never be pruned (woodblock lesson holds).
- Testbed: `jamblock / jam` appears via params discovery.
