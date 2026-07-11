"""Probe: woodblock mode structure — spectral peaks + demodulated decays.

For each reference file: FFT peak-pick (no series assumption), then complex
demodulation at each candidate with a short window, piecewise-dB decay fit.
Prints freq / level / tau to decide how many modes the model needs.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from lab.audio import load_mono, find_onset
from lab.partials import parabolic_peak, partial_envelope, fit_double_decay

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "woodblock", "samples")


def peaks_above_floor(x, sr, fmin=250.0, fmax=12000.0, n_max=14):
    onset = find_onset(x, sr)
    seg = x[onset:onset + int(0.35 * sr)]
    w = np.hanning(len(seg))
    nfft = 1 << 16
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    binw = fax[1]
    out = []
    s = spec.copy()
    s[(fax < fmin) | (fax > fmax)] = 0
    smax = s.max()
    for _ in range(n_max):
        k = int(np.argmax(s))
        if s[k] < smax * 10 ** (-35 / 20):
            break
        d, pk = parabolic_peak(spec, k)
        out.append((float((k + d) * binw), float(20 * np.log10(pk / smax + 1e-12))))
        lo, hi = max(0, k - int(45 / binw)), k + int(45 / binw)
        s[lo:hi] = 0
    return sorted(out)


def main():
    for name in ["F6v1", "F6v2", "F6v3", "F6v4", "F6v1_alt1", "F6v3_alt1"]:
        p = os.path.join(SAMPLES, f"{name}.flac")
        x, sr = load_mono(p)
        onset = find_onset(x, sr)
        xo = x[onset:]
        print(f"\n=== {name} (sr={sr}, {len(xo)/sr:.2f}s after onset)")
        for freq, db in peaks_above_floor(xo, sr):
            # short window (~6 ms) resolves fast decay; 2 ms hop
            t, env = partial_envelope(xo, sr, freq, hop=0.002,
                                      win_samples=int(0.006 * sr))
            fit = fit_double_decay(t, env, floor_db=-55.0)
            if fit is None:
                print(f"  {freq:8.1f} Hz  {db:6.1f} dB   (no fit)")
                continue
            print(f"  {freq:8.1f} Hz  {db:6.1f} dB   "
                  f"a1={fit.a_fast:.4f} t1={fit.tau_fast*1000:6.1f}ms  "
                  f"a2={fit.a_slow:.4f} t2={fit.tau_slow*1000:7.1f}ms  "
                  f"rmse={fit.rmse_db:.1f}dB")


if __name__ == "__main__":
    main()
