import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from pianomodel.analysis import load_mono, find_onset

ROOT = os.path.join(os.path.dirname(__file__), "..")
for name in ["C8v6", "A7v16", "C7v6", "F#6v16", "C6v16"]:
    x, sr = load_mono(os.path.join(ROOT, "reference", "samples", f"{name}.flac"))
    x = x[find_onset(x, sr):]
    seg = x[int(1.0 * sr): int(2.5 * sr)]
    if len(seg) < sr:
        seg = x[int(0.8 * sr):]
    w = np.hanning(len(seg))
    spec = 20 * np.log10(np.abs(np.fft.rfft(seg * w)) + 1e-12)
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    sel = (fax > 80) & (fax < 3000)
    s, f = spec[sel], fax[sel]
    # peak picking: local maxima 12 dB above local median
    from scipy.ndimage import median_filter, maximum_filter
    locmed = median_filter(s, 201)
    ismax = (s == maximum_filter(s, 25)) & (s > locmed + 12)
    idx = np.nonzero(ismax)[0]
    idx = idx[np.argsort(-s[idx])][:12]
    idx = idx[np.argsort(f[idx])]
    print(name, " ".join(f"{f[i]:.0f}" for i in idx))
