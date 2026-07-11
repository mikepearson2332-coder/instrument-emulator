# Vibraphone

Third instrument in the bank (2026-07-11, `--auto` run). Reference:
University of Iowa MIS vibraphone — chromatic C3–F6 (4-octave instrument,
tuned ≈ A442) × 3 dynamics, recorded in an anechoic chamber; damper fade
measured from the MIS `dampen` articulation. License: "may be downloaded
and used for any projects, without restrictions."

## Sound model

- **3–6 modes per bar** at measured frequency ratios (tuned ≈ 1:4:10 for
  the first three bending modes; upper modes untuned and bar-specific),
  each with the two-stage exponential envelope. The aluminum fundamental
  rings 10–30 s; overtones die in 0.5–3 s. Stored as per-partial `fr`
  ratios in `params/vibes.json` (~143 KiB, 42 keys × 3 layers).
- **Per-band mallet thud** (thump machinery, per-band decay times), 2 ms
  onset ramp. The bed calibrates to near-silence (anechoic).
- **Dampers on every bar**: `release_fade_s = 0.075` (measured), no
  remnant; the sustain pedal holds notes exactly like the piano path.
- Motor/tremolo not modeled (reference recorded motor off).

## Calibration pipeline

Range AIFFs are split by HF-flux onset detection (mallet attacks carry
broadband HF the ring lacks; pp needed adaptive thresholds + a minimum
ring-length guard). Mode lists are detected on ff and *measured* at fixed
frequencies in mf/pp (soft strikes put overtones under any detection
gate), with junk-fit filters and per-key inheritance for modes that don't
speak at pp. Everything is measured through an order-6 80 Hz high-pass —
the anechoic recordings carry infrasound rumble up to 26 dB above the
note on pp takes.

## Scores (composite, lower = better)

- Python model: **0.464** (pp 0.693 / mf 0.349 / ff 0.365); seed-to-seed
  null Δ 0.004 ± 0.048.
- Rust engine: **0.477** — inside the null.
- Quality: pruning to 2–5 modes is free-to-noise-level; `noise: false`
  costs only ~0.03 at mf (soft mallets); voices are already ≤10 partials.
- Worst cells are pp top-register notes where the reference's own hiss
  and neighbor-ring bleed dominate (~30 dB SNR takes).

## Known limitations

- pp for E4, G#4, C#6 (+3 keys whose pp fits failed) is imputed from mf
  scaled by the global pp/mf ratio.
- No tremolo (motor) model; no bowed articulation.
- Mallet hardness is a single (yarn) type; brightness–velocity coupling
  comes only from the measured layer differences.
- Reference tuning ≈ A442 is preserved (like the piano's stretch).
