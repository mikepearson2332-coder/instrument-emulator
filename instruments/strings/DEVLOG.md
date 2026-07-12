# Development log — bowed string ensemble

Run in `--auto` mode (2026-07-11) — but this instrument hits the
skill's hard stop: **continuous excitation needs engine family 2,
which does not exist** (ROADMAP defers it until family 1 matured).
Steps 1–2 are complete; implementation is gated on a user decision.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**VSCO-2-CE section sustains (CC0)** — violin/viola/cello sections +
solo contrabass (no bass section exists in VSCO2-CE), susVib, 2
dynamics, unlooped with natural bow attacks and releases. Full audit
(SSO rejected on chain-of-title, Philharmonia on MP3+solo, FreePats
synthesized, VCSL none) in SOURCES.md. Iowa MIS solo strings noted as
the anechoic per-player physics substrate, download deferred.

Normalized: **129 files** → `reference/strings/samples/`
(`{vln|vla|vc|cb|cb_nv}_{Note}{Octave}v{1|2}.flac`), pitch verified
per file by autocorrelation at candidate octaves (VSCO names sit one
octave below sounding pitch; HPS mislocked an octave up on
weak-fundamental low violin notes — ACF at candidate lags fixed it;
all files landed at consistent +1 octave, layers agreeing).

## Step 2 — research brief (2026-07-11)

`research/research-brief.md` (written inline; the PDF-gathering agent
was cut short by session limits — citations are to standard published
work, page-level details unverified). Core conclusions:

- Bowed steady state = Helmholtz motion → sawtooth bridge force →
  **exact harmonics ~1/n** shaped by fixed body formants (absorbable
  into calibrated per-note amplitude tables, like the piano
  soundboard).
- The ENSEMBLE percept is pitch spread (±5–15 c/player, slow wander),
  vibrato decorrelation, onset asynchrony (30–100 ms), power-wise
  summation with slow (0.1–2 Hz) level undulation, soft onsets, room
  in the release.

## ⛔ Engine-family gate — STOPPED, needs user decision

The modal engine cannot sustain a note. Three candidate families were
costed (research brief §"Candidate engine families"):

- **A. Waveguide per player (MSW × N)** — high cost, uncalibratable
  bow-control schedules from section recordings; right for a future
  SOLO bowed instrument, wrong for sections. Reject.
- **B. Sustained stochastic harmonic bank (RECOMMENDED)** — the modal
  voice + three additions: (i) sustained (non-decaying) envelope with
  measured rise/undulation/two-stage release, (ii) per-partial slow
  random FM/AM (~±5–10 c, 0.1–3 Hz) for ensemble spread, (iii) shared
  vibrato LFO with per-partial AM coupling. Reuses ~80 % of the voice
  (rotators, noise bands, salience pruning); CPU same order as a
  piano voice. Calibration plan drafted (harmonic table, envelope
  spectrum, linewidth-vs-n for detune spread, bow-noise floor).
  Benchmark needs one new metric family: modulation-spectrum energy
  (0.1–5 Hz) per band — plain LSD can't hear "shimmer realism".
- **C. Spectral-frame wavetable** — a disguised sample player; against
  the bank's no-samples rule. Reject.

Family B is a real engine addition (Rust `voice`/`stream` + Python
reference implementation + schema), not a config tweak — exactly what
the skill's stop-and-discuss rule is for.

**GATE RESOLVED (2026-07-11): user approved family B** ("Build family 2").
Everything below documents the build.

## Engine family 2 — sustained stochastic harmonic bank

Reference implementation `lab/sustained.py`; Rust `core/engine/src/
sustained.rs` behind `config.engine: "sustained"` (`AnyVoice` dispatch
in synth/stream; modal tables untouched — piano gate re-verified).
Per voice: harmonic bank with per-sample sine phase integration,
shared vibrato LFO (FM cents + AM dB), per-harmonic slow random
detune + AM (one-pole noise nodes at 64-sample hops, linearly
interpolated, ANALYTIC stationary gain — realized-std normalization
is unreproducible in a streaming engine), 12-band steady bow-noise bed
(own 0.2 s-window STFT calibration convention, geomspace 40–16000),
smoothstep rise → undulating sustain → two-stage release on note-off.

## Benchmark

`benchmark.py`: harm_db/4 (steady 16-harmonic table), lsd_sus/6
(floor −45), env_db/3 (1 s-smoothed macro envelope), mod_db/4
(modulation-spectrum energy 0.2–1/1–3/3–9 Hz — the shimmer metric LSD
cannot hear). rise/rel parametric errors are DIAGNOSTIC ONLY:
threshold-crossings on a stochastically undulating envelope are
realization-hostage. Null (perturbed self): 0.200 ± ~0.1 — NOTE it
under-estimates the honest floor (it shares the reference's
realization; every synth render is a different realization).
Eval grid: 102 section cells (vln/vla/vc/cb susvib), release_at =
measured reference sustain end.

## Score history

| iter | mean | change |
|---|---|---|
| 1 | 1.371 | baseline; catastrophic outliers (lsd 148) |
| 2 | 1.433* | smoothed marks + noise-bed convention fix (0.2 s windows, 12 bands to 16 kHz — 46 ms cannot resolve non-harmonic bins at low f0); *composite re-scoped, not comparable |
| 3 | 1.541* | ungated bed (−100 dB gate ate real top bands: per-bin medians run below −100 in this convention), rise/rel dropped from composite; lsd median 8.2→6.9 |
| 4 | 1.186 | modulation caps: bow-change notches measured as huge log-domain "depths" and the exponentiating renderer BLEW UP (cb peaks 1e5, found by sequential-render probe); und ≤3.5 dB, vib_am ≤2.5 dB + defensive ±12 dB exponent clamp (mirrored in Rust) |
| 5 | **1.006** (seeds 1.006/1.015/1.027) | benchmark-fitted ensemble depths: vib 3c + drift 4c (sweep; deeper vibrato double-smears the already-section-smeared harmonic peaks); analytic lp-noise gain. CURRENT |

## What failed / lessons

- **Exponentiating measured log-domain modulation is a blowup hazard**:
  articulation notches (bow changes) read as 20+ dB "depths". Cap at
  calibration AND clamp at render (both engines).
- **Absolute dB gates do not transfer between STFT conventions**: real
  content sits below −100 dB per-bin in 0.2 s windows.
- **Threshold-crossing envelope metrics fail on stochastic sustains** —
  score statistics (modulation spectrum), not realizations.
- **ACF pitch verification is octave-ambiguous DOWNWARD** (r(2T)≈r(T));
  prefer the highest candidate within 8 % of the best correlation.

## Gate 3 — ship (auto-decision 2026-07-11)

- Rust: sustained note_params parity ≤ 3.6e-15 over all sections ×
  velocities; engine tests pass; piano gate (`compare_engines.py`) OK;
  rhodes/jamblock smoke unchanged. **Rust eval 1.003** (median 0.982,
  worst 1.441) vs Python seeds 1.006/1.015/1.027 — inside the null.
  StreamSynth: sustained voices hold until note-off, then two-stage
  release and cull (smoke_stream_new.py).
- Known limitations: solo contrabass (no section exists in VSCO2-CE) —
  ships as solo-bass timbre; harm_db plateau ~5 dB partly reflects
  peak-vs-smear measurement circularity; room ambience of the reference
  is part of the calibrated noise bed (recording-chain-in-benchmark,
  đàn tranh precedent); vibrato/drift depths are benchmark-fitted, not
  measured (section recordings cannot separate them).
- Testbed: `strings / {vln,vla,vc,cb}` appear via params discovery.
