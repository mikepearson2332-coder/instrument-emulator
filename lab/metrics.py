"""Generic benchmark metrics (instrument-agnostic).

Per-instrument benchmark modules build their `compare()` from these and add
instrument-specific structure (e.g. the piano adds partial matching and
decay comparison); composite-score weights are always per-instrument."""

from __future__ import annotations

import numpy as np
from scipy.signal import stft

STFT_WIN_S = 0.046
STFT_HOP_S = 0.010


def band_spectrogram(x: np.ndarray, sr: int, n_bands: int = 60,
                     fmin: float = 25.0, fmax: float = 18000.0):
    """Log-frequency band energies over time, in dB (benchmark metric)."""
    nper = int(STFT_WIN_S * sr)
    nover = nper - int(STFT_HOP_S * sr)
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
    P = np.abs(Z) ** 2
    edges = np.geomspace(fmin, min(fmax, sr / 2 * 0.98), n_bands + 1)
    bands = np.zeros((n_bands, P.shape[1]))
    for i in range(n_bands):
        sel = (f >= edges[i]) & (f < edges[i + 1])
        if sel.any():
            bands[i] = P[sel].sum(axis=0)
    return t, 10 * np.log10(bands + 1e-14)


def lsd_slice(bs: np.ndarray, br: np.ndarray, t: np.ndarray, t0: float, t1: float,
              floor_db: float = -75.0) -> float:
    """Mean abs dB difference over a time slice of two band spectrograms,
    ignoring bands where both are below the floor (relative to each signal's
    own max)."""
    sel = (t >= t0) & (t < t1)
    if not sel.any():
        return float("nan")
    a = bs[:, sel] - bs.max()
    b = br[:, sel] - br.max()
    mask = (a > floor_db) | (b > floor_db)
    if not mask.any():
        return float("nan")
    return float(np.abs(a[mask] - b[mask]).mean())
