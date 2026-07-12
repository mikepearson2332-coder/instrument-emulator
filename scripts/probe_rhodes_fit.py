"""Check double-decay fits against the raw demod envelopes for one note.

  python scripts/probe_rhodes_fit.py E2v5 [n...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from lab.audio import find_onset, load_mono
from lab.notes import name_to_midi, midi_to_freq
from lab.partials import (envelope_window, fit_double_decay,
                          partial_envelope)
from instruments.rhodes.analysis import snap_harmonic
from lab.partials import find_partials

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "rhodes", "samples")

TIMES = [0.02, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "E2v5"
    ns = [int(a) for a in sys.argv[2:]] or [1, 2, 3, 4, 5, 7]
    note = name.split("v")[0]
    midi = name_to_midi(note)
    x, sr = load_mono(os.path.join(SAMPLES, f"{name}.flac"))
    xo = x[find_onset(x, sr):]
    peak_abs = float(np.max(np.abs(x)))
    f0_fit, _B, raw = find_partials(xo, sr, midi_to_freq(midi), max_partials=24)
    f0, partials = snap_harmonic(f0_fit, raw)
    print(f"{name}: f0={f0:.2f} peak_abs={peak_abs:.3f}")
    for n in ns:
        fn = n * f0
        win = envelope_window(sr, f0, f0=f0)
        t, env = partial_envelope(xo, sr, fn, hop=0.005, win_samples=win)
        _, envn = partial_envelope(xo, sr, fn + 0.5 * f0, hop=0.005,
                                   win_samples=win)
        noise_med = float(np.median(envn))
        valid = env > 2.0 * envn
        if n <= 2:
            valid = np.ones(len(env), bool)
        floor = max(-65.0, 20 * math.log10(
            2.5 * noise_med / (env.max() + 1e-20) + 1e-12))
        fit = fit_double_decay(t[valid], env[valid], floor_db=floor)
        print(f"\n n={n} f={fn:.1f} env_max={env.max():.4f} "
              f"argmax_t={t[np.argmax(env)]:.3f} noise={noise_med:.5f} "
              f"floor={floor:.1f}dB valid={valid.sum()}/{len(valid)}")
        if fit:
            print(f"   fit: a1={fit.a_fast:.4f} t1={fit.tau_fast:.3f} "
                  f"a2={fit.a_slow:.4f} t2={fit.tau_slow:.3f} "
                  f"rmse={fit.rmse_db:.2f}dB")
            print("   t     env(dB)  fit(dB)  diff")
            emax = env.max()
            for tc in TIMES:
                i = int(tc / 0.005)
                if i >= len(env):
                    break
                ev = 20 * math.log10(env[i] / emax + 1e-12)
                fv = fit.a_fast * math.exp(-tc / fit.tau_fast) \
                    + fit.a_slow * math.exp(-tc / max(fit.tau_slow, 1e-4))
                fd = 20 * math.log10(fv / emax + 1e-12)
                print(f"  {tc:5.2f} {ev:8.1f} {fd:8.1f} {fd-ev:+6.1f}")


if __name__ == "__main__":
    main()
