import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from pianomodel.analysis import load_mono, find_onset

ROOT = os.path.join(os.path.dirname(__file__), "..")
for name in ["C7v1", "C7v6", "C7v11", "C7v16", "A7v6", "A7v16", "C8v6", "C8v16"]:
    x, sr = load_mono(os.path.join(ROOT, "reference", "samples", f"{name}.flac"))
    x = x[find_onset(x, sr):]
    seg = x[: int(0.4 * sr)]
    w = np.hanning(len(seg))
    nfft = 1 << 20
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    # fundamental search band: +/- 6% around nominal
    for nominal in [2093.0 if name.startswith("C7") else 3520.0 if name.startswith("A7") else 4186.0]:
        sel = (fax > nominal * 0.94) & (fax < nominal * 1.08)
        k = np.argmax(spec[sel])
        fpk = fax[sel][k]
        cents = 1200 * np.log2(fpk / nominal)
        print(f"{name}: peak {fpk:.1f} Hz  ({cents:+.1f} c vs ET)")
