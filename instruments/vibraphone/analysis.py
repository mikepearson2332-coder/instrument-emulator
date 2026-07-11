"""Analysis of vibraphone recordings: bar-mode finding + decay fitting.

A vibraphone note is a few far-apart modes (tuned ≈ 1:4:10 plus untuned
higher modes), the fundamental ringing 10-30 s (anechoic reference — no
room bed), overtones dying in 0.5-3 s, and a soft mallet thud. Compared to
the woodblock analysis: modes are widely separated (no cluster-merging
problem), decays are long (10 ms hop, low floor, full-length fits), and f0
is pinned near the nominal note frequency (tuned instrument, ≈A442).
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import stft, get_window

from lab.audio import find_onset, load_mono
from lab.metrics import STFT_HOP_S, STFT_WIN_S
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import fit_double_decay, parabolic_peak, partial_envelope

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)


def load_hp(path: str) -> tuple[np.ndarray, int]:
    """Load mono + 60 Hz high-pass. The anechoic chamber recordings carry
    heavy infrasound rumble (2-45 Hz, up to 26 dB ABOVE the note on pp
    takes) that corrupts peak/RMS calibration and floods the low bands.
    Lowest bar is C3 (131 Hz): an order-6 80 Hz HP costs it -0.006 dB but
    takes the 43 Hz rumble down another ~30 dB (order-4 at 60 Hz left it
    at -30 dB rel peak — still above the benchmark floor).
    Used by BOTH analysis and benchmark — measurement conventions match."""
    from scipy.signal import butter, sosfilt

    x, sr = load_mono(path)
    sos = butter(6, 80.0, btype="highpass", fs=sr, output="sos")
    return sosfilt(sos, x), sr

MAX_MODES = 10
SNR_DB = 15.0
REL_FLOOR_DB = -55.0   # fundamental dominates a 1 s window; overtones sit low
MIN_SEP_REL = 0.06

THUMP_WIN_S = 0.12
BED_LO_S, BED_HI_S = 0.8, 3.5
SLOPE_LO_S, SLOPE_HI_S = 0.5, 5.0


def find_modes(x: np.ndarray, sr: int, f0_nominal: float,
               fmax: float = 12000.0,
               fixed: list[float] | None = None) -> tuple[float, list[dict]]:
    """Spectral peaks of the first second; f0 = strongest peak within ±6%
    of nominal. Returns (f0, modes sorted by freq, amp normalized).

    `fixed`: measure amplitudes at these known mode frequencies instead of
    detecting peaks — soft (pp) strikes put overtones under the detection
    gates, but the bar's modes are at the same frequencies at every
    dynamic, so the loud layer's mode list anchors the soft layers."""
    seg = x[: int(1.0 * sr)]
    w = get_window("hann", len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg) * 4)))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    binw = fax[1]

    def noise_floor(f):
        lo = max(1, int((f * 0.8) / binw))
        hi = min(len(spec) - 1, int((f * 1.25) / binw))
        return np.median(spec[lo:hi]) if hi > lo else spec.max() * 1e-9

    # f0: strongest credible peak near nominal
    lo = int(f0_nominal * 0.94 / binw)
    hi = int(f0_nominal * 1.065 / binw)
    k = lo + int(np.argmax(spec[lo:hi]))
    d, _ = parabolic_peak(spec, k)
    f0 = (k + d) * binw

    if fixed is not None:
        modes = []
        for f in fixed:
            a = max(1, int((f * 0.99) / binw))
            b = min(len(spec) - 1, int((f * 1.01) / binw))
            if b <= a:
                continue
            k = a + int(np.argmax(spec[a:b]))
            d, pk = parabolic_peak(spec, k)
            modes.append({"freq": float((k + d) * binw), "amp": float(pk)})
        if not modes:
            return float(f0), []
        amax = max(m["amp"] for m in modes)
        for m in modes:
            m["amp"] /= amax
        return float(f0), sorted(modes, key=lambda m: m["freq"])

    s = spec.copy()
    s[(fax < f0 * 0.9) | (fax > fmax)] = 0
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
        sep = max(MIN_SEP_REL * f, 30.0)
        a, b = max(0, int((f - sep) / binw)), int((f + sep) / binw)
        s[a:b] = 0
        if pk < noise_floor(f) * 10 ** (SNR_DB / 20):
            continue
        modes.append({"freq": float(f), "amp": float(pk)})
    if not modes:
        return f0, []
    amax = max(m["amp"] for m in modes)
    for m in modes:
        m["amp"] /= amax
    return float(f0), sorted(modes, key=lambda m: m["freq"])


def bed_thump_profile(x: np.ndarray, sr: int,
                      mode_freqs: list[float]) -> dict:
    """Piano-style broadband profile + per-band click decay (woodblock
    convention). Anechoic reference: bed is expected near the noise floor."""
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
    guard = max(1.5 * binw, 0.04 * (pf.min() if len(pf) else 1e9))
    non_mode = dist > guard

    T = t[-1] if len(t) else 0.0
    thump_sel = t < THUMP_WIN_S
    bed_sel = (t >= BED_LO_S) & (t <= min(BED_HI_S, 0.8 * T))
    slope_sel = (t >= SLOPE_LO_S) & (t <= min(SLOPE_HI_S, 0.9 * T))

    thump_db, thump_tau, bed_db, bed_t60 = [], [], [], []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1]) & non_mode
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
    return {"thump_db": thump_db, "thump_tau": thump_tau,
            "bed_db": bed_db, "bed_t60": bed_t60,
            "bed_anchor_s": round(0.5 * (BED_LO_S + BED_HI_S), 2)}


def analyze_note(path: str, note: str,
                 fixed_modes: list[float] | None = None) -> dict:
    x, sr = load_hp(path)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak_abs = float(np.max(np.abs(x)) + 1e-20)
    f0_nom = midi_to_freq(name_to_midi(note))

    f0, modes = find_modes(xo, sr, f0_nom, fixed=fixed_modes)
    results = []
    for i, m in enumerate(modes):
        freq = m["freq"]
        # 20 ms window: ±22 Hz passband; modes are >= 3 f0 apart
        win = max(16, int(sr / 50.0))
        t, env = partial_envelope(xo, sr, freq, hop=0.010, win_samples=win)
        if i + 1 < len(modes):
            probe_f = 0.5 * (freq + modes[i + 1]["freq"])
        else:
            probe_f = freq * 1.12
        _, env_noise = partial_envelope(xo, sr, probe_f, hop=0.010,
                                        win_samples=win)
        noise_med = float(np.median(env_noise))
        entry = {"n": i + 1, "freq": freq, "amp": m["amp"]}
        valid = env > 2.0 * env_noise
        if abs(freq - f0) < 0.03 * f0:  # the fundamental: never mask
            valid = np.ones(len(env), bool)
        # a struck bar's envelope peaks at the attack; a peak in the back
        # half means the demod picked up trailing junk (handling noise,
        # next-note bleed) — reject rather than fit garbage
        if valid.sum() >= 12 and int(np.argmax(env)) > 0.35 * len(env):
            valid = np.zeros(len(env), bool)
        if valid.sum() >= 12:
            # adaptive floor: stay ~8 dB above the co-located noise probe,
            # or the slow stage latches onto the flat noise tail (pp takes
            # put the recording floor at only ~-58 dB rel peak)
            floor = max(-70.0, 20 * math.log10(
                2.5 * noise_med / (env.max() + 1e-20) + 1e-12))
            fit = fit_double_decay(t[valid], env[valid], floor_db=floor)
            if fit is not None:
                env_max = float(env.max())
                a_fast = min(fit.a_fast, 2.2 * env_max)
                a_slow = min(fit.a_slow, 1.5 * env_max)
                entry.update({
                    "a_fast": a_fast / peak_abs, "tau_fast": fit.tau_fast,
                    "a_slow": a_slow / peak_abs,
                    "tau_slow": min(fit.tau_slow, 60.0),
                    "fit_rmse_db": fit.rmse_db,
                    "snr": float(env.max() / (noise_med + 1e-20)),
                })
        results.append(entry)

    profile = bed_thump_profile(xo, sr, [m["freq"] for m in modes])

    hop = int(0.010 * sr)
    nfr = len(xo) // hop
    fr = xo[: nfr * hop].reshape(nfr, hop)
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)

    seg = xo[: int(0.3 * sr)]
    w = get_window("hann", len(seg))
    mag = np.abs(np.fft.rfft(seg * w))
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    centroid = float((mag * fax).sum() / (mag.sum() + 1e-20))

    return {
        "note": note,
        "midi": name_to_midi(note),
        "sr": sr,
        "duration": len(x) / sr,
        "onset_s": onset / sr,
        "f0_nominal": f0_nom,
        "f0": f0,
        "n_modes": len(results),
        "peak_abs": peak_abs,
        "rms_max": float(rms.max()),
        "centroid_300ms": centroid,
        "thump_db": profile["thump_db"],
        "thump_tau": profile["thump_tau"],
        "bed_db": profile["bed_db"],
        "bed_t60": profile["bed_t60"],
        "bed_anchor_s": profile["bed_anchor_s"],
        "modes": results,
        "rms_env_hop_s": 0.010,
        "rms_env_db": [round(float(20 * np.log10(v / (rms.max() + 1e-20) + 1e-12)), 2)
                       for v in rms[:1000]],
    }


def analyze_to_json(path: str, note: str, out_path: str,
                    fixed_modes: list[float] | None = None) -> dict:
    res = analyze_note(path, note, fixed_modes=fixed_modes)
    with open(out_path, "w") as f:
        json.dump(res, f)
    return res


def measure_damper_fade(dampen_dir: str) -> float:
    """Median exponential fade time from the pedal-damped takes: fit the
    f0 envelope's decay from its peak. The damped decay (<0.5 s) is much
    faster than the natural ring, so the fit is dominated by the felt."""
    import glob
    import os

    taus = []
    for p in sorted(glob.glob(os.path.join(dampen_dir, "*.flac"))):
        note = os.path.basename(p)[:-5]
        try:
            x, sr = load_hp(p)
            onset = find_onset(x, sr)
            xo = x[onset:]
            f0_nom = midi_to_freq(name_to_midi(note))
            f0, modes = find_modes(xo, sr, f0_nom)
            win = max(16, int(sr / 50.0))
            t, env = partial_envelope(xo[: int(3.0 * sr)], sr, f0,
                                      hop=0.005, win_samples=win)
            i0 = int(np.argmax(env))
            db = 20 * np.log10(env / env[i0] + 1e-12)
            # fit the fall from -5 dB to -40 dB after the peak
            sel = (np.arange(len(db)) > i0) & (db < -5) & (db > -40)
            if sel.sum() < 6:
                continue
            ts, ds = t[sel], db[sel]
            A_ = np.stack([ts, np.ones_like(ts)], axis=1)
            coef, *_ = np.linalg.lstsq(A_, ds, rcond=None)
            if coef[0] < -20:
                taus.append(-8.686 / coef[0])
        except Exception:
            continue
    return float(np.median(taus)) if taus else 0.15
