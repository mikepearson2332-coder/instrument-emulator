"""Parity check: Rust engine vs Python reference implementation.

1. note_params (deterministic interpolation) must agree to float precision
   across on-grid and off-grid keys/velocities.
2. Rendered waveforms are compared statistically (RMS envelope in dB over
   250 ms windows) — realizations differ by design (different PRNG), but
   levels and decay must track closely.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.piano.synth import Piano as PianoPy
from instruments.piano.synth_rs import Piano as PianoRs


def cmp_val(a, b, path, worst):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        denom = max(abs(a), abs(b), 1e-12)
        rel = abs(a - b) / denom
        if rel > worst[0]:
            worst[0], worst[1] = rel, path
        return
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: len {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            cmp_val(x, y, f"{path}[{i}]", worst)
        return
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys {set(a) ^ set(b)}"
        for k in a:
            cmp_val(a[k], b[k], f"{path}.{k}", worst)
        return
    assert a == b, f"{path}: {a!r} != {b!r}"


def main():
    py = PianoPy()
    rs = PianoRs()

    # --- note_params parity: on-grid, off-grid, extremes, layer boundaries
    midis = [21, 22, 25, 33, 40, 41, 47, 60, 61, 75, 76, 88, 89, 100, 107, 108]
    vels = [1, 8, 20, 48, 60, 88, 100, 127]
    worst = [0.0, ""]
    for m in midis:
        for v in vels:
            a = py.note_params(m, v)
            b = rs.note_params(m, v)
            cmp_val(a, b, f"m{m}v{v}", worst)
    print(f"note_params: {len(midis) * len(vels)} combos, "
          f"max rel diff {worst[0]:.3e} at {worst[1] or '-'}")
    assert worst[0] < 1e-9, "note_params parity FAILED"

    # --- waveform level tracking. Random phases (esp. unison beating) move
    # energy between windows legitimately, so compare against a null baseline:
    # the same Python engine with a different seed. The Rust engine passes if
    # its deviation is comparable to the Python seed-to-seed deviation.
    # Null spread is wide (up to ~5 dB) for low keys where the unison beat
    # period exceeds the render length — the random beat phase then sets the
    # fundamental's level for the whole note. See DEVLOG (phase-2 port).
    print("\nRMS envelope deviation vs Python ref (250 ms windows, dB):")
    print("            rust    null(py, max over 5 seeds)")
    py_nulls = [PianoPy(seed=s) for s in (4321, 777, 2024, 42, 31337)]
    hop = int(0.25 * py.sr)

    def env_dev(ya, yb):
        rows = []
        for s in range(0, len(ya) - hop, hop):
            ra = np.sqrt(np.mean(ya[s:s + hop] ** 2)) + 1e-12
            rb = np.sqrt(np.mean(yb[s:s + hop] ** 2)) + 1e-12
            rows.append(20 * np.log10(ra / rb))
        return float(np.max(np.abs(rows)))

    bad = 0
    for m, v in [(21, 88), (36, 48), (60, 88), (60, 8), (84, 127), (105, 88)]:
        ya = py.synth_note(m, v, dur=3.0)
        yb = rs.synth_note(m, v, dur=3.0)
        d_rs = env_dev(ya, yb)
        d_null = max(env_dev(ya, p.synth_note(m, v, dur=3.0)) for p in py_nulls)
        # Catastrophic-breakage gate only. Beat-phase realization alone can
        # move a 250 ms window by up to ~5.4 dB (2-string beat depth 0.3,
        # beat period >> render for low keys; 10-seed py-vs-py null reached
        # 4.7 dB). Fine-grained fidelity is judged by the 120-note eval score,
        # where phase luck averages out.
        limit = max(6.0, 1.3 * d_null)
        flag = "  <-- FAIL" if d_rs > limit else ""
        if d_rs > limit:
            bad += 1
        print(f"  m{m:3d} v{v:3d}: {d_rs:5.2f}   {d_null:5.2f}{flag}")
    if bad:
        print(f"\n{bad} notes exceed the null-calibrated limit")
        sys.exit(1)
    print("\nOK")


if __name__ == "__main__":
    main()
