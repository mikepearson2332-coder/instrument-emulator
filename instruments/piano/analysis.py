"""Analysis of piano recordings: partial tracking, inharmonicity, decay fitting.

Extracts a compact parametric description of a recorded piano note:
  - refined fundamental f0 and inharmonicity coefficient B
  - per-partial: frequency, initial amplitude, two-stage decay times
  - broadband attack-noise profile
These descriptions serve both as calibration targets for the synthesizer and
as the reference side of the benchmark.

The generic machinery (loading, onset, partial tracking, envelopes, decay
fits) lives in lab/ and is re-exported here for compatibility; this module
keeps what is piano-specific: the damper-cliff release detector, the
bed/thump broadband profile, and the full analysis recipe.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import stft, get_window

from lab.audio import find_onset, load_mono  # noqa: F401  (re-exported)
from lab.metrics import STFT_HOP_S, STFT_WIN_S
from lab.partials import (  # noqa: F401  (re-exported)
    DecayFit,
    envelope_window as _envelope_window,
    find_partials,
    fit_double_decay,
    partial_envelope,
)
from .notes import name_to_midi, midi_to_freq


def find_release(x: np.ndarray, sr: int) -> int | None:
    """Sample index of the key-release damper cliff, or None.

    Looks for a sustained sudden drop (>= 12 dB within 200 ms) in the RMS
    envelope after the first 25% of the signal."""
    hop = int(0.05 * sr)
    m = len(x) // hop
    if m < 12:
        return None
    fr = x[: m * hop].reshape(m, hop)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-12)
    peak = db.max()
    start = max(4, int(0.25 * m))
    for i in range(start, m - 4):
        if db[i] < peak - 70:
            continue  # already in the noise floor
        if db[i + 4] - db[i] <= -12.0:
            return i * hop
    return None


# ---------------------------------------------------- broadband bed / thump

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)  # 10 log bands


def bed_thump_profile(x: np.ndarray, sr: int, f0: float,
                      partial_freqs: list[float]) -> dict:
    """Broadband (non-partial) content: attack thump and sustained
    resonance bed, per log band. Levels are absolute dB of median STFT
    magnitude across non-partial bins.

    Returns {"thump_db": [...], "bed_db": [...], "bed_t60": [...]} with None
    for bands that can't be measured (partial forest too dense)."""
    nper = int(STFT_WIN_S * sr)
    nover = nper - int(STFT_HOP_S * sr)
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
    A = np.abs(Z)
    binw = f[1] - f[0]

    pf = np.asarray(partial_freqs, float)
    if len(pf):
        dist = np.min(np.abs(f[:, None] - pf[None, :]), axis=1)
    else:
        dist = np.full(len(f), 1e9)
    guard = max(1.5 * binw, 0.15 * f0)
    non_partial = dist > guard

    T = t[-1] if len(t) else 0.0
    thump_sel = t < 0.12
    bed_lo, bed_hi = 0.8, max(1.2, min(3.5, 0.8 * T))
    bed_sel = (t >= bed_lo) & (t <= bed_hi)
    slope_sel = (t >= 0.5) & (t <= max(1.0, min(5.0, 0.9 * T)))

    thump_db, bed_db, bed_t60 = [], [], []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1]) & non_partial
        if sel.sum() < 3:
            thump_db.append(None)
            bed_db.append(None)
            bed_t60.append(None)
            continue
        med = np.median(A[sel], axis=0)  # per-frame broadband amplitude
        tv = float(med[thump_sel].max()) if thump_sel.any() else 0.0
        bv = float(np.median(med[bed_sel])) if bed_sel.any() else 0.0
        thump_db.append(round(20 * math.log10(tv + 1e-12), 2))
        bed_db.append(round(20 * math.log10(bv + 1e-12), 2))
        # decay of the bed: dB slope over the sustained region
        if slope_sel.sum() > 8:
            ts = t[slope_sel]
            ds = 20 * np.log10(med[slope_sel] + 1e-12)
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            slope = coef[0]
            t60 = 60.0 / -slope if slope < -0.5 else 60.0
            bed_t60.append(round(float(np.clip(t60, 0.3, 60.0)), 2))
        else:
            bed_t60.append(None)
    return {"thump_db": thump_db, "bed_db": bed_db, "bed_t60": bed_t60,
            "bed_anchor_s": round(0.5 * (bed_lo + bed_hi), 2)}


# ------------------------------------------------------------ full analysis

def analyze_note(path: str, note: str, max_partials: int = 80) -> dict:
    """Full parametric analysis of one recorded note."""
    x, sr = load_mono(path)
    onset = find_onset(x, sr)
    midi = name_to_midi(note)
    f0_nom = midi_to_freq(midi)
    f0, B, partials = find_partials(x, sr, f0_nom, max_partials=max_partials)

    xo = x[onset:]
    peak_abs = float(np.max(np.abs(x)) + 1e-20)
    release = find_release(xo, sr)
    # decay fitting must not see the damper cliff
    xo_fit = xo[: release - int(0.1 * sr)] if release else xo
    if len(xo_fit) < sr // 2:
        xo_fit = xo
    results = []
    for p in partials:
        n = p["n"]
        # local partial spacing from the inharmonic model
        spacing = f0 * (math.sqrt(1 + B * (n + 1) ** 2) * (n + 1)
                        - math.sqrt(1 + B * n * n) * n)
        spacing = max(spacing, f0 * 0.5)
        win = _envelope_window(sr, spacing, f0=f0)
        t, env = partial_envelope(xo_fit, sr, p["freq"], win_samples=win)
        # noise probe halfway to the next partial: the same window nulls the
        # partials there, so this measures the broadband floor only
        _, env_noise = partial_envelope(xo_fit, sr, p["freq"] + 0.5 * spacing,
                                        win_samples=win)
        noise_med = float(np.median(env_noise))
        entry = {"n": n, "freq": p["freq"], "amp": p["amp"]}
        # pointwise validity: the partial must beat the *simultaneous*
        # broadband floor, otherwise attack noise masquerades as a partial.
        # The lowest three partials always dominate their band — no mask,
        # or soft-attack notes lose their tone core.
        if n <= 3:
            valid = np.ones(len(env), bool)
        else:
            valid = env > 2.2 * env_noise
        if valid.sum() >= 8:
            fit = fit_double_decay(t[valid], env[valid])
            if fit is not None:
                entry.update({
                    "a_fast": fit.a_fast / peak_abs, "tau_fast": fit.tau_fast,
                    "a_slow": fit.a_slow / peak_abs, "tau_slow": fit.tau_slow,
                    "fit_rmse_db": fit.rmse_db,
                    "snr": float(env.max() / (noise_med + 1e-20)),
                })
        results.append(entry)

    profile = bed_thump_profile(xo_fit, sr, f0, [p["freq"] for p in partials])

    # global loudness envelope (RMS, 10 ms hop) for benchmark use
    hop = int(0.010 * sr)
    nfr = len(xo) // hop
    fr = xo[: nfr * hop].reshape(nfr, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)

    # spectral centroid of the first 300 ms (brightness proxy)
    seg = xo[: int(0.3 * sr)]
    w = get_window("hann", len(seg))
    mag = np.abs(np.fft.rfft(seg * w))
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    centroid = float((mag * fax).sum() / (mag.sum() + 1e-20))

    return {
        "note": note,
        "midi": midi,
        "sr": sr,
        "duration": len(x) / sr,
        "onset_s": onset / sr,
        "release_s": release / sr if release else None,
        "f0_nominal": f0_nom,
        "f0": f0,
        "B": B,
        "n_partials": len(results),
        "peak_abs": peak_abs,
        "rms_max": float(rms.max()),
        "centroid_300ms": centroid,
        "thump_db": profile["thump_db"],
        "bed_db": profile["bed_db"],
        "bed_t60": profile["bed_t60"],
        "bed_anchor_s": profile["bed_anchor_s"],
        "partials": results,
        "rms_env_hop_s": 0.010,
        "rms_env_db": [round(float(20 * np.log10(v / (rms.max() + 1e-20) + 1e-12)), 2) for v in rms[:3000]],
    }


def analyze_to_json(path: str, note: str, out_path: str, **kw) -> dict:
    res = analyze_note(path, note, **kw)
    with open(out_path, "w") as f:
        json.dump(res, f)
    return res
