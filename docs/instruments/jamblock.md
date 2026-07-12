# Plastic jam block (`jamblock / jam`)

LP Jam Block / Meinl "granite block" family — hard-plastic modern
woodblock. Reference: 5 CC0 Freesound recordings of genuine plastic
granite blocks (ashboy34, dry takes) + a CC0 LP Jam Block hit
(Sajmund) as timbre validation. Two documented compromises
(SOURCES.md): single recorded dynamic, and HQ-preview transcodes
(original downloads are login-gated) — the original-WAV upgrade path
changes nothing but re-running the pipeline.

## Sound model

Woodblock's modal machinery, multi-key:

- 4 keys (E5/F#5/G5/C6) anchored at each block's **measured** dominant
  mode (names don't order by pitch); the engine interpolates between
  blocks and transposes beyond — a keyboard-mapped block family.
- Per block: ≤5 modes as `fr` ratios (tighter mode separation than the
  woodblock — 5.5 %/40 Hz vs 10 %/100 Hz — because jam block sibling
  modes are distinct ~30 Hz-wide resonances 5–8 % apart), per-band
  click decay capped 12 ms, bed dropped (woodblock room lesson), no
  dampers.
- **Velocity layers are modeled, not measured**: soft/loud layers are
  derived from the VCSL woodblock's measured pp→ff level + spectral
  tilt + click deltas (same modal family). The benchmark scores only
  the recorded dynamic.

## Results (2026-07-11)

- Composite (woodblock metric set/weights, floor −35 dB): **1.019
  mean** (seeds 0.995–1.031) vs block-vs-block null **0.753** (one
  pair: two different physical blocks sharing a dominant mode —
  a generous floor). F#5 sits at the null; the residual is codec +
  single-take variance (see DEVLOG for the codec-floor lessons).
- Rust: parity ≤ 9.1e-16; rust eval seeds 0.991–1.053 overlap Python.
- Quality: pruning to 2 modes costs +0.03; the click noise is the
  percept — never prune noise for percussion.

## Known limitations

- Velocity response is an analogy (woodblock deltas), not a fit.
- Lossy reference: mode structure and decays are trustworthy, but
  absolute click brightness carries a −6 dB codec compensation that
  should be re-measured from original WAVs.
- C6's sibling modes (−7..−10 dB cluster) partially rejected by the
  mode finder on the codec-noised spectrum; C6 renders slightly
  simpler than the real block.
