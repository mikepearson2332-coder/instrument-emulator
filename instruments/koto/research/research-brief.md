# Koto / long-zither — research brief

## Physics of sound production

The koto (and its relatives: Chinese zheng, Vietnamese đàn tranh, Korean
gayageum) is a plucked long zither: 13+ strings over a curved wooden
soundbox (paulownia), each string carried by a movable bridge (ji) that
sets its pitch; strings are plucked with plectra (tsume). References:
Fletcher & Rossing ch. 9–10 (plucked strings / guitars & lutes), Ando,
"Acoustics of the koto" (papers in J. Acoust. Soc. Jpn.), Karjalainen,
Välimäki & Tolonen on plucked-string modeling (JASA/DAFx), Weinreich
on coupled string decay.

- **Inharmonic string series**: f_n = n·f0·√(1+B·n²), B small
  (~1e-5..1e-4 for silk/tetron or steel zither strings) — exactly the
  engine's native mode series (`lab.partials.find_partials` applies
  as-is, unlike woodblock/vibraphone).
- **Two-stage decay** per partial: initial fast decay (energy flowing
  into the bridge/body + dual-polarization coupling) then a slower tail —
  the a1/t1 + a2/t2 envelope again (Weinreich's two-polarization
  mechanism, same as the piano's).
- **Pluck excitation**: a plectrum pluck at ~1/5–1/8 of the string length
  imposes a comb-filtered initial spectrum (missing harmonics at
  multiples of the inverse pluck fraction, ~sinc rolloff) plus a short
  broadband plectrum click. Brightness rises with pluck force.
- **Body/room response**: the soundbox adds a short resonant bed;
  VCSL recordings are mid-close with modest room.
- **Release**: strings ring 2–7 s; players damp with the palm — model as
  a fixed short damper fade on note-off.

## Synthesis approach

Modal/additive with the engine's inharmonic string series (no `fr`
needed): per-key f0 + B + per-partial two-stage decays, per-band pluck
click (thump machinery with per-band taus), release fade. This is the
piano pipeline minus hammers, unisons, dampers-by-register, and
sympathetic forest. Waveguide/Karplus-Strong alternatives exist
(Karjalainen et al.) but the modal family is already verified and ships.

## Reference-instrument note

Calibrated on the VCSL đàn tranh (see SOURCES.md for the koto-license
gate decision): steel strings → slightly brighter and longer-ringing
than a tetron-strung koto, same family physics. FluidR3's true-koto
zones serve as a timbre sanity check only.

## Expected difficulties

1. **Pentatonic sampling grid** (minor-third-ish gaps, B2 missing mf):
   key interpolation spans 3–4 semitones — the piano's interpolators
   handle wider gaps already.
2. **Session retuning**: the C#4 string appears in two sessions 35 c
   apart (movable bridges) — cluster per session, use the consistent
   trio, keep the other as a null take.
3. **Pluck-position comb** in the initial amplitudes is per-take (player
   varies position): fitted per layer, not modeled parametrically.
4. Short high-string takes (2.2 s for B5) still contain the full decay.
