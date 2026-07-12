"""Objective benchmark: synthesized section sustain vs reference.

Sustained-ensemble percept: steady harmonic timbre (body formants),
the MODULATION texture (ensemble shimmer, vibrato, sustain
undulation — plain LSD cannot hear this), and the macro envelope
(rise, sustain, release). All renders are stochastic realizations:
judge against the seed and perturbed-self nulls.

Metrics (lower = better unless noted):
  - harm_db:  mean |dB diff| of the first 16 matched steady harmonics
              (each side normalized to its strongest, ref > -60 dB)
  - lsd_sus:  band-LSD over the sustain window (floor -45 dB)
  - env_db:   mean |RMS env diff| (dB), 50 ms hop, full note,
              ref-masked at -40 dB
  - mod_db:   modulation-spectrum distance — dB energy of the sustain
              envelope's modulation in 3 bins (0.2-1, 1-3, 3-9 Hz),
              mean |diff|
  - rise_err: |log ratio| of -20..-3 dB rise times
  - rel_err:  |log ratio| of release fade taus
"""

from __future__ import annotations

import math

import numpy as np

from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram as _band_spectrogram
from lab.metrics import lsd_slice as _lsd
from lab.notes import midi_to_freq, name_to_midi

from .analysis import (envelope_marks, release_fit, rms_env,
                       steady_spectrum)

MOD_BINS = [(0.2, 1.0), (1.0, 3.0), (3.0, 9.0)]


def _mod_spectrum(x, sr, t0, t1):
    env = rms_env(x, sr, 0.005)
    i0, i1 = int(t0 / 0.005), int(t1 / 0.005)
    sus = env[i0:i1]
    if len(sus) < 100:
        return [0.0] * len(MOD_BINS)
    d = 20 * np.log10(sus / (sus.mean() + 1e-20) + 1e-12)
    d = d - d.mean()
    w = np.hanning(len(d))
    spec = np.abs(np.fft.rfft(d * w)) ** 2
    frq = np.fft.rfftfreq(len(d), 0.005)
    out = []
    for lo, hi in MOD_BINS:
        sel = (frq >= lo) & (frq < hi)
        e = float(spec[sel].sum()) if sel.any() else 1e-12
        out.append(10 * math.log10(e + 1e-12))
    return out


def compare(synth: np.ndarray, sr: int, ref_path: str, note: str,
            max_seconds: float = 12.0) -> dict:
    ref, sr_r = load_mono(ref_path)
    assert sr_r == sr, f"sample-rate mismatch {sr_r} vs {sr}"
    s = np.asarray(synth, float)
    s = s[find_onset(s, sr):]
    r = ref[find_onset(ref, sr):]
    n = int(min(len(s), len(r), max_seconds * sr))
    s, r = s[:n], r[:n]

    # gain: match median sustain RMS
    er, es = rms_env(r, sr), rms_env(s, sr)
    m = min(len(er), len(es))
    er, es = er[:m], es[:m]
    mask = er > er.max() * 10 ** (-20 / 20)
    gain = float(np.median(er[mask]) / (np.median(es[mask]) + 1e-20))
    s = s * gain

    # macro envelope: smoothed 1 s — pointwise undulation realizations
    # differ by construction (stochastic); mod_db scores their statistics
    from scipy.ndimage import uniform_filter1d

    es = uniform_filter1d(es * gain, 101)
    er_s = uniform_filter1d(er, 101)
    ref_db = 20 * np.log10(er_s / (er_s.max() + 1e-20) + 1e-12)
    dmask = ref_db > -40
    hop10 = 5  # 50 ms in 10 ms frames
    d = 20 * np.log10((es[dmask][::hop10] + 1e-12)
                      / (er_s[dmask][::hop10] + 1e-12))
    env_db = float(np.abs(d).mean()) if len(d) else float("nan")

    # marks from each side
    r0, r1, rise_r = envelope_marks(r, sr)
    s0, s1, rise_s_ = envelope_marks(s, sr)
    rise_err = abs(math.log(max(rise_s_, 0.02) / max(rise_r, 0.02)))

    span = r1 - r0
    w0, w1 = r0 + 0.15 * span, r0 + 0.85 * span

    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)
    _, hr, _ = steady_spectrum(r, sr, f0n, w0, w1)
    _, hs, _ = steady_spectrum(s, sr, f0n, w0, w1)
    hs_m = {h["n"]: h["db"] for h in hs}
    diffs = []
    for h in hr[:16]:
        if h["db"] < -60:
            continue
        if h["n"] in hs_m:
            diffs.append(abs(hs_m[h["n"]] - h["db"]))
        else:
            diffs.append(20.0)
    harm_db = float(np.mean(diffs)) if diffs else float("nan")

    tt_s, bs = _band_spectrogram(s, sr)
    tt_r, br = _band_spectrogram(r, sr)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt_s[:m2]
    lsd_sus = _lsd(bs, br, tt, w0, w1, floor_db=-45.0)

    ms = _mod_spectrum(s, sr, w0, w1)
    mr = _mod_spectrum(r, sr, w0, w1)
    mod_db = float(np.mean([abs(a - b) for a, b in zip(ms, mr)]))

    rel_r, _, _ = release_fit(r, sr, r1)
    rel_s2, _, _ = release_fit(s, sr, s1)
    rel_err = abs(math.log(max(rel_s2, 0.02) / max(rel_r, 0.02)))

    def _r(v, nd=2):
        return round(v, nd) if v == v else None

    return {
        "note": note,
        "harm_db": _r(harm_db),
        "lsd_sus": _r(lsd_sus),
        "env_db": _r(env_db),
        "mod_db": _r(mod_db),
        "rise_err": _r(rise_err, 3),
        "rel_err": _r(rel_err, 3),
        "gain_applied": round(gain, 4),
    }


def composite_score(m: dict) -> float:
    """Single scalar distance. Weights are SECTION-SUSTAIN-SPECIFIC."""
    parts = []
    if m.get("harm_db") is not None:
        parts.append(m["harm_db"] / 4)
    if m.get("lsd_sus") is not None:
        parts.append(m["lsd_sus"] / 6)
    if m.get("env_db") is not None:
        parts.append(m["env_db"] / 3)
    if m.get("mod_db") is not None:
        parts.append(m["mod_db"] / 4)
    # rise_err / rel_err stay in the metrics dict as diagnostics only:
    # threshold-crossing times on a stochastically undulating envelope
    # are realization-hostage even after smoothing; the 1 s-smoothed
    # env_db scores the same macro shape robustly
    return round(float(np.mean(parts)), 3)
