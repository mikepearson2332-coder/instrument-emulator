"""Analysis of plucked long-zither recordings (VCSL đàn tranh).

The piano's machinery applies nearly unchanged — inharmonic string series
via `lab.partials.find_partials`, per-partial complex-demodulation
envelopes, robust two-stage decay fits — with pluck-scale windows (5 ms
hop; notes ring 2-7 s) and the woodblock's per-band click decay for the
plectrum transient.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import stft, get_window

from lab.audio import find_onset, load_mono
from lab.metrics import STFT_HOP_S, STFT_WIN_S
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import (
    envelope_window,
    find_partials,
    fit_double_decay,
    partial_envelope,
)

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)

MAX_PARTIALS = 40

THUMP_WIN_S = 0.08
BED_LO_S, BED_HI_S = 0.5, 2.0
SLOPE_LO_S, SLOPE_HI_S = 0.4, 2.5


def bed_thump_profile(x: np.ndarray, sr: int, f0: float,
                      partial_freqs: list[float]) -> dict:
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
    thump_sel = t < THUMP_WIN_S
    bed_sel = (t >= BED_LO_S) & (t <= min(BED_HI_S, 0.8 * T))
    slope_sel = (t >= SLOPE_LO_S) & (t <= min(SLOPE_HI_S, 0.9 * T))

    thump_db, thump_tau, bed_db, bed_t60 = [], [], [], []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1]) & non_partial
        if sel.sum() < 2:
            thump_db.append(None)
            thump_tau.append(None)
            bed_db.append(None)
            bed_t60.append(None)
            continue
        med = np.median(A[sel], axis=0)
        tv = float(med[thump_sel].max()) if thump_sel.any() else 0.0
        bv = float(np.median(med[bed_sel])) if bed_sel.any() else 0.0
        thump_db.append(round(20 * math.log10(tv + 1e-12), 2))
        bed_db.append(round(20 * math.log10(bv + 1e-12), 2))
        k0 = int(np.argmax(med[thump_sel])) if thump_sel.any() else 0
        tsel = (t >= t[k0]) & (t <= 0.15)
        if tsel.sum() > 4:
            ts = t[tsel]
            ds = 20 * np.log10(med[tsel] + 1e-12)
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            slope = coef[0]
            tau = -8.686 / slope if slope < -30.0 else 0.12
            thump_tau.append(round(float(np.clip(tau, 0.004, 0.12)), 4))
        else:
            thump_tau.append(None)
        if slope_sel.sum() > 6:
            ts = t[slope_sel]
            ds = 20 * np.log10(med[slope_sel] + 1e-12)
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            slope = coef[0]
            t60 = 60.0 / -slope if slope < -1.0 else 30.0
            bed_t60.append(round(float(np.clip(t60, 0.2, 30.0)), 2))
        else:
            bed_t60.append(None)
    return {"thump_db": thump_db, "thump_tau": thump_tau,
            "bed_db": bed_db, "bed_t60": bed_t60,
            "bed_anchor_s": round(0.5 * (BED_LO_S + BED_HI_S), 2)}


def analyze_note(path: str, note: str) -> dict:
    x, sr = load_mono(path)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak_abs = float(np.max(np.abs(x)) + 1e-20)
    midi = name_to_midi(note)
    f0_nom = midi_to_freq(midi)

    f0, B, partials = find_partials(xo, sr, f0_nom, max_partials=MAX_PARTIALS)

    results = []
    for p in partials:
        n = p["n"]
        spacing = f0 * (math.sqrt(1 + B * (n + 1) ** 2) * (n + 1)
                        - math.sqrt(1 + B * n * n) * n)
        spacing = max(spacing, f0 * 0.5)
        win = envelope_window(sr, spacing, f0=f0)
        t, env = partial_envelope(xo, sr, p["freq"], hop=0.005,
                                  win_samples=win)
        _, env_noise = partial_envelope(xo, sr, p["freq"] + 0.5 * spacing,
                                        hop=0.005, win_samples=win)
        noise_med = float(np.median(env_noise))
        entry = {"n": n, "freq": p["freq"], "amp": p["amp"]}
        valid = env > 2.0 * env_noise
        if n <= 2:
            valid = np.ones(len(env), bool)
        # trailing-junk guard (see vibraphone DEVLOG)
        if valid.sum() >= 10 and int(np.argmax(env)) > 0.4 * len(env):
            valid = np.zeros(len(env), bool)
        if valid.sum() >= 10:
            floor = max(-65.0, 20 * math.log10(
                2.5 * noise_med / (env.max() + 1e-20) + 1e-12))
            fit = fit_double_decay(t[valid], env[valid], floor_db=floor)
            if fit is not None:
                env_max = float(env.max())
                a_fast = min(fit.a_fast, 2.2 * env_max)
                a_slow = min(fit.a_slow, 1.3 * env_max)
                entry.update({
                    "a_fast": a_fast / peak_abs, "tau_fast": fit.tau_fast,
                    "a_slow": a_slow / peak_abs,
                    "tau_slow": min(fit.tau_slow, 30.0),
                    "fit_rmse_db": fit.rmse_db,
                    "snr": float(env.max() / (noise_med + 1e-20)),
                })
        results.append(entry)

    profile = bed_thump_profile(xo, sr, f0, [p["freq"] for p in partials])

    hop = int(0.005 * sr)
    nfr = len(xo) // hop
    fr = xo[: nfr * hop].reshape(nfr, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)

    seg = xo[: int(0.15 * sr)]
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
        "f0_nominal": f0_nom,
        "f0": f0,
        "B": B,
        "n_partials": len(results),
        "peak_abs": peak_abs,
        "rms_max": float(rms.max()),
        "centroid_150ms": centroid,
        "thump_db": profile["thump_db"],
        "thump_tau": profile["thump_tau"],
        "bed_db": profile["bed_db"],
        "bed_t60": profile["bed_t60"],
        "bed_anchor_s": profile["bed_anchor_s"],
        "partials": results,
        "rms_env_hop_s": 0.005,
        "rms_env_db": [round(float(20 * np.log10(v / (rms.max() + 1e-20) + 1e-12)), 2)
                       for v in rms[:1200]],
    }


def analyze_to_json(path: str, note: str, out_path: str) -> dict:
    res = analyze_note(path, note)
    with open(out_path, "w") as f:
        json.dump(res, f)
    return res
