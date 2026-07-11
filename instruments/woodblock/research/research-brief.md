# Woodblock — research brief

## What the instrument is, physically

An orchestral woodblock is a small rectangular block of dense hardwood with
one or two slots cut along its side, struck with a stick or hard mallet. It
is a *struck idiophone*: the sound source is the vibration of the wood body
itself plus the air cavity behind the slot.

Sound production decomposes into:

1. **Stick contact transient** — a broadband click, a few ms long, set by
   the contact stiffness/time of stick on wood (shorter/brighter at higher
   striking force, like the piano hammer). Perceptually dominant: most of
   a woodblock's identity is in the first 10–20 ms.
2. **A small set of damped resonant modes** — the slotted-box plate modes
   and the cavity (Helmholtz-like) resonance. Wood has high internal
   damping, so Q is low: decay times are of order 10–100 ms. Typical
   instruments show one dominant mode (the "pitch" of the block, roughly
   0.6–2.5 kHz depending on size) plus 1–4 weaker modes at *non-integer*
   frequency ratios (idiophone mode series — nothing like a harmonic
   string).
3. **A weak broadband residue** — stick noise and room response, decaying
   in tens of ms.

There is no sustain, no damper, and no release behavior: the note is over
in well under half a second. Velocity affects level and spectral balance
(harder hits excite the higher modes and the contact click more strongly).

## Measured reference (VCSL block, this project)

Probe of the raw files (see DEVLOG): dominant mode cluster at
1.27–1.44 kHz (≈ F6), secondary content near 3.1 kHz, ring to −60 dB
under 0.5 s dominated by room tail. Dynamics change level by ~24 dB
(pp→ff) with visible brightening.

## Known synthesis approaches

- **Modal synthesis** (sum of exponentially decaying sinusoids, one
  second-order resonator per mode) is the canonical technique for struck
  bars/blocks/plates; see e.g. the McGill CAML modal-synthesis notes
  (https://caml.music.mcgill.ca/~gary/618/week11/node10.html), Laroche &
  Meillier "Efficient analysis/synthesis of percussion musical instrument
  sounds using an all-pole model" (IEEE TSAP), and STK/Cook's percussion
  models. Struck-idiophone sounds are exactly "a relatively small number
  of exponentially decaying sinusoids" — the modal engine family in
  `core/engine` is the right target.
- Attack click: standard practice is a short filtered-noise burst (or
  shaped impulse through the resonator bank). The piano model's per-band
  "thump" component is the same idea and is reused here.
- All-pole/coupled-filter variants (US patent 5,748,513; LFM oscillators,
  Hsu & Smyth) exist but offer no accuracy advantage for a 5-mode block
  over direct modal synthesis.

## Mapping onto this project's engine

- **Modes**: measured mode frequencies are NOT an inharmonic string series
  `n·f0·√(1+Bn²)` — they need per-mode frequency ratios. Engine extension:
  optional per-partial `fr` (frequency = fr·f0) with B unused (0). The
  existing two-stage decay (a1/t1 + a2/t2) covers mode decay + room tail.
- **Attack**: the existing per-band thump machinery (10 log bands,
  τ = 20 ms) measured at analysis time. Expect to need the thump to carry
  a much larger share of the energy than in the piano.
- **No unison beating, no dampers, no sympathetic lines** — engine flags.
- **Pitch mapping**: one calibrated block anchored at F6 (MIDI 89);
  other keys transpose f0 (mode ratios and decays fixed). This mirrors how
  sampled woodblocks are mapped across a keyboard.

## Expected difficulties

1. **Attack-transient fidelity dominates the percept** — the benchmark
   must weight the first ~50 ms heavily (piano weights would under-weight
   it badly).
2. **Very short signals**: envelope/decay fitting at 10 ms hop (piano
   default) has only ~5 points above the floor; the analysis needs a finer
   hop (~2 ms) and decay fits over 20–150 ms windows.
3. **Mode clusters**: the 1.27–1.44 kHz "peak" may be 2–3 close modes
   (or a single fast-decaying mode's spectral width). Fitting must not
   invent modes out of one broad peak — check bandwidth-vs-decay
   consistency (a mode with τ = 30 ms has ~11 Hz half-width; a 100 Hz-wide
   bump is not five modes).
4. **Room tail in the reference**: the slow stage of the double decay will
   absorb it; don't chase it with extra modes.
