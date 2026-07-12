"""Measure per-instrument rendered loudness (A-weighted RMS, vel 96)
across each table's register; propose config.gain_db values anchored to
the piano.

  python scripts/measure_bank_loudness.py
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")

VEL = 96.0
SR = 44100

INSTRUMENTS = [
    ("piano", "instruments/piano/params/grand.json", None),
    ("woodblock", "instruments/woodblock/params/block.json", None),
    ("vibraphone", None, "auto"),  # find params file
    ("koto", "instruments/koto/params/tranh.json", None),
    ("rhodes", "instruments/rhodes/params/mk1.json", None),
    ("jamblock", "instruments/jamblock/params/jam.json", None),
    ("strings-vln", "instruments/strings/params/vln.json", None),
    ("strings-vla", "instruments/strings/params/vla.json", None),
    ("strings-vc", "instruments/strings/params/vc.json", None),
    ("strings-cb", "instruments/strings/params/cb.json", None),
]


def a_weight(f):
    f2 = f * f
    num = (12194.0 ** 2) * f2 * f2
    den = ((f2 + 20.6 ** 2)
           * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2))
           * (f2 + 12194.0 ** 2))
    return num / (den + 1e-30) / 0.7943


def aw_rms_db(x, sr):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / sr)
    w = a_weight(f)
    p = np.sum(np.abs(X * w) ** 2) / (len(x) ** 2)
    return 10 * math.log10(2 * p + 1e-20)


def probe_midis(path):
    with open(os.path.join(ROOT, path)) as fh:
        t = json.load(fh)
    ms = sorted(k["midi"] for k in t["keys"])
    return [ms[len(ms) // 4], ms[len(ms) // 2], ms[3 * len(ms) // 4]], t


def render(path, midi, sustained):
    sys.path.insert(0, os.path.join(ROOT, "core", "dist"))
    import instrument_core
    p = instrument_core.Piano(os.path.join(ROOT, path), SR, 1234)
    if sustained:
        buf = p.synth_note(midi, VEL, 2.5, 1.8, False)
    else:
        buf = p.synth_note(midi, VEL, 1.5, None, False)
    return np.frombuffer(buf, dtype=np.float64)


def main():
    rows = []
    for name, path, mode in INSTRUMENTS:
        if path is None:
            import glob
            hits = glob.glob(os.path.join(ROOT, "instruments", name, "params", "*.json"))
            if not hits:
                continue
            path = os.path.relpath(hits[0], ROOT)
        midis, t = probe_midis(path)
        sustained = (t.get("config") or {}).get("engine") == "sustained"
        levels = []
        for m in midis:
            y = render(path, m, sustained)
            levels.append(aw_rms_db(y, SR))
        med = float(np.median(levels))
        rows.append((name, path, med, levels))
    anchor = next(r[2] for r in rows if r[0] == "piano")
    print(f"{'instrument':14s} {'AW-RMS(dB)':>10s}  {'per-note':30s} gain_db->piano")
    for name, path, med, levels in rows:
        print(f"{name:14s} {med:10.1f}  {str([round(v,1) for v in levels]):30s} "
              f"{anchor - med:+6.1f}")


if __name__ == "__main__":
    main()
