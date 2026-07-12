"""Probe jRhodes3d reference samples: tuning, partial series, decay,
noise floor. Informs the rhodes analysis/benchmark design.

  python scripts/probe_rhodes.py [names...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from lab.audio import find_onset, load_mono
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import find_partials, fit_double_decay, partial_envelope

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "rhodes", "samples")

DEFAULT = ["F1v5", "F1v1", "A2v5", "A2v1", "B3v5", "B3v3", "B3v1",
           "F4v5", "F4v1", "E5v5", "A5v4", "C7v4"]


def probe(name: str):
    note = name.split("v")[0]
    path = os.path.join(SAMPLES, f"{name}.flac")
    x, sr = load_mono(path)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak = np.max(np.abs(x))
    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)

    # tail noise floor (last 5% of file) + pre-onset floor
    tail = x[int(len(x) * 0.97):]
    pre = x[: max(onset - int(0.005 * sr), 1)]
    tail_db = 20 * math.log10(np.sqrt((tail ** 2).mean()) / peak + 1e-12)
    pre_db = 20 * math.log10(np.sqrt((pre ** 2).mean() + 1e-20) / peak + 1e-12)

    f0, B, partials = find_partials(xo, sr, f0n, max_partials=24)
    dev = 1200 * math.log2(f0 / f0n)

    print(f"\n=== {name}  midi={midi} f0={f0:.2f} ({dev:+.1f}c) "
          f"B={B:.2e} partials={len(partials)} "
          f"len={len(x)/sr:.1f}s onset={onset/sr*1000:.0f}ms "
          f"peak={peak:.3f} tail={tail_db:.0f}dB pre={pre_db:.0f}dB")

    amps = np.array([p["amp"] for p in partials])
    a0 = amps.max() + 1e-20
    for p in partials[:10]:
        ratio = p["freq"] / f0
        cents_harm = 1200 * math.log2(ratio / round(ratio)) if ratio > 0.5 else 0
        t, env = partial_envelope(xo, sr, p["freq"], hop=0.01)
        fit = fit_double_decay(t, env, floor_db=-60.0)
        if fit:
            fs = (f"t1={fit.tau_fast:6.3f} t2={fit.tau_slow:6.2f} "
                  f"a1/a2={fit.a_fast/(fit.a_slow+1e-20):5.1f}")
        else:
            fs = "fit=None"
        print(f"  n={p['n']:2d} f={p['freq']:8.1f} r={ratio:6.3f} "
              f"({cents_harm:+5.1f}c vs harm) "
              f"amp={20*math.log10(p['amp']/a0+1e-12):6.1f}dB {fs}")


def main():
    names = sys.argv[1:] or DEFAULT
    for n in names:
        try:
            probe(n)
        except Exception as e:
            print(f"{n}: FAILED {e}")


if __name__ == "__main__":
    main()
