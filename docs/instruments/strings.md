# Bowed string sections (`strings / vln|vla|vc|cb`)

The bank's first **engine family 2** instrument (continuous
excitation): orchestral string section sustains. Reference:
**VSCO-2-CE** section susVib (CC0) — violin/viola/cello sections + solo
contrabass (no bass section exists in VSCO2-CE), 2 dynamics each,
unlooped with natural bow attacks/releases; 128 samples, pitch-verified
per file (autocorrelation with upward octave preference). Full audit in
SOURCES.md.

## Sound model — sustained stochastic harmonic bank

`config.engine: "sustained"` switches the engine to family 2
(`core/engine/src/sustained.rs`; executable reference
`lab/sustained.py`):

- **Steady harmonic table** per note × dynamic (body formants and the
  recording's tonal balance baked in, like the piano soundboard).
- **Ensemble texture**: shared vibrato LFO (measured rate per layer,
  FM 3 cents + measured AM depth) + per-harmonic slow random detune
  (4 cents rms, 1 Hz walk) and AM — one-pole noise updated at 64-sample
  hops with analytic stationary gain (identical semantics in both
  engines). FM/drift depths are benchmark-fitted, not measured: section
  recordings can't separate vibrato smear from player spread.
- **Bow-noise bed**: 12 log bands (40 Hz–16 kHz) of steady filtered
  noise, self-calibrated through the family's own 0.2 s-window STFT
  median convention (the modal 46 ms convention cannot resolve
  non-harmonic bins between low-string harmonics).
- **Macro envelope**: smoothstep rise (measured, 0.1–5 s — these are
  section swells), undulating sustain (measured depth/rate, capped —
  see DEVLOG blowup lesson), two-stage release on note-off (bow stop +
  room tail). Sustains indefinitely until note-off.

## Results (2026-07-11)

- Composite (102 cells; steady timbre + modulation-spectrum "shimmer"
  metric + smoothed macro envelope): **1.006 mean** (seeds
  1.006/1.015/1.027), worst ~1.6. Perturbed-self null 0.200 (an
  underestimate — it shares the reference's stochastic realization).
- Rust port: sustained note_params parity ≤ 3.6e-15; renders verified
  statistically; piano/rhodes/jamblock gates unaffected.

## Known limitations

- Contrabass is a solo instrument, not a section.
- Reference room ambience lives in the calibrated noise bed.
- One articulation (susVib); trem/pizz/spic material is downloaded but
  unmodeled.
- Attack bow scratch is smoothed into the rise (section-appropriate;
  a solo bowed instrument would need the waveguide family).
