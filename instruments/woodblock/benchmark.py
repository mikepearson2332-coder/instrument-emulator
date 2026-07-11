"""Objective benchmark: synthesized woodblock hit vs reference sample.

Woodblock-specific structure: the percept is dominated by the attack
transient and the fast decay of a couple of modes, so the metric set and
composite weights lean on the first 150 ms (piano weights would be wrong).

Metrics (lower = better unless noted):
  - attack_db:   mean |RMS-envelope diff| (dB), 1 ms hop, first 50 ms
  - env_db:      mean |RMS-envelope diff| (dB), 2 ms hop, first 350 ms
  - mode_cents:  median |cents| error of the top reference modes matched
                 nearest-frequency in the synth (strike-to-strike f0 wander
                 in the reference is ~1% — judge against the null)
  - decay_logerr: mean |log(tau_fast ratio)| of the top 2 matched modes
  - lsd_early:   band-spectrogram distance 0-0.15 s
  - lsd_mid:     band-spectrogram distance 0.15-0.4 s
  - centroid_ratio: brightness ratio (first 60 ms), 1.0 = ideal
"""

from __future__ import annotations

import math

import numpy as np

from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram as _band_spectrogram
from lab.metrics import lsd_slice as _lsd
from lab.partials import fit_double_decay, partial_envelope
from .analysis import find_modes


def _align(x: np.ndarray, sr: int) -> np.ndarray:
    return x[find_onset(x, sr):]


def _rms_env(x: np.ndarray, sr: int, hop_s: float) -> np.ndarray:
    hop = max(1, int(hop_s * sr))
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def _env_db_diff(s: np.ndarray, r: np.ndarray, sr: int, hop_s: float,
                 t_max: float, floor_db: float = -55.0) -> float:
    es, er = _rms_env(s, sr, hop_s), _rms_env(r, sr, hop_s)
    m = min(len(es), len(er), int(t_max / hop_s))
    if m == 0:
        return float("nan")
    es, er = es[:m], er[:m]
    ref_db = 20 * np.log10(er / (er.max() + 1e-20) + 1e-12)
    mask = ref_db > floor_db
    if not mask.any():
        return float("nan")
    d = 20 * np.log10((es[mask] + 1e-12) / (er[mask] + 1e-12))
    return float(np.abs(d).mean())


def compare(synth: np.ndarray, sr: int, ref_path: str, note: str,
            max_seconds: float = 1.0) -> dict:
    ref, sr_r = load_mono(ref_path)
    assert sr_r == sr, f"sample-rate mismatch {sr_r} vs {sr}"
    s = _align(np.asarray(synth, float), sr)
    r = _align(ref, sr)
    n = int(min(len(s), len(r), max_seconds * sr))
    s, r = s[:n], r[:n]

    # gain: match peak RMS (2 ms hop)
    es, er = _rms_env(s, sr, 0.002), _rms_env(r, sr, 0.002)
    gain = er.max() / (es.max() + 1e-20)
    s = s * gain

    attack_db = _env_db_diff(s, r, sr, 0.001, 0.05)
    env_db = _env_db_diff(s, r, sr, 0.002, 0.35)

    # mode structure
    ms = find_modes(s, sr)
    mr = find_modes(r, sr)
    sfreqs = np.array([m["freq"] for m in ms]) if ms else np.array([1.0])
    pairs = []
    for m_ref in sorted(mr, key=lambda q: -q["amp"])[:4]:
        fr_ = m_ref["freq"]
        k = int(np.argmin(np.abs(np.log(sfreqs / fr_))))
        c = 1200 * math.log2(sfreqs[k] / fr_)
        if abs(c) < 200:
            pairs.append((float(sfreqs[k]), fr_, abs(c)))
    mode_cents = float(np.median([c for _, _, c in pairs])) if pairs else float("nan")

    # fast-decay comparison for the two strongest matched modes
    decs = []
    win = max(8, int(sr / 160.0))
    for fs_, fr_, _c in pairs[:2]:
        ts_, envs_ = partial_envelope(s, sr, fs_, hop=0.001, win_samples=win)
        tr_, envr_ = partial_envelope(r, sr, fr_, hop=0.001, win_samples=win)
        dfs = fit_double_decay(ts_, envs_, floor_db=-55.0)
        dfr = fit_double_decay(tr_, envr_, floor_db=-55.0)
        if dfs and dfr and dfs.tau_fast > 0 and dfr.tau_fast > 0:
            decs.append(abs(math.log(dfs.tau_fast / dfr.tau_fast)))
    decay_logerr = float(np.mean(decs)) if decs else float("nan")

    tt_s, bs = _band_spectrogram(s, sr)
    tt_r, br = _band_spectrogram(r, sr)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt_s[:m2]
    # floor -35 dB (not the piano's -75): pp reference takes bottom out at
    # the recording noise floor ~30 dB below the peak band — comparing the
    # synth's silence against tape hiss is not a model error
    lsd_early = _lsd(bs, br, tt, 0.0, 0.15, floor_db=-35.0)
    lsd_mid = _lsd(bs, br, tt, 0.15, 0.4, floor_db=-35.0)

    def centroid(x):
        seg = x[: int(0.06 * sr)]
        w = np.hanning(len(seg))
        magn = np.abs(np.fft.rfft(seg * w))
        fax = np.fft.rfftfreq(len(seg), 1 / sr)
        return (magn * fax).sum() / (magn.sum() + 1e-20)

    centroid_ratio = float(centroid(s) / (centroid(r) + 1e-20))

    def _r(v, nd=2):
        return round(v, nd) if v == v else None

    return {
        "note": note,
        "attack_db": _r(attack_db),
        "env_db": _r(env_db),
        "mode_cents": _r(mode_cents),
        "decay_logerr": _r(decay_logerr, 3),
        "lsd_early": _r(lsd_early),
        "lsd_mid": _r(lsd_mid),
        "centroid_ratio": _r(centroid_ratio, 3),
        "gain_applied": round(float(gain), 4),
        # keys the shared eval harness prints for the piano; keep the
        # interface tolerant
        "f0_cents": _r(mode_cents if mode_cents == mode_cents else 0.0),
        "partial_cents": _r(mode_cents),
    }


def composite_score(m: dict) -> float:
    """Single scalar distance (lower = better). Weights are
    WOODBLOCK-SPECIFIC: attack + short-time envelope dominate."""
    parts = []
    if m.get("attack_db") is not None:
        parts.append(m["attack_db"] / 3)
    if m.get("env_db") is not None:
        parts.append(m["env_db"] / 3)
    if m.get("lsd_early") is not None:
        parts.append(m["lsd_early"] / 5)
    if m.get("lsd_mid") is not None:
        parts.append(m["lsd_mid"] / 8)
    if m.get("mode_cents") is not None:
        parts.append(min(m["mode_cents"], 120) / 40)
    if m.get("decay_logerr") is not None:
        parts.append(m["decay_logerr"] * 1.5)
    if m.get("centroid_ratio"):
        parts.append(abs(math.log(max(m["centroid_ratio"], 1e-3))) * 2)
    return round(float(np.mean(parts)), 3)
