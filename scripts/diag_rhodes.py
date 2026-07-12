"""Diagnose one rhodes eval cell: RMS env + per-harmonic envelopes,
synth vs reference, at matched gain.

  python scripts/diag_rhodes.py E2v5 [E2v4 ...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from lab.audio import find_onset, load_mono
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import partial_envelope
from instruments.rhodes.calibrate import LAYER_TO_VEL
from instruments.rhodes.synth import Rhodes

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "rhodes", "samples")

CHECK_T = [0.01, 0.03, 0.08, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0]


def rms_env(x, sr, hop_s=0.005):
    hop = int(hop_s * sr)
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def diag(name):
    note, layer = name.split("v")
    midi = name_to_midi(note)
    vel = LAYER_TO_VEL[int(layer)]
    ref, sr = load_mono(os.path.join(SAMPLES, f"{name}.flac"))
    ref = ref[find_onset(ref, sr):]
    synth = Rhodes()
    y = synth.synth_note(midi, vel, dur=min(len(ref) / sr, 8.0))
    y = y[find_onset(y, sr):]
    n = min(len(y), len(ref))
    y, ref = y[:n], ref[:n]
    es, er = rms_env(y, sr), rms_env(ref, sr)
    gain = er.max() / es.max()
    y = y * gain
    es = es * gain

    print(f"\n=== {name} midi={midi} vel={vel} gain={20*math.log10(gain):+.1f}dB")
    print("t(s)    ref_rms(dB)  syn_rms(dB)  diff")
    rmax = er.max()
    for tc in CHECK_T:
        i = int(tc / 0.005)
        if i >= len(er):
            break
        rd = 20 * math.log10(er[i] / rmax + 1e-12)
        sd = 20 * math.log10(es[i] / rmax + 1e-12)
        print(f"{tc:5.2f}   {rd:8.1f}    {sd:8.1f}   {sd-rd:+6.1f}")

    f0 = midi_to_freq(midi)
    p = synth.note_params(midi, vel)
    print(f"table f0={p['f0']:.2f}  partials={len(p['partials'])}")
    print("harm  freq    ref@t: " + "  ".join(f"{t:４.2f}" if False else f"{t:5.2f}" for t in [0.05, 0.5, 2.0]) + "   syn same   (dB rel ref peak)")
    for prt in p["partials"][:8]:
        fn = prt["n"] * p["f0"]
        tr, envr = partial_envelope(ref, sr, fn, hop=0.01)
        ts, envs = partial_envelope(y, sr, fn, hop=0.01)
        def at(env, t):
            i = int(t / 0.01)
            return 20 * math.log10(env[i] / rmax + 1e-12) if i < len(env) else float("nan")
        rvals = [at(envr, t) for t in [0.05, 0.5, 2.0]]
        svals = [at(envs, t) for t in [0.05, 0.5, 2.0]]
        print(f"n={prt['n']:2d} {fn:7.1f}  "
              + " ".join(f"{v:6.1f}" for v in rvals) + "   "
              + " ".join(f"{v:6.1f}" for v in svals)
              + f"   a1={prt['a1']:.3f} t1={prt['t1']:.2f} a2={prt['a2']:.3f} t2={prt['t2']:.2f}")


if __name__ == "__main__":
    for name in sys.argv[1:] or ["E2v5"]:
        diag(name)
