# Development log — Rhodes (tine electric piano) model

Run in `--auto` mode (2026-07-11): checkpoint gates are logged decisions,
not pauses.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**Target: Rhodes MK8. Reference: jRhodes3d (1977 Mark I Stage 73), CC
BY-NC 4.0 — a koto-style substitution** (no license-clean MK8 multisample
exists; the only MK8 set is the proprietary Rhodes V8 plugin). Same
tine + tonebar + electromagnetic-pickup mechanism; ships as `rhodes / mk1`.
Full candidate audit + license-gate reasoning in SOURCES.md.

- Coverage: 15 pitches F1(29)..C7(96) every ~5 semitones × up to 5
  velocity layers (65 mono FLACs, 44.1 kHz, up to 25 s unlooped decays).
  High notes are sparser: B4/E5 lack v3; A5/D6/G6/C7 lack v3+v5 (the sfz
  reuses neighbour takes there — we keep only true recordings, the
  calibrator interpolates the gaps).
- Layer→velocity map from the sfz groups (v1 soft .. v5 loud):
  `{1: 24, 2: 60, 3: 84, 4: 104, 5: 120}` (group centers).
- Recording chain: DI from the harp connector — **no microphone, no
  room** (a first for this bank: the piano/woodblock/koto references all
  fought room+chain artifacts). Author's fixed EQ (treble boost, low-mid
  scoop) is absorbed into the calibrated tables like any chain response.
- No round robins → no take-vs-take null; the benchmark null must come
  from seed-to-seed synth renders + perturbed self-comparison of the
  reference.

## Gate 2 — benchmark design (auto-decision 2026-07-11)

Metrics (`benchmark.py`), tine-EP percept order: harmonic balance >
sustain decay > attack. `harm_db` (mean |dB diff| of the first 8 matched
harmonic amplitudes, each side self-normalized) is the timbre core — an
EP's character IS the fundamental/bell/bark mix and its velocity
dependence. Rest as koto with EP scales: partial_cents/10 (guard only —
exact harmonics), decay_logerr×1.5 (tau_slow of first 6 harmonics, capped
12 s), env_db/3 (5 ms hop, 6 s window — notes sing for many seconds),
attack_db/4 (1 ms hop, 80 ms), lsd_early/5 + lsd_mid/7 at **floor −40 dB**
(DI recording: no room, tails bottom at −51..−78 dB — deeper floors than
the mic'd instruments are meaningful), |log centroid_ratio|×2.

Null (no round robins): perturbed self-comparison — reference vs itself
trimmed 2–8 ms + gain-jittered ±0.5 dB, deterministic per case:
**mean 0.280 std 0.197**. Strongly register-dependent: bass cells with
sharp attacks + slow beats float 0.5–0.8 (the trim de-aligns the 1 ms-hop
attack metric), treble sits 0.06–0.2. Judge per-register, not just the
global mean. Eval grid: all 65 recorded cells, dur_cap 8 s.

## Research (2026-07-11)

`research/research-brief.md` + 8 PDFs (Pfeifle/Münster Rhodes
measurement + FPGA papers, Falaize & Hélie port-Hamiltonian model,
Shear & Wright tine data, Rhodes patent US 2,972,922, Novak pickup
nonlinearity). Decisive facts for the model:

- The tine rings as a **pure decaying sinusoid after ~10–14 ms**
  (high-speed camera); essentially all steady harmonic content is the
  **pickup's memoryless nonlinearity** (flux ≈ a + k/(x+gap)²), so the
  partials are EXACT harmonics — `find_partials`' free inharmonic fit
  mislocks on loud takes and is snapped to a forced-harmonic grid
  (analysis.py::snap_harmonic), B := 0.
- Harmonic n scales ≈ (tine swing)ⁿ → decay rate of harmonic n ≈ n×σ
  and the spectrum is velocity- AND time-varying. A per-layer static
  modal fit is therefore *structurally exact* in the small-signal
  regime; the deviation is the loud-bass "bark/bloom" (below).
- Tonebar modes are far from the tine (100s–1400+ cents) and matter
  only in the attack — covered by the thump bands, not partials.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 0.617 | first full baseline (koto pipeline + harmonic snap, B=0) |
| 2 | 0.837 | NNLS amplitude re-solve over full envelope — REGRESSION: near-floor tail dominates relative-error LS on short notes (C7 lsd_early 10+) |
| 3 | 0.739 | + log-spaced sampling — still regressed: demod settle-region samples (tiny, huge relative weight) crush amplitudes (F1v1 fundamental −22.7 dB vs dominant) |
| 4 | 0.734 | + settle exclusion (t ≥ 1.5 demod windows) — bulk fixed, bloomers now flat-held by a 12 s basis tau → tail overshoot (E2v5 1.69 vs 1.39 at iter 1) |
| 5 | 0.630 | hybrid: classic capped fit for normal envelopes, NNLS flat-hold for bloomers — median improved (0.509) but bloomer tails still overshoot |
| 6 | **0.609** (median 0.509) | classic capped fit for EVERYTHING + settle exclusion. Beats iter 1 on mean and median; seed spread ±0.006. CURRENT |

Seeds at iter 6: 1234/4321/777 → 0.609 / 0.638 / 0.641... (mean spread
±0.006 after re-render; values 0.630/0.638/0.641 measured at iter 5
params — see eval logs). Null (perturbed self): 0.280 ± 0.197,
register-dependent (bass 0.5–0.8, treble 0.06–0.2).

### Known limitation — loud-bass bloom (engine-extension candidate)

Loud bass reference envelopes RISE for seconds (E2v5 fundamental peaks
at t = 4.2 s, +7 dB): pickup harmonic redistribution as the tine swing
decays through the nonlinear zone. A nonnegative double-exponential
cannot rise; every fitting scheme tried (iters 2–5) either inflates
t=0 (killing gain normalization) or overshoots the tail. Those ~8 cells
plateau at 1.2–1.4 vs bass-null 0.6–0.8. The honest fix is an engine
extension — a signed fast component (a2·e^{−t/τ2} − |a1|·e^{−t/τ1})
per partial — but it breaks log-domain amplitude interpolation in BOTH
engines (log of negative) and salience ordering; costed and deferred.
Audibility: the model renders a smooth sustain instead of a swelling
growl on hard-struck bass notes.

## What failed / lessons

- **Relative-error NNLS over an envelope is a trap twice over**: the
  near-floor tail (thousands of samples) and the demod settle region
  (tiny values → enormous relative weight) each dominate the solve in
  different directions. Log-spaced sampling + settle exclusion fix the
  sampling; but the classic piecewise-dB fit with woodblock caps still
  beat every NNLS variant end-to-end. Measured, not assumed: iters 2–5.
- **f0 drifts per take** (F1: −15.5c to +3.3c across layers — tine
  tuning/session drift, not error). One f0 per key (median) costs ~20c
  partial_cents on the worst layer; per-layer f0 is not representable
  in the engine's key schema. Accepted.

## Gate 3 — ship (auto-decision 2026-07-11)

- No engine feature changes needed: generic modal config (n-series,
  B = 0, damper fade 0.15 s). BUT the table is the bank's first with
  B = 0 everywhere, which exposed a **Rust interp bug**: log-domain
  B lerp did ln(0) → NaN → NaN salience → panic in the voice sort
  (StreamSynth smoke test caught it; offline eval never interpolates
  between keys). Fixed in `interp.rs` (mirrors the Python floor/clamp
  exactly; B > 0 tables byte-unaffected) + `voice.rs` sort hardened
  (`total_cmp`). Piano gate re-verified: `compare_engines.py` OK;
  koto/woodblock rust evals re-run unchanged.
- **Rust parity**: note_params ≤ 1.9e-15 rel over the full grid; rust
  eval 0.638 vs python seeds 0.630/0.638/0.641 — inside the null.
- **Quality sweep** (rust): full(24) 0.638, p16 0.723, p8 0.842 —
  bass harmonics matter; p16 is the lowest defensible preset.
- Testbed: `rhodes / mk1` appears via params discovery; StreamSynth
  renders, note-off damps, voices cull.

### Iteration 1 diagnosis (worst: loud bass, 1.2–1.4)

Loud bass harmonic envelopes are NOT double-decays: the fundamental
*blooms* (E2v5 n1 peaks at t=4.2 s, +7 dB over its early level — pickup
nonlinearity relaxing as tine swing decays) and the RMS envelope beats
slowly. `fit_double_decay` anchors at env argmax and extrapolates to
t=0 → amplitudes inflated 8–22 dB (2.2× cap still +7 dB) → every partial
starts hot → peak-RMS gain normalization drags the render ~10 dB down →
env_db/attack_db blow up. Same failure class as the woodblock's
"explosive t=0 extrapolation" lesson, different disguise.
