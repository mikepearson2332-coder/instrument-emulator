# Physically-Based / Parametric Piano Synthesis — Technical Design Brief

(Compiled from literature research, 2026-07-10. Companion PDFs in this folder:
bensa_piano.pdf, cheng_decay.pdf, dafx06_dispersion.pdf, lehtonen_thesis.pdf,
rauhala_excitation.pdf, _bank_taslp10.txt.)

## 1. Stiff-string physics and inharmonicity

Partial frequencies (Fletcher, Blackham & Stratton 1962):

    f_n = n · f0 · sqrt(1 + B·n²)

Inharmonicity from string parameters (Rauhala & Välimäki DAFx-06):
B = π³ Q d⁴ / (64 L² T). For wound bass strings use core diameter for
stiffness but total mass/length for f0 — why bass B stays low.

Measured values: grand B ≈ 1e-4 (bass) → ~1e-2..0.025 (top treble); the
minimum of B(key) ≈ 5e-5..1e-4 sits around keys 15–30. log10(B) is roughly
piecewise-linear in key number: ≈ −3.7 at key 1, min ≈ −4.2 near keys 20–28,
rising to ≈ −2.0…−1.6 at key 88.

## 2. Digital waveguide piano

Loop: excitation → delay z^-N → loss filter → dispersion allpass cascade →
Thiran fractional-delay tuning → feedback. Loop delay = fs/f0.

Loss filter: per-partial loop gain g_k = exp(−1/(f0·τ_k)) = 10^(−3/(f0·T60_k)).
One-pole baseline H(z) = g(1+a)/(1+a z⁻¹); multi-ripple loss filter
(Rauhala/Lehtonen ICMC-05) adds sparse FIR combs for per-partial deviations.

Bensa et al. JASA 2003 damping fits (stiff-string PDE with σ(β)=b1+b2β²,
T60(f) = 6.91/σ):

    b1 = 4.4e-3·f0 − 4.0e-2   [1/s]
    b2 = 1.0e-6·f0 + 1.0e-5   [m²/s]

Per-note examples (Table I): C2: L=1.23m c=160.9 κ=0.58 b1=0.25 b2=7.5e-5;
C4: L=0.63 c=329.6 κ=1.25 b1=1.1 b2=2.7e-4; C7: L=0.10 c=418.6 κ=1.24
b1=9.17 b2=2.1e-3. (T60 fundamental ≈ 6.91/b1: C2≈28s, C4≈6.3s, C7≈0.75s.)

Dispersion filter (Rauhala/Välimäki DAFx-06, cascade of M identical
first-order allpasses A(z) = (a1+z⁻¹)/(1+a1 z⁻¹)):

    a1 = (1−D)/(1+D)
    D(I_key,B) = exp(Cd − I_key·kd)
    I_key(f0) = log_{2^{1/12}}( f0/(27.5·2^{1/12}) )
    kd(B) = exp( k1·(ln B)² + k2·ln B + k3 )
    Cd(B,M) = exp( (m1·ln M + m2)·ln M + m3·ln M + m4 )
    k1=−0.00179 k2=−0.0233 k3=−2.93
    m1=0.0126 m2=0.0606 m3=−0.00825 m4=1.97
    M=8 good; bypass when D<1 (≈ keys 75–88).

Coupled strings (Weinreich JASA 1977): symmetric mode decays fast (bridge
moves), antisymmetric slow → prompt sound ≈ 8 dB/s vs aftersound < 2 dB/s
(Eb3). Mistuning of 0.1 cent already yields double decay; typical unison
mistuning 0.1–2 cents. Implementation options: 2–3 detuned loops (beats
only), bridge coupling filter (STK/Faust commuted piano), Bank's secondary
resonator bank (unidirectional, stable), Rauhala's beating equalizer.

## 3. Modal synthesis (Bank, Zambon & Fontana TASLP 2010 — chosen approach)

Mode k: y_k(t) = A_k e^{−t/τ_k} sin(2πf_k t), A_k = 1/(πLμf_k),
1/τ_k = b1 + b3·2πf_k. Impulse-invariant two-pole resonator:

    p_k = exp(j2πf_k/fs)·exp(−1/(τ_k fs))
    a1 = −2Re{p_k}, a2 = |p_k|², b = (A_k/fs)·Im{p_k}, leading z⁻¹.

Input weights w_in,k = sin(kπx_h/L) — this IS the strike-point comb.
Bridge force F_b ∝ Σ k·y_k(t). Mode counts ~120–140 (bass) → few (treble);
secondary detuned bank for double decay/beats; sympathetic resonance via
R×R region gain matrix (R=8) into secondary banks; pedal = enable routing.

Longitudinal modes / phantom partials (Bank & Sujbert JASA 2005):
f_long,1 ≈ 16–20 × f0; K=2–10 modes suffice. Phantoms at sum/difference
frequencies of transverse partials, amplitude quadratic in level (+2 dB per
1 dB) — bass fortissimo "metallic" character. Tension term
T(t) = T0 + (π²ES/4L²)Σ n²y_n²(t) added to bridge force.

## 4. Hammer–string interaction

Models: power law F = K_h δ^p; Hunt–Crossley F = kδ^p(1+λδ̇); Stulov
hereditary felt (4 params: F0, p, ε, τ0).

Values: p ≈ 2 (bass) → 4 (treble), prefer 2–3. Hammer mass ≈ 11 g (A0) →
4 g (C8). Hammer velocity 0.5 (pp) – 7 m/s (ff), map MIDI velocity
logarithmically. Contact time ~4 ms bass → <1 ms treble, shrinks with
velocity → brighter. Strike point x_h/L ≈ 1/7–1/9 (bass up to 0.158).

Rauhala ICASSP-06 parametric velocity mapping: excitation = one period of
additive partials (ff target amps, random phases, Hann window of length
period/5) + HP noise for keys 1–49; velocity effect = 2nd-order shelf/notch
EQ, max attenuation at 1–3 kHz, up to 30–40 dB at pp; per-key min gains
g_m ≈ −20…−40 dB.

## 5. Soundboard

- Impedance ~1000× string impedance → strings ~rigidly terminated,
  unidirectional energy flow OK.
- Plate-like below ≈1.1 kHz (modal spacing tens of Hz, lowest installed
  modes ≈ 50–100 Hz); above 1.1 kHz inter-rib localization. Damping 1–3%.
- Parametric IR substitutes: FDN; Bank's ~100 log-spaced parallel biquads
  (pole radii R^{θ/π}, R=0.98 at fs/2, zeros by linear LS on target IR);
  filtered noise burst 50–200 ms + low-frequency knock (50–200 Hz modes).
- Duplex scaling: lightly damped resonators near partials of speaking
  length, excited by bridge force → treble shimmer.
- Una corda: zero hammer weight of one string. Sustain pedal: more beating
  in low harmonics, decay time barely changes.

## 6. Key calibration numbers

| Quantity | Value | Source |
|---|---|---|
| B grand | 1e-4 bass → 1e-2..0.025 treble, min ~5e-5–1e-4 keys 15–30 | Rauhala; Fletcher |
| T60 fundamental | bass 10–20 s+, C7–C8 0.5–1 s | Bensa; Weinreich |
| Double decay | prompt ~8 dB/s vs aftersound <2 dB/s | Weinreich |
| Unison mistuning | 0.1–2 cents | Euphonics 7.3 |
| f_long,1 | 16–20 × f0 | Conklin |
| Hammer p | 2→4 bass→treble | Russell |
| Strike point | 1/7–1/9 | Conklin |
| pp vs ff tilt | up to 30–40 dB extra HF attenuation at pp, max 1–3 kHz | Rauhala |
| Modes/note | ~140 bass → few treble | Bank |

## 7. Pianoteq architecture (patent US7915515B2)

Sum of exponentially damped sinusoids + percussion components. Offline FEM
of coupled string–soundboard solved over a constellation of physical
parameter points → modal tables ("timbre coefficients"); runtime
interpolates (Taylor/Padé) and picks among per-velocity excitation sets.
Lesson: precompute modal parameter tables, cheap additive resynthesis at
runtime — the proven sweet spot. (Exactly our architecture.)

## 8. Open-source references

- OpenPiano (C++/JUCE): FD stiff string + hammer; no soundboard; CPU heavy.
- Faust/STK commuted piano (piano.dsp): split at MIDI 88; low notes =
  soundboard-excitation → 4 one-pole velocity-interpolated hammer filters →
  3 coupled detuned delay lines with stiffness allpass; high notes = biquad
  cascade. Per-note pole/zero tables.
- Bank's TASLP 2010 paper = complete implementation spec (docs/_bank_taslp10.txt).
- Chabassier FEM piano (JASA 2013): reference-quality offline model; HAL
  report hal-00873089 has full per-note parameter tables.

## 9. Chosen architecture for this project

Bank-style modal synthesizer calibrated per note/velocity from Salamander
analysis: inharmonic partial bank with two-stage decay + detuned unison
copies, velocity interpolation of per-partial amplitudes in log domain,
parametric attack noise (hammer knock + HP hiss), optional parametric
soundboard resonance + sympathetic coupling for pedal/chords. Benchmarked
against Salamander via partial-tuning/decay/spectral-envelope metrics.
