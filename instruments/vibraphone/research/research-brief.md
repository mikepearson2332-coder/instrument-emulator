# Vibraphone — research brief

## Physics of sound production

Struck aluminum bars with a deep arch cut on the underside, each over a
closed tube resonator. Standard references: Fletcher & Rossing, *The
Physics of Musical Instruments*, ch. 19 (mallet percussion); Bork,
"Practical tuning of xylophone bars and resonators" (Applied Acoustics
46, 1995); Chaigne & Doutaut's time-domain xylophone bar models (JASA
101, 1997); Henrique & Antunes, "Optimal design and physical modelling of
mallet percussion instruments" (Acta Acustica 89, 2003).

- **Tuned bending modes.** The arch is cut so the first three transverse
  bending modes are tuned to ratios ≈ **1 : 4 : 10** (fundamental, double
  octave, double octave + major third). Higher modes are untuned and
  vary bar-to-bar; torsional modes are weak when struck at center.
- **Tube resonators** reinforce the fundamental (and shorten its decay by
  radiation coupling — the classic loudness/sustain tradeoff). With the
  motor off (our reference) the vanes are static; no tremolo.
- **Aluminum has very low internal damping**: the fundamental rings for
  10–40 s (the reference confirms: notes ring 15–30 s). Overtones decay
  in ~0.5–3 s, faster with frequency. Decays are close to exponential;
  the coupled bar+resonator fundamental often shows a two-stage decay
  (fast early / slow late) — exactly our a1/t1 + a2/t2 envelope.
- **Mallet**: soft yarn head → gentle broadband thud, most energy into
  the fundamental; harder strikes excite modes 2–3 and contact noise
  (brightness grows with velocity).
- **Dampers**: a pedal-operated felt bar. Note-off = felt contact →
  exponential fade over ~0.05–0.3 s. All bars are damped (unlike the
  piano's undamped top octave). The MIS `dampen` articulation measures
  exactly this fade.
- MIS instrument specifics (measured during splitting): 4-octave range
  C3–F6, tuned ≈ A442 (+10 c systematic vs A440).

## Synthesis approach

Modal synthesis, same engine family as the piano/woodblock: a handful of
decaying sinusoids at per-mode frequency ratios `fr` (non-integer — the
1:4:10 tuning is approximate per bar) + per-band mallet thump. The
anechoic reference means the "bed" component should calibrate to near
silence. Release uses the engine's `ReleaseStyle::Fade` with the fade
time measured from the dampen takes.

Prior art for mallet-instrument modal synthesis: the same
percussion-modal literature as the woodblock (one resonator per mode);
no new engine machinery is needed beyond what the woodblock added.

## Expected difficulties

1. **Very long decays**: fitting a 10–30 s fundamental decay needs long
   analysis windows and a low floor; eval renders must cap duration
   (8–10 s) to keep runtime sane while still scoring the decay rate.
2. **Two close tuned modes at 4f0** (bending mode 2) vs **3.9–4.1
   variation**: peak separation is fine (modes are far apart in Hz);
   cluster merging is NOT the issue it was for the woodblock.
3. **pp coverage**: 3 keys lack a pp take (E4, G#4, C#6) — impute from
   mf scaled by the global pp/mf ratio so the velocity response stays
   uniform across the keyboard.
4. **Beating** in some bars (bar/resonator detuning) shows as envelope
   ripple; the double-decay fit rides through it, and per-note random
   phases reproduce something similar statistically.
5. The +10 c tuning is real (A442) — keep it, don't "fix" it (mirrors
   the piano's stretch-tuning decision).
