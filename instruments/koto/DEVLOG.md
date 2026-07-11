# Development log — koto (long-zither) model

Run in `--auto` mode (2026-07-11): checkpoint gates are logged decisions.

## Gate 1 — reference acquisition (auto-decision 2026-07-11)

**No license-clean true-koto multisample exists** (full search table in
SOURCES.md). The decisive rejections: Unreal Instruments' excellent
13-string koto set prohibits unauthorized modification/processing (加工)
of the sound data — fails the analysis/derivatives bar; the Musical
Artifacts sf2s sit behind an active bot-check and have unverifiable
uploader-declared licenses; FluidR3 (MIT) has a real koto but only 3
truncated looped zones.

**Decision: calibrate on the VCSL Đàn Tranh (CC0)** — the koto's closest
relative (same movable-bridge East-Asian long-zither family), 16 sampled
pitches × mf/f/ff from the already-vetted VCSL collection. Shipped as
`koto / tranh`, substitution documented everywhere user-facing. If a
licensed koto set appears, only recalibration is needed.

Normalization audit (HPS pitch detection): VCSL names are one octave
below sounding pitch; `B1_mf_1` actually sounds B3; the `C#2_*` group
sounds C#4 and `C#3_*` is the same string in a second session retuned
+35 c (movable bridges!). Final grid: **14 keys B2–B5 × mf/f/ff**
(B2 lacks mf), 3 alternate takes kept as the benchmark null set.

## Gate 2 — benchmark design (auto-decision 2026-07-11)

Metrics: partial_cents (12 partials), b_logerr, decay_logerr (slow tau,
6 partials), env_db (5 ms hop / 2.5 s, ref-masked −50 dB), attack_db
(1 ms / 80 ms), band-LSD 0–0.3 / 0.3–1.5 s at floor −35 dB, level-gated
centroid (150 ms). Take-vs-take null: **1.754** (std 0.20; dominated by
the C#4 cross-session pair — 38 c retuning — real instrument variance).
Seed-to-seed: 1.132 / 1.126 (±0.01).

## Score history

| iter | mean | change |
|---|---|---|
| 1 | **1.132** | piano-family pipeline (find_partials series, per-partial double decay, per-band pluck click with measured taus, bed) — already below the take null. CURRENT |
| 2 | 1.262 | ✗ dual-polarization beating, random phase (dips land on the attack — unphysical) |
| 3 | 1.238 | ✗ polarization beating, in-phase start + t=0 normalization — still loses: the benchmark's tau-refit and LSD are dip-sensitive on both sides |

**Polarization beating recorded as the losing candidate** (kept in
`lab/modal.py` behind `pol_beat_*` config, off for this table). The
reference envelopes genuinely show dip-and-recover (e.g. B4v2: −16 dB at
0.2 s, flat to 0.5 s), so the physics is right, but a fixed-heuristic
depth/rate distribution scores worse than a plain render; revisit only
with per-note measured beat parameters.

## Gate 3 — ship (auto-decision 2026-07-11)

- Python **1.132** (seeds ±0.01, take null 1.754), Rust **1.114** —
  inside the null. note_params parity ≤ 1.8e-15.
- Quality sweep (v2 subset): full 1.090 · p16 1.092 (free) · p10 1.120 ·
  p6 1.240 · no-noise 1.303 (the pluck click matters).
- Palm-damp release verified via StreamSynth (−21 dB in 0.25 s,
  τ = 0.12 s config).
- Demos: `output/demo/koto/` A/B (B3 f, F#4 ff, C#5 mf, B2 f) + phrase.
- Testbed: appears as `koto / tranh`.

## Known weaknesses / next steps

1. Worst cells are B5 (2.2 s takes — decay fits extrapolate) and B3v1
   (the mislabeled-origin mf take).
2. Pluck-position comb is fitted per layer, not modeled — no continuous
   brightness control between layers beyond interpolation.
3. True-koto timbre: sanity-listen vs FluidR3's koto zones shows the
   tranh is brighter with longer ring (steel vs tetron strings) —
   acceptable as a family model; swap references when licensing allows.

## Data flow

```
reference/koto/raw/tranh/*.wav        (VCSL CC0, gitignored)
  └─ python -m instruments.koto.normalize_raw → reference/koto/samples/*.flac
       └─ python -m instruments.koto.analyze → reference/koto/analysis/*.json
            └─ python -m instruments.koto.calibrate → instruments/koto/params/tranh.json
                 └─ lab/modal.py (ModalSynth) ← instruments/koto/synth.py
                 └─ core/engine ← instruments/koto/synth_rs.py
                      └─ python -m instruments.koto.evaluate [--null|--engine=rust]
```
