"""Probe jam block raw takes: dominant modes, decays, ring time.

  python scripts/probe_jamblock.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import soundfile as sf
from scipy.signal import find_peaks

from lab.audio import find_onset
from lab.partials import fit_double_decay, partial_envelope

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "reference", "jamblock", "raw")


def probe(path):
    x, sr = sf.read(path, always_2d=True)
    x = x.mean(axis=1)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak = np.max(np.abs(xo)) + 1e-20

    # ring time to -40 dB
    hop = int(0.002 * sr)
    m = len(xo) // hop
    env = np.sqrt((xo[: m * hop].reshape(m, hop) ** 2).mean(axis=1))
    edb = 20 * np.log10(env / (env.max() + 1e-20) + 1e-12)
    below = np.nonzero(edb < -40)[0]
    ring40 = below[0] * 0.002 if len(below) else m * 0.002

    seg = xo[: int(min(0.4, len(xo) / sr) * sr)]
    w = np.hanning(len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg) * 4)))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    sel = (freqs > 150) & (freqs < 12000)
    sp = spec[sel]
    fq = freqs[sel]
    pk, _ = find_peaks(sp, height=sp.max() * 10 ** (-30 / 20),
                       distance=int(60 / (fq[1] - fq[0])))
    order = np.argsort(sp[pk])[::-1][:6]
    print(f"\n=== {os.path.basename(path)}  sr={sr} len={len(x)/sr:.2f}s "
          f"onset={onset/sr*1000:.0f}ms ring40={ring40*1000:.0f}ms")
    f_dom = fq[pk[order[0]]]
    for i in order:
        f = fq[pk[i]]
        db = 20 * math.log10(sp[pk[i]] / sp[pk[order[0]]] + 1e-12)
        t, e = partial_envelope(xo, sr, f, hop=0.001, bw=120)
        fit = fit_double_decay(t, e, floor_db=-45.0)
        tau = f"tau={fit.tau_fast*1000:.0f}ms" if fit else "tau=?"
        print(f"  f={f:7.1f}  {db:6.1f}dB  r={f/f_dom:5.2f}  {tau}")


def main():
    for fn in sorted(os.listdir(RAW)):
        if fn.endswith((".ogg", ".mp3")):
            try:
                probe(os.path.join(RAW, fn))
            except Exception as e:
                print(f"{fn}: FAILED {e}")


if __name__ == "__main__":
    main()
