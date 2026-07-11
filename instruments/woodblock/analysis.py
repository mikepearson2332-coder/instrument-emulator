"""Analysis of woodblock recordings: idiophone mode finding + decay fitting.

A woodblock note is a handful of fast-decaying modes (tau ~ 5-40 ms) at
non-integer frequency ratios plus a broadband stick click and a short room
tail. Differences from the piano analysis:

  - mode finder picks spectral peaks with a minimum separation instead of
    fitting a string series (`lab.partials.find_partials` doesn't apply);
  - envelopes are demodulated at 1 ms hop with a ~10 ms window (piano's
    10 ms hop can't see a 7 ms decay);
  - thump/bed windows are scaled to a <0.5 s event: thump = max over
    t < 0.06 s, bed = median over 0.10-0.30 s (anchor 0.2 s).

Mode-cluster warning (see research brief): a tau = 8 ms mode is ~20 Hz wide
(Lorentzian), so naive peak-picking slices one resonance into several fake
peaks. The min separation below keeps picked modes at least ~6% apart.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import stft, get_window

from lab.audio import find_onset, load_mono
from lab.metrics import STFT_HOP_S, STFT_WIN_S
from lab.partials import fit_double_decay, parabolic_peak, partial_envelope

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)

MAX_MODES = 8
SNR_DB = 18.0          # peak must beat the local median floor by this much
REL_FLOOR_DB = -32.0   # and be within this of the strongest mode
# A tau=8 ms mode is a ~100 Hz-wide resonance: peaks closer than ~10% are
# one physical mode group. The 60-band benchmark spectrogram can't resolve
# sub-band structure at these frequencies either — one sine per group.
MIN_SEP_REL = 0.10     # minimum separation between picked modes (relative)
MIN_SEP_HZ = 100.0

THUMP_WIN_S = 0.06     # attack metric: max of band median over t < this
BED_LO_S, BED_HI_S = 0.10, 0.30
# bed t60 from the LATE slope only: the early region mixes the fast mode
# decay into the slope and underestimates the room-tail t60
SLOPE_LO_S, SLOPE_HI_S = 0.12, 0.35


def find_modes(x: np.ndarray, sr: int, fmin: float = 200.0,
               fmax: float = 12000.0) -> list[dict]:
    """Spectral peaks of a struck idiophone: greedy strongest-first picking
    with SNR + relative-level gates and a minimum separation.

    Returns [{"freq", "amp"}] sorted by frequency, amp normalized to the
    strongest mode."""
    seg = x[: int(0.35 * sr)]
    w = get_window("hann", len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg) * 4)))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    binw = fax[1]

    def noise_floor(f):
        lo = max(1, int((f * 0.75) / binw))
        hi = min(len(spec) - 1, int((f * 1.3) / binw))
        return np.median(spec[lo:hi]) if hi > lo else spec.max() * 1e-9

    s = spec.copy()
    s[(fax < fmin) | (fax > fmax)] = 0
    smax = s.max()
    modes = []
    for _ in range(MAX_MODES * 3):
        if len(modes) >= MAX_MODES:
            break
        k = int(np.argmax(s))
        if s[k] <= 0 or s[k] < smax * 10 ** (REL_FLOOR_DB / 20):
            break
        d, pk = parabolic_peak(spec, k)
        f = (k + d) * binw
        sep = max(MIN_SEP_HZ, MIN_SEP_REL * f)
        lo, hi = max(0, int((f - sep) / binw)), int((f + sep) / binw)
        s[lo:hi] = 0
        if pk < noise_floor(f) * 10 ** (SNR_DB / 20):
            continue
        modes.append({"freq": float(f), "amp": float(pk)})
    if not modes:
        return []
    amax = max(m["amp"] for m in modes)
    for m in modes:
        m["amp"] /= amax
    return sorted(modes, key=lambda m: m["freq"])


def bed_thump_profile(x: np.ndarray, sr: int,
                      mode_freqs: list[float]) -> dict:
    """Short-event adaptation of the piano's broadband profile: per log
    band, attack max (t < 0.06 s) and short bed (0.10-0.30 s) of the median
    STFT magnitude across non-mode bins."""
    nper = int(STFT_WIN_S * sr)
    nover = nper - int(STFT_HOP_S * sr)
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
    A = np.abs(Z)
    binw = f[1] - f[0]

    pf = np.asarray(mode_freqs, float)
    if len(pf):
        dist = np.min(np.abs(f[:, None] - pf[None, :]), axis=1)
    else:
        dist = np.full(len(f), 1e9)
    guard = np.maximum(1.5 * binw, 0.05 * np.where(len(pf) > 0, pf.min(), 1e9))
    non_mode = dist > guard

    thump_sel = t < THUMP_WIN_S
    bed_sel = (t >= BED_LO_S) & (t <= BED_HI_S)
    slope_sel = (t >= SLOPE_LO_S) & (t <= SLOPE_HI_S)

    thump_db, thump_tau, bed_db, bed_t60 = [], [], [], []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1]) & non_mode
        # 46 ms window -> ~22 Hz bins: the lowest bands hold only 2 bins
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
        # per-band click decay: dB slope from the attack peak to 0.12 s
        # (the reference click's broadband tail decays 5-10x slower than a
        # fixed 10 ms thump; early room reflections live here)
        k0 = int(np.argmax(med[thump_sel])) if thump_sel.any() else 0
        tsel = (t >= t[k0]) & (t <= 0.12)
        if tsel.sum() > 4:
            ts = t[tsel]
            ds = 20 * np.log10(med[tsel] + 1e-12)
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            slope = coef[0]
            tau = -8.686 / slope if slope < -30.0 else 0.10
            thump_tau.append(round(float(np.clip(tau, 0.004, 0.10)), 4))
        else:
            thump_tau.append(None)
        if slope_sel.sum() > 5:
            ts = t[slope_sel]
            ds = 20 * np.log10(med[slope_sel] + 1e-12)
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            slope = coef[0]
            t60 = 60.0 / -slope if slope < -1.0 else 30.0
            bed_t60.append(round(float(np.clip(t60, 0.05, 30.0)), 3))
        else:
            bed_t60.append(None)
    return {"thump_db": thump_db, "thump_tau": thump_tau,
            "bed_db": bed_db, "bed_t60": bed_t60,
            "bed_anchor_s": round(0.5 * (BED_LO_S + BED_HI_S), 2)}


def analyze_note(path: str, note: str) -> dict:
    """Full parametric analysis of one woodblock hit."""
    x, sr = load_mono(path)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak_abs = float(np.max(np.abs(x)) + 1e-20)

    modes = find_modes(xo, sr)
    results = []
    for i, m in enumerate(modes):
        freq = m["freq"]
        # window: ~6 ms — passband wide enough (+-74 Hz at -3 dB) to read
        # the whole mode group's energy once; neighbors are >=10% away
        win = max(8, int(sr / 160.0))
        t, env = partial_envelope(xo, sr, freq, hop=0.001, win_samples=win)
        # co-located noise probe halfway to the next mode (or +7% for the
        # last one) measures the broadband floor under this mode
        if i + 1 < len(modes):
            probe_f = 0.5 * (freq + modes[i + 1]["freq"])
        else:
            probe_f = freq * 1.12
        _, env_noise = partial_envelope(xo, sr, probe_f, hop=0.001,
                                        win_samples=win)
        noise_med = float(np.median(env_noise))
        entry = {"n": i + 1, "freq": freq, "amp": m["amp"]}
        valid = env > 1.8 * env_noise
        # dominant mode: never mask (it defines the note)
        if m["amp"] >= 0.999:
            valid = np.ones(len(env), bool)
        if valid.sum() >= 10:
            fit = fit_double_decay(t[valid], env[valid], floor_db=-55.0)
            if fit is not None:
                # percussion guard: the t=0 extrapolation must stay anchored
                # to the measured envelope peak (tau ~ anchor time makes the
                # e-folding correction explosive; the piano never hits this
                # because its taus are 100x the anchor)
                env_max = float(env.max())
                a_fast = min(fit.a_fast, 2.2 * env_max)
                a_slow = min(fit.a_slow, 1.1 * env_max)
                entry.update({
                    "a_fast": a_fast / peak_abs, "tau_fast": fit.tau_fast,
                    "a_slow": a_slow / peak_abs, "tau_slow": fit.tau_slow,
                    "fit_rmse_db": fit.rmse_db,
                    "snr": float(env.max() / (noise_med + 1e-20)),
                })
        results.append(entry)

    profile = bed_thump_profile(xo, sr, [m["freq"] for m in modes])

    # loudness envelope at 2 ms hop (short event needs the resolution)
    hop = int(0.002 * sr)
    nfr = len(xo) // hop
    fr = xo[: nfr * hop].reshape(nfr, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)

    seg = xo[: int(0.06 * sr)]
    w = get_window("hann", len(seg))
    mag = np.abs(np.fft.rfft(seg * w))
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    centroid = float((mag * fax).sum() / (mag.sum() + 1e-20))

    f0 = max(modes, key=lambda m: m["amp"])["freq"] if modes else 0.0
    return {
        "note": note,
        "sr": sr,
        "duration": len(x) / sr,
        "onset_s": onset / sr,
        "f0": f0,
        "n_modes": len(results),
        "peak_abs": peak_abs,
        "rms_max": float(rms.max()),
        "centroid_60ms": centroid,
        "thump_db": profile["thump_db"],
        "thump_tau": profile["thump_tau"],
        "bed_db": profile["bed_db"],
        "bed_t60": profile["bed_t60"],
        "bed_anchor_s": profile["bed_anchor_s"],
        "modes": results,
        "rms_env_hop_s": 0.002,
        "rms_env_db": [round(float(20 * np.log10(v / (rms.max() + 1e-20) + 1e-12)), 2)
                       for v in rms[:500]],
    }


def analyze_to_json(path: str, note: str, out_path: str) -> dict:
    res = analyze_note(path, note)
    with open(out_path, "w") as f:
        json.dump(res, f)
    return res
