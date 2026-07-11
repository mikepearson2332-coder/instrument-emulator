"""Objective benchmark: compare a synthesized piano note against its
reference sample. Generic metrics come from lab/; this module adds the
piano-specific structure (partial matching, decay comparison) and the
composite weighting.

Metrics (all lower = better, except noted):
  - f0_cents:        fundamental tuning error in cents
  - b_logerr:        |log10(B_synth / B_ref)| inharmonicity mismatch
  - partial_cents:   mean partial-frequency error (cents, first 20 partials)
  - decay_logerr:    mean |log(tau_synth / tau_ref)| for the slow decay of
                     the first 12 partials
  - lsd_early:       log-spectral distance (dB) over 0-0.5 s, 60 bands
  - lsd_mid:         log-spectral distance (dB) over 0.5-2.5 s
  - env_db:          mean |RMS-envelope difference| (dB) over first 3 s
  - centroid_ratio:  brightness ratio synth/ref in first 300 ms (1.0 = ideal)
"""

from __future__ import annotations

import math

import numpy as np

from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram as _band_spectrogram
from lab.metrics import lsd_slice as _lsd
from lab.partials import find_partials, fit_double_decay, partial_envelope
from .notes import midi_to_freq, name_to_midi


def _align(x: np.ndarray, sr: int) -> np.ndarray:
    return x[find_onset(x, sr):]


def compare(synth: np.ndarray, sr: int, ref_path: str, note: str,
            max_seconds: float = 8.0) -> dict:
    ref, sr_r = load_mono(ref_path)
    assert sr_r == sr, f"sample-rate mismatch {sr_r} vs {sr}"
    s = _align(np.asarray(synth, float), sr)
    r = _align(ref, sr)
    n = int(min(len(s), len(r), max_seconds * sr))
    s, r = s[:n], r[:n]

    # normalize both to unit RMS-max for envelope/spectral comparison
    def rms_env(x):
        hop = int(0.010 * sr)
        m = len(x) // hop
        fr = x[: m * hop].reshape(m, hop)
        return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)

    es, er = rms_env(s), rms_env(r)
    gain = er.max() / (es.max() + 1e-20)
    s = s * gain
    es = es * gain

    m = min(len(es), len(er), 300)  # 3 s
    env_db = float(np.abs(20 * np.log10((es[:m] + 1e-12) / (er[:m] + 1e-12))).mean())

    # partial structure
    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)
    f0s, Bs, ps = find_partials(s, sr, f0n)
    f0r, Br, pr = find_partials(r, sr, f0n)
    f0_cents = 1200 * math.log2(max(f0s, 1e-6) / max(f0r, 1e-6))
    b_logerr = abs(math.log10(max(Bs, 1e-8) / max(Br, 1e-8)))

    # match ref partials to synth partials by nearest frequency (robust to
    # index mislocks on either side); ignore pairs further than 60 cents
    sfreqs = np.array([p["freq"] for p in ps]) if ps else np.array([1.0])
    pairs = []
    for p_ref in sorted(pr, key=lambda q: q["n"])[:20]:
        fr_ = p_ref["freq"]
        k = int(np.argmin(np.abs(np.log(sfreqs / fr_))))
        c = 1200 * math.log2(sfreqs[k] / fr_)
        if abs(c) < 60:
            pairs.append((float(sfreqs[k]), fr_, abs(c)))
    if pairs:
        partial_cents = float(np.median([c for _, _, c in pairs]))
    else:
        partial_cents = float("nan")

    # decay of slow stage, first 12 matched partials
    decs = []
    for fs_, fr_, _c in pairs[:12]:
        ts_, envs_ = partial_envelope(s, sr, fs_)
        tr_, envr_ = partial_envelope(r, sr, fr_)
        dfs = fit_double_decay(ts_, envs_)
        dfr = fit_double_decay(tr_, envr_)
        if dfs and dfr and dfr.tau_slow > 0 and dfs.tau_slow > 0:
            decs.append(abs(math.log(dfs.tau_slow / dfr.tau_slow)))
    decay_logerr = float(np.mean(decs)) if decs else float("nan")

    # band spectrograms
    tt_s, bs = _band_spectrogram(s, sr)
    tt_r, br = _band_spectrogram(r, sr)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt_s[:m2]
    lsd_early = _lsd(bs, br, tt, 0.0, 0.5)
    lsd_mid = _lsd(bs, br, tt, 0.5, 2.5)

    # brightness
    def centroid(x):
        seg = x[: int(0.3 * sr)]
        w = np.hanning(len(seg))
        magn = np.abs(np.fft.rfft(seg * w))
        fax = np.fft.rfftfreq(len(seg), 1 / sr)
        return (magn * fax).sum() / (magn.sum() + 1e-20)

    centroid_ratio = float(centroid(s) / (centroid(r) + 1e-20))

    return {
        "note": note,
        "f0_cents": round(f0_cents, 2),
        "b_logerr": round(b_logerr, 3),
        "partial_cents": round(partial_cents, 2) if partial_cents == partial_cents else None,
        "decay_logerr": round(decay_logerr, 3) if decay_logerr == decay_logerr else None,
        "lsd_early": round(lsd_early, 2) if lsd_early == lsd_early else None,
        "lsd_mid": round(lsd_mid, 2) if lsd_mid == lsd_mid else None,
        "env_db": round(env_db, 2),
        "centroid_ratio": round(centroid_ratio, 3),
        "gain_applied": round(float(gain), 4),
    }


def composite_score(m: dict) -> float:
    """Single scalar quality distance (lower = closer to reference).
    Weights are PIANO-SPECIFIC — do not reuse for other instruments."""
    parts = []
    if m.get("partial_cents") is not None:
        parts.append(min(m["partial_cents"], 50) / 10)
    if m.get("decay_logerr") is not None:
        parts.append(m["decay_logerr"] * 2)
    if m.get("lsd_early") is not None:
        parts.append(m["lsd_early"] / 6)
    if m.get("lsd_mid") is not None:
        parts.append(m["lsd_mid"] / 6)
    parts.append(m["env_db"] / 4)
    parts.append(abs(math.log(max(m["centroid_ratio"], 1e-3))) * 3)
    return round(float(np.mean(parts)), 3)
