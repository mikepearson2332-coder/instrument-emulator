# Koto (long-zither family)

Fourth instrument in the bank (2026-07-11, `--auto` run).

**Reference-instrument note (read this first):** no license-clean true
koto multisample exists — the only rich koto set (Unreal Instruments)
prohibits processing/derivatives of its sound data, and the remaining
candidates fail on provenance, access, or coverage (the full audit is in
`instruments/koto/SOURCES.md`). The model is therefore calibrated on the
**VCSL Đàn Tranh** (CC0), the koto's closest well-licensed relative in
the East-Asian movable-bridge long-zither family; it ships as
`koto / tranh`. The pipeline is family-generic: when a licensed koto set
appears, re-calibration alone upgrades it.

## Sound model

- **Inharmonic string partials** — the engine's native series
  `f_n = n·f0·√(1+B·n²)` with per-key measured f0 and B (~1e-5..1e-3;
  the tranh's pentatonic tuning deviations, up to ±38 c, are kept as
  measured). Up to 40 partials per layer, each with the two-stage
  exponential decay (Weinreich two-polarization physics fits the
  a1/t1 + a2/t2 envelope).
- **Plectrum click**: per-band thump with per-band measured decay times;
  1.5 ms onset ramp; short room bed.
- **Palm-damp release**: `release_fade_s = 0.12` on note-off; strings
  ring 2–7 s if held.
- 14 sampled keys B2–B5 × mf/f/ff (velocities 45/90/127; B2 lacks mf);
  key/velocity interpolation spans the pentatonic gaps.

Dual-polarization envelope beating was implemented as a candidate
(`pol_beat_*` config in `lab/modal.py`) and **lost to the plain render
on the benchmark** — see the DEVLOG.

## Scores (composite, lower = better)

- Take-vs-take null: **1.754** (dominated by a genuine 38 c
  cross-session retuning of the C#4 string — movable bridges).
- Python model: **1.132** (seeds ±0.01) — below the null.
- Rust engine: **1.114**; note_params parity ≤ 1.8e-15.
- Quality: pruning to 16 partials is free; the pluck click (noise) is
  worth ~0.2 composite — keep it.

## Known limitations

- It's a đàn tranh timbre (steel strings: brighter, longer ring) — a
  true koto (tetron/silk) is darker; documented substitution.
- B5's reference takes are 2.2 s; decay fits extrapolate.
- No vibrato/bend articulations (the left-hand pressure techniques that
  define much koto playing are performance-level, not per-note-sample,
  features — they'd need pitch-envelope support in the engine).
