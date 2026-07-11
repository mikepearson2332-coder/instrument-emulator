# Woodblock

First non-piano instrument in the bank; smallest possible end-to-end
exercise of the `instrument-dev` pipeline and the generic modal engine
path. Developed 2026-07-11 in `--auto` mode (gate decisions logged in
`instruments/woodblock/DEVLOG.md`).

## Sound model

A woodblock hit is over in ~300 ms and decomposes into:

- **2–3 modes** at non-integer frequency ratios (dominant ≈ 1.37 kHz ≈ F6
  for the reference block, secondary ≈ 3.1 kHz on harder hits, a weak
  ~290 Hz body knock on soft hits), each a decaying sinusoid with a
  two-stage envelope: fast structural decay tau ≈ 7–10 ms + slow
  after-ring/room tail tau ≈ 70 ms. Mode frequencies are stored as
  explicit ratios `fr` to the key f0 (`freq = fr * f0`) — the engine's
  non-string mode series (the piano's `n·f0·√(1+Bn²)` does not apply).
- **Broadband click**: the per-band thump machinery, with a per-band decay
  time (`config.thump_tau_bands`, ~5 ms treble to ~50 ms mids) measured
  from the reference — the click's tail is early room response and decays
  5–10× slower than the piano's fixed 20 ms thump.
- **No room bed**: the VCSL room's early reflections measured into the
  noise model made the block read as a "toy snare" when played dry
  (user-ear finding). The bed is dropped and click decays are capped at
  20 ms — the model ships the instrument, not the room.
- **1.5 ms onset ramp** on all modes (contact time) — without it the
  discontinuous sine onsets splatter −57 dB of broadband into every band.
- **No dampers** (`release_fade_s: null`): note-off is a no-op, like the
  real instrument.

One calibrated block is mapped across the keyboard by transposing f0 from
the anchor key (MIDI 89); mode ratios, decays, and noise profiles are
fixed, matching standard practice for mapped percussion.

## Calibration

`analysis.py` peak-picks modes with a 10% minimum separation (a tau = 8 ms
mode is a ~100 Hz-wide resonance — closer picks are slices of one mode
group), demodulates each at 1 ms hop with a ~6 ms window, and fits the
robust piecewise-dB double decay with amplitude caps anchored to the
measured envelope peak (the piano's t=0 extrapolation is explosive when
tau ≈ anchor time). `calibrate.py` clusters modes across the four dynamic
layers (pp/mp/f/ff → velocities 20/56/96/127) into stable indices for the
key/velocity interpolators. Table: `params/block.json`, 3 KiB.

## Benchmark

Woodblock-specific metric weights (attack + short-time envelope dominate;
see `benchmark.py`): attack_db (1 ms RMS, 50 ms), env_db (2 ms, 350 ms),
mode_cents, fast-decay log-error, band-LSD 0–0.15 s / 0.15–0.4 s at
floor −35 dB (pp takes bottom out at the recording noise floor), centroid
ratio. Composite lower = better.

- **Take-vs-take null** (round robins vs primary takes): mean 1.315,
  std 0.65 — strike-to-strike variability is large (dominant mode wanders
  ~1%, pp attack up to 26 dB between takes).
- **Python model**: 1.362 (Rust 1.290) — at the take null. The roomy
  variant of the model scored 1.012, but the score is measured against
  the roomy recording; the shipped dry model deliberately trades score
  for instrument realism (see DEVLOG iter 6).
- note_params parity Python↔Rust: ≤ 1.9e-16 relative.

## Quality

Salience pruning works but there is little to prune (≤3 modes): full
1.028 = p2 1.028, p1 1.073. `noise: false` is catastrophic (1.89) — the
click IS the instrument; never drop noise for percussion voices.

## Known limitations

- Single block: no round-robin variation model (each strike in reality
  shifts the dominant mode ±1% and the attack several dB; a future
  per-note-on jitter of f0/amp within the measured take spread would be
  cheap and realistic).
- `wood_click2`/`wood_click3` takes (different block / rim strikes) were
  excluded; a multi-block "temple blocks" variant could map them to
  different keys.
- The reference's pp layers have ~30 dB SNR; sub-noise-floor detail is
  unknowable from this source.
