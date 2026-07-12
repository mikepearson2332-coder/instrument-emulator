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
the skill's stop-and-discuss rule is for. **Next action (user):**
approve family B (or redirect), then: envelope/modulation analysis →
calibrate vln/vla/vc/cb → benchmark with modulation metrics → Rust
engine family 2 → ship.
