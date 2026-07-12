"""Objective benchmark: synthesized tine-EP note vs reference.

Tine-EP percept, in order: (1) harmonic balance — the fundamental vs
bell (n2/n3) vs bark (higher harmonics) mix and how it moves with
velocity; (2) the singing sustain decay; (3) the hammer attack. Tuning
is near-trivial (exact harmonics) but kept as a guard.

Metrics (lower = better unless noted):
  - partial_cents: median |cents| of the first 10 reference harmonics
  - harm_db:       mean |dB diff| of the first 8 matched harmonic
                   amplitudes (each side normalized to its strongest) —
                   the timbre core for an EP
  - decay_logerr:  mean |log tau_slow ratio| of the first 6 matched
                   harmonics
  - env_db:        mean |RMS env diff| (dB), 5 ms hop, first 6 s,
                   ref-masked at -50 dB
  - attack_db:     same at 1 ms hop over the first 80 ms
  - lsd_early:     band-LSD 0-0.3 s (floor -40 dB; DI recording, no room)
  - lsd_mid:       band-LSD 0.3-2.0 s (floor -40 dB)
  - centroid_ratio: brightness ratio, first 150 ms (level-gated)
"""

from __future__ import annotations

import math

import numpy as np

from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram as _band_spectrogram
from lab.metrics import lsd_slice as _lsd
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import find_partials, fit_double_decay, partial_envelope

from .analysis import snap_harmonic


def _align(x, sr):
    return x[find_onset(x, sr):]


def _rms_env(x, sr, hop_s):
    hop = max(1, int(hop_s * sr))
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def _env_db_diff(s, r, sr, hop_s, t_max, floor_db=-50.0):
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


def _harmonics(x, sr, f0n):
    f0_fit, _B, raw = find_partials(x, sr, f0n, max_partials=16)
    return snap_harmonic(f0_fit, raw)


def compare(synth: np.ndarray, sr: int, ref_path: str, note: str,
            max_seconds: float = 8.0) -> dict:
    ref, sr_r = load_mono(ref_path)
    assert sr_r == sr, f"sample-rate mismatch {sr_r} vs {sr}"
    s = _align(np.asarray(synth, float), sr)
    r = _align(ref, sr)
    n = int(min(len(s), len(r), max_seconds * sr))
    s, r = s[:n], r[:n]

    es, er = _rms_env(s, sr, 0.005), _rms_env(r, sr, 0.005)
    gain = er.max() / (es.max() + 1e-20)
    s = s * gain

    env_db = _env_db_diff(s, r, sr, 0.005, 6.0)
    attack_db = _env_db_diff(s, r, sr, 0.001, 0.08)

    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)
    f0s, ps = _harmonics(s, sr, f0n)
    f0r, pr = _harmonics(r, sr, f0n)

    sp = {p["n"]: p for p in ps}
    pairs, harm_diffs = [], []
    smax = max((p["amp"] for p in ps), default=1.0)
    rmax = max((p["amp"] for p in pr), default=1.0)
    for p_ref in sorted(pr, key=lambda q: q["n"])[:10]:
        q = sp.get(p_ref["n"])
        if q is None:
            continue
        c = 1200 * math.log2(q["freq"] / p_ref["freq"])
        if abs(c) < 60:
            pairs.append((q, p_ref, abs(c)))
        if p_ref["n"] <= 8:
            ds = 20 * math.log10(q["amp"] / smax + 1e-12)
            dr = 20 * math.log10(p_ref["amp"] / rmax + 1e-12)
            if dr > -60:
                harm_diffs.append(abs(ds - dr))
    partial_cents = (float(np.median([c for _, _, c in pairs]))
                     if pairs else float("nan"))
    harm_db = float(np.mean(harm_diffs)) if harm_diffs else float("nan")

    decs = []
    for q, p_ref, _c in pairs[:6]:
        ts_, envs_ = partial_envelope(s, sr, q["freq"], hop=0.005)
        tr_, envr_ = partial_envelope(r, sr, p_ref["freq"], hop=0.005)
        dfs = fit_double_decay(ts_, envs_, floor_db=-55.0)
        dfr = fit_double_decay(tr_, envr_, floor_db=-55.0)
        if dfs and dfr and dfs.tau_slow > 0 and dfr.tau_slow > 0:
            decs.append(abs(math.log(min(dfs.tau_slow, 12.0)
                                     / min(dfr.tau_slow, 12.0))))
    decay_logerr = float(np.mean(decs)) if decs else float("nan")

    tt_s, bs = _band_spectrogram(s, sr)
    tt_r, br = _band_spectrogram(r, sr)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt_s[:m2]
    lsd_early = _lsd(bs, br, tt, 0.0, 0.3, floor_db=-40.0)
    lsd_mid = _lsd(bs, br, tt, 0.3, 2.0, floor_db=-40.0)

    def centroid(x):
        seg = x[: int(0.15 * sr)]
        w = np.hanning(len(seg))
        magn = np.abs(np.fft.rfft(seg * w))
        fax = np.fft.rfftfreq(len(seg), 1 / sr)
        magn = np.where(magn > magn.max() * 10 ** (-50 / 20), magn, 0.0)
        return (magn * fax).sum() / (magn.sum() + 1e-20)

    centroid_ratio = float(centroid(s) / (centroid(r) + 1e-20))

    def _r(v, nd=2):
        return round(v, nd) if v == v else None

    return {
        "note": note,
        "partial_cents": _r(partial_cents),
        "harm_db": _r(harm_db),
        "decay_logerr": _r(decay_logerr, 3),
        "env_db": _r(env_db),
        "attack_db": _r(attack_db),
        "lsd_early": _r(lsd_early),
        "lsd_mid": _r(lsd_mid),
        "centroid_ratio": _r(centroid_ratio, 3),
        "gain_applied": round(float(gain), 4),
    }


def composite_score(m: dict) -> float:
    """Single scalar distance. Weights are TINE-EP-SPECIFIC."""
    parts = []
    if m.get("partial_cents") is not None:
        parts.append(min(m["partial_cents"], 50) / 10)
    if m.get("harm_db") is not None:
        parts.append(m["harm_db"] / 4)
    if m.get("decay_logerr") is not None:
        parts.append(m["decay_logerr"] * 1.5)
    parts.append(m["env_db"] / 3)
    if m.get("attack_db") is not None:
        parts.append(m["attack_db"] / 4)
    if m.get("lsd_early") is not None:
        parts.append(m["lsd_early"] / 5)
    if m.get("lsd_mid") is not None:
        parts.append(m["lsd_mid"] / 7)
    if m.get("centroid_ratio"):
        parts.append(abs(math.log(max(m["centroid_ratio"], 1e-3))) * 2)
    return round(float(np.mean(parts)), 3)
