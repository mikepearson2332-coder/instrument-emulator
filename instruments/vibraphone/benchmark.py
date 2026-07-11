"""Objective benchmark: synthesized vibraphone note vs reference.

What the ear cares about for vibes: fundamental tuning (it's a tuned
mallet instrument), the long fundamental decay, the attack's mode balance
(4f0/10f0 + mallet thud brightness), and the envelope over several
seconds. Weights differ from both piano and woodblock accordingly.

Metrics (lower = better unless noted):
  - f0_cents:     fundamental tuning error (tuned instrument: weighted)
  - mode_cents:   median |cents| of the top-3 reference modes matched
                  nearest in the synth
  - decay_logerr: |log tau ratio| of the fundamental's effective decay
                  (measured as t(-40 dB) on the envelope, robust to
                  fast/slow stage splits)
  - env_db:       mean |RMS envelope diff| (dB), 10 ms hop, first 6 s
  - lsd_early:    band-LSD 0-0.5 s   (floor -45 dB)
  - lsd_mid:      band-LSD 0.5-4 s   (floor -45 dB)
  - centroid_ratio: brightness ratio, first 300 ms
"""

from __future__ import annotations

import math

import numpy as np

from lab.audio import find_onset
from lab.metrics import band_spectrogram as _band_spectrogram
from lab.metrics import lsd_slice as _lsd
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import partial_envelope

from .analysis import find_modes, load_hp


def _align(x, sr):
    return x[find_onset(x, sr):]


def _rms_env(x, sr, hop_s=0.010):
    hop = max(1, int(hop_s * sr))
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def _t_at_db(t, env, db_down=40.0):
    """Time where the envelope last crosses `db_down` below its peak."""
    db = 20 * np.log10(env / (env.max() + 1e-20) + 1e-12)
    above = np.nonzero(db > -db_down)[0]
    if len(above) == 0:
        return None
    return float(t[above[-1]])


def compare(synth: np.ndarray, sr: int, ref_path: str, note: str,
            max_seconds: float = 8.0) -> dict:
    ref, sr_r = load_hp(ref_path)
    assert sr_r == sr, f"sample-rate mismatch {sr_r} vs {sr}"
    s = _align(np.asarray(synth, float), sr)
    r = _align(ref, sr)
    n = int(min(len(s), len(r), max_seconds * sr))
    s, r = s[:n], r[:n]

    es, er = _rms_env(s, sr), _rms_env(r, sr)
    gain = er.max() / (es.max() + 1e-20)
    s = s * gain
    es = es * gain

    m = min(len(es), len(er), 600)  # 6 s
    ref_db = 20 * np.log10(er[:m] / (er[:m].max() + 1e-20) + 1e-12)
    # pp takes have ~30-40 dB SNR: below -45 dB the envelope is hiss
    mask = ref_db > -45.0
    env_db = float(np.abs(20 * np.log10(
        (es[:m][mask] + 1e-12) / (er[:m][mask] + 1e-12))).mean())

    f0n = midi_to_freq(name_to_midi(note))
    f0s, ms = find_modes(s, sr, f0n)
    f0r, mr = find_modes(r, sr, f0n)
    f0_cents = 1200 * math.log2(max(f0s, 1e-6) / max(f0r, 1e-6))

    sfreqs = np.array([m_["freq"] for m_ in ms]) if ms else np.array([1.0])
    pairs = []
    for m_ref in sorted(mr, key=lambda q: -q["amp"])[:3]:
        fr_ = m_ref["freq"]
        k = int(np.argmin(np.abs(np.log(sfreqs / fr_))))
        c = 1200 * math.log2(sfreqs[k] / fr_)
        if abs(c) < 150:
            pairs.append((float(sfreqs[k]), fr_, abs(c)))
    mode_cents = float(np.median([c for _, _, c in pairs])) if pairs else float("nan")

    # fundamental decay: time to -40 dB on the demodulated f0 envelope
    win = max(16, int(sr / 50.0))
    ts_, envs_ = partial_envelope(s, sr, f0s, hop=0.010, win_samples=win)
    tr_, envr_ = partial_envelope(r, sr, f0r, hop=0.010, win_samples=win)
    ta = _t_at_db(ts_, envs_)
    tb = _t_at_db(tr_, envr_)
    if ta and tb and ta > 0.1 and tb > 0.1:
        decay_logerr = abs(math.log(ta / tb))
    else:
        decay_logerr = float("nan")

    # fmin 90: below the lowest bar there is only recording-chain residue
    tt_s, bs = _band_spectrogram(s, sr, fmin=90.0)
    tt_r, br = _band_spectrogram(r, sr, fmin=90.0)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt_s[:m2]
    # floor -35 dB: the pp reference bottoms out at the recording noise
    # floor ~30 dB under the peak band (same lesson as the woodblock)
    lsd_early = _lsd(bs, br, tt, 0.0, 0.5, floor_db=-35.0)
    lsd_mid = _lsd(bs, br, tt, 0.5, 4.0, floor_db=-35.0)

    def centroid(x):
        seg = x[: int(0.3 * sr)]
        w = np.hanning(len(seg))
        magn = np.abs(np.fft.rfft(seg * w))
        fax = np.fft.rfftfreq(len(seg), 1 / sr)
        # level gate: integrated hiss across 60k bins otherwise dominates
        # the pp takes and drags the "brightness" to 14 kHz
        magn = np.where(magn > magn.max() * 10 ** (-50 / 20), magn, 0.0)
        return (magn * fax).sum() / (magn.sum() + 1e-20)

    centroid_ratio = float(centroid(s) / (centroid(r) + 1e-20))

    def _r(v, nd=2):
        return round(v, nd) if v == v else None

    return {
        "note": note,
        "f0_cents": _r(f0_cents),
        "mode_cents": _r(mode_cents),
        "decay_logerr": _r(decay_logerr, 3),
        "env_db": _r(env_db),
        "lsd_early": _r(lsd_early),
        "lsd_mid": _r(lsd_mid),
        "centroid_ratio": _r(centroid_ratio, 3),
        "gain_applied": round(float(gain), 4),
    }


def composite_score(m: dict) -> float:
    """Single scalar distance. Weights are VIBRAPHONE-SPECIFIC: tuning +
    fundamental decay + multi-second envelope dominate."""
    parts = []
    if m.get("f0_cents") is not None:
        parts.append(min(abs(m["f0_cents"]), 50) / 12)
    if m.get("mode_cents") is not None:
        parts.append(min(m["mode_cents"], 60) / 25)
    if m.get("decay_logerr") is not None:
        parts.append(m["decay_logerr"] * 2.0)
    parts.append(m["env_db"] / 3)
    if m.get("lsd_early") is not None:
        parts.append(m["lsd_early"] / 6)
    if m.get("lsd_mid") is not None:
        parts.append(m["lsd_mid"] / 6)
    if m.get("centroid_ratio"):
        parts.append(abs(math.log(max(m["centroid_ratio"], 1e-3))) * 2)
    return round(float(np.mean(parts)), 3)
