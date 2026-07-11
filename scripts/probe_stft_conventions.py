"""Pin down the exact scipy.signal.stft conventions used by Piano._band_metric,
so the Rust port of the band metric can reproduce them. Prints reference values
for a deterministic input; core/engine has a unit test against these numbers."""

import numpy as np
from scipy.signal import stft, butter, sosfilt

sr = 48000
nper = int(0.046 * sr)
nover = nper - int(0.010 * sr)

# deterministic pseudo-signal
x = np.sin(2 * np.pi * 997.0 * np.arange(sr) / sr) * np.exp(-np.arange(sr) / (0.3 * sr))

f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
A = np.abs(Z)
print(f"nper={nper} nover={nover} hop={nper-nover}")
print(f"n_freq_bins={len(f)}  f[0:3]={f[0:3]}  f[-1]={f[-1]}")
print(f"n_frames={len(t)}  t[0:4]={t[0:4]}")
print(f"frames with t<0.12: {int((t < 0.12).sum())}")
print(f"A[100,0]={A[100,0]:.12e}  A[46,5]={A[46,5]:.12e}  A[0,0]={A[0,0]:.12e}")

# band medians as _band_metric computes them (band 40*200**(i/10))
edges = np.geomspace(40.0, 8000.0, 11)
for band in (4, 9):
    sel = (f >= edges[band]) & (f < edges[band + 1])
    med = np.median(A[sel], axis=0)
    steady = float(np.median(med))
    attack = float(med[t < 0.12].max())
    print(f"band{band}: n_bins={int(sel.sum())} steady={steady:.12e} attack={attack:.12e}")

# butter SOS reference for band 0 and band 9
for band in (0, 9):
    lo, hi = edges[band], edges[band + 1]
    sos = butter(4, [lo, min(hi, sr / 2 * 0.98)], btype="bandpass", fs=sr, output="sos")
    print(f"butter band{band} sos shape={sos.shape}")
    for row in sos:
        print("  " + " ".join(f"{v:.15e}" for v in row))

# sosfilt reference on a small deterministic input
xs = np.zeros(16); xs[0] = 1.0  # impulse
sos0 = butter(4, [edges[0], edges[1]], btype="bandpass", fs=sr, output="sos")
ys = sosfilt(sos0, xs)
print("impulse response head:", " ".join(f"{v:.15e}" for v in ys[:6]))
