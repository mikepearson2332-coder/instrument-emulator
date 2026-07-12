"""Probe VSCO section sustains: envelope shape, harmonic table, vibrato,
ensemble linewidth, bow-noise floor. Grounds the family-2 model.

  python scripts/probe_strings.py [vln_A3v1 ...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from scipy.signal import get_window

from lab.audio import load_mono
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import partial_envelope

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "strings", "samples")

DEFAULT = ["vln_G3v1", "vln_G3v2", "vln_A4v1", "vln_D6v1",
           "vla_C3v1", "vc_C2v1", "vc_A3v2", "cb_E1v1"]


def rms_env(x, sr, hop_s=0.01):
    hop = int(hop_s * sr)
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def probe(name):
    note = name.split("_")[1].split("v")[0]
    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)
    x, sr = load_mono(os.path.join(SAMPLES, f"{name}.flac"))
    env = rms_env(x, sr)
    pk = env.max()
    edb = 20 * np.log10(env / pk + 1e-12)
    t = np.arange(len(env)) * 0.01

    # rise: first crossing of -20 dB to first crossing of -3 dB
    above20 = np.nonzero(edb > -20)[0]
    above3 = np.nonzero(edb > -3)[0]
    t_on = t[above20[0]] if len(above20) else 0
    rise = t[above3[0]] - t_on if len(above3) else float("nan")

    # sustain region: between first -3 dB and last -6 dB crossing
    last6 = np.nonzero(edb > -6)[0]
    s0, s1 = (above3[0], last6[-1]) if len(above3) and len(last6) else (0, len(t) - 1)
    sus = edb[s0:s1]
    und_db = float(np.std(sus)) if len(sus) > 10 else float("nan")
    # undulation rate: spectrum of sustain envelope, 0.1-5 Hz peak
    und_hz = float("nan")
    if len(sus) > 100:
        d = sus - sus.mean()
        spec = np.abs(np.fft.rfft(d * np.hanning(len(d))))
        fr_ = np.fft.rfftfreq(len(d), 0.01)
        sel = (fr_ > 0.15) & (fr_ < 5.0)
        if sel.any():
            und_hz = float(fr_[sel][np.argmax(spec[sel])])

    # release: from last -6 dB, time to -26 dB
    rel = float("nan")
    tail = edb[s1:]
    below = np.nonzero(tail < -26)[0]
    if len(below):
        rel = below[0] * 0.01

    # steady spectrum: middle 50% window
    n0, n1 = int(len(x) * 0.3), int(len(x) * 0.8)
    seg = x[n0:n1]
    w = get_window("hann", len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg))))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    binw = fax[1]

    # find true f0 near nominal (ensemble center)
    lo, hi = int(f0n * 0.94 / binw), int(f0n * 1.06 / binw)
    k0 = lo + int(np.argmax(spec[lo:hi]))
    f0 = k0 * binw

    print(f"\n=== {name} f0={f0:.1f} len={len(x)/sr:.1f}s rise(-20..-3dB)="
          f"{rise*1000:.0f}ms und={und_db:.2f}dB@{und_hz:.2f}Hz "
          f"rel(-6..-26dB)={rel*1000:.0f}ms")
    print("  n    f(Hz)   amp(dB)  width(c)  noise_mid(dB)  vib")
    amax = None
    for n in range(1, 25):
        fc = n * f0
        if fc > 16000 or fc > fax[-1]:
            break
        lo = int((fc - 0.35 * f0) / binw)
        hi = int((fc + 0.35 * f0) / binw)
        if hi <= lo + 2:
            break
        k = lo + int(np.argmax(spec[lo:hi]))
        pkv = spec[k]
        if amax is None:
            amax = pkv
        # -6 dB linewidth in cents
        half = pkv / 2
        kl = k
        while kl > lo and spec[kl] > half:
            kl -= 1
        kr = k
        while kr < hi - 1 and spec[kr] > half:
            kr += 1
        width_c = 1200 * math.log2((kr * binw) / (kl * binw)) if kl > 0 else 0
        # inter-harmonic noise floor midway up
        mlo = int((fc + 0.4 * f0) / binw)
        mhi = int((fc + 0.6 * f0) / binw)
        nz = np.median(spec[mlo:mhi]) if mhi > mlo else 0
        # vibrato of this harmonic (FM): demod freq wobble
        vib = ""
        if n in (2, 3) and len(x) / sr > 4:
            seg2 = x[n0:n0 + 3 * sr]
            tt, e2 = partial_envelope(seg2, sr, fc, hop=0.005,
                                      win_samples=int(sr / (0.5 * f0)))
            d = 20 * np.log10(e2 + 1e-12)
            d = d - d.mean()
            sp2 = np.abs(np.fft.rfft(d * np.hanning(len(d))))
            fr2 = np.fft.rfftfreq(len(d), 0.005)
            sel2 = (fr2 > 3.0) & (fr2 < 9.0)
            if sel2.any():
                kv = np.argmax(sp2[sel2])
                vib = f"AM@{fr2[sel2][kv]:.1f}Hz"
        print(f"  {n:2d} {fc:8.1f} {20*math.log10(pkv/amax+1e-12):8.1f} "
              f"{width_c:8.1f} {20*math.log10(nz/amax+1e-12):10.1f}  {vib}")


if __name__ == "__main__":
    for n in sys.argv[1:] or DEFAULT:
        try:
            probe(n)
        except Exception as e:
            print(f"{n}: FAILED {e}")
