"""Audio loading and onset detection (instrument-agnostic)."""

from __future__ import annotations

import numpy as np
import soundfile as sf


def load_mono(path: str) -> tuple[np.ndarray, int]:
    x, sr = sf.read(path, always_2d=True)
    return x.mean(axis=1).astype(np.float64), sr


def find_onset(x: np.ndarray, sr: int, thresh_db: float = -45.0) -> int:
    """Index of the first sample where short-term energy exceeds thresh_db
    relative to the global peak."""
    win = max(1, sr // 200)  # 5 ms
    n = len(x) // win
    frames = x[: n * win].reshape(n, win)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-20)
    peak = rms.max()
    above = np.nonzero(rms > peak * 10 ** (thresh_db / 20))[0]
    if len(above) == 0:
        return 0
    return int(above[0] * win)
