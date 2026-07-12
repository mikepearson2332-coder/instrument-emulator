"""Band-level + harmonic-level ref-vs-synth for one strings cell.

  python scripts/diag_strings_bands.py vla_C3v2
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.evaluate import _vel_map, cases_for
from instruments.strings.synth import Strings
from instruments.strings.analysis import envelope_marks, steady_spectrum, rms_env
from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram
from lab.notes import midi_to_freq


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "vla_C3v2"
    sec = name.split("_")[0]
    c = {q["name"]: q for q in cases_for(sec)}[name]
    vel = _vel_map(sec).get((c["midi"], c["layer"]), 90)
    ref, sr = load_mono(c["ref"])
    dur = min(len(ref) / sr, 12.0)
    synth = Strings(section=sec)
    y = synth.synth_note(c["midi"], vel, dur=dur,
                         release_at=min(c["release_at"] or dur * 0.75, dur - 0.1))
    r = ref[find_onset(ref, sr):]
    s = y[find_onset(y, sr):]
    n = min(len(r), len(s))
    r, s = r[:n], s[:n]
    er, es = rms_env(r, sr), rms_env(s, sr)
    m = min(len(er), len(es))
    mask = er[:m] > er.max() * 0.1
    gain = float(np.median(er[:m][mask]) / (np.median(es[:m][mask]) + 1e-20))
    s = s * gain

    r0, r1, _ = envelope_marks(r, sr)
    span = r1 - r0
    w0, w1 = r0 + 0.15 * span, r0 + 0.85 * span
    print(f"{name}: vel={vel} gain={20*np.log10(gain):+.1f}dB window={w0:.2f}..{w1:.2f}")

    tt, bs = band_spectrogram(s, sr)
    _, br = band_spectrogram(r, sr)
    sel = (tt >= w0) & (tt < w1)
    a = bs[:, sel].mean(axis=1)
    b = br[:, sel].mean(axis=1)
    bmax = b.max()
    edges = np.geomspace(25.0, 18000.0, 61)
    print("band(Hz)      ref     syn    diff")
    for i in range(60):
        if b[i] - bmax < -70 and a[i] - bmax < -70:
            continue
        print(f"{edges[i]:7.0f} {b[i]-bmax:8.1f} {a[i]-bmax:8.1f} "
              f"{a[i]-b[i]:+7.1f}")

    f0n = midi_to_freq(c["midi"])
    _, hr, _ = steady_spectrum(r, sr, f0n, w0, w1)
    _, hs, _ = steady_spectrum(s, sr, f0n, w0, w1)
    hs_m = {h["n"]: h["db"] for h in hs}
    print("\nharm  ref(dB)  syn(dB)")
    for h in hr[:16]:
        print(f"{h['n']:3d} {h['db']:8.1f} {hs_m.get(h['n'], float('nan')):8.1f}")


if __name__ == "__main__":
    main()
