"""Partial tracking, per-partial envelopes, and decay fitting.

Shared machinery for the modal engine family (struck/plucked strings,
mallets, bells, percussion): anything whose sound is a sum of decaying
resonances. `find_partials` assumes an inharmonic-string series
f_n = n·f0·sqrt(1 + B·n²); instruments with non-string mode series
(bells, bars) need their own mode finder but reuse the envelope/decay code.

Moved verbatim from the piano lab (see instruments/piano/DEVLOG.md for the
measurement lessons baked in here).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.signal import get_window

from .audio import find_onset


def parabolic_peak(mag: np.ndarray, k: int) -> tuple[float, float]:
    """Parabolic interpolation around bin k. Returns (bin_offset, peak_mag)."""
    if k <= 0 or k >= len(mag) - 1:
        return 0.0, mag[k]
    a, b, c = mag[k - 1], mag[k], mag[k + 1]
    denom = a - 2 * b + c
    if abs(denom) < 1e-30:
        return 0.0, b
    d = 0.5 * (a - c) / denom
    d = float(np.clip(d, -0.5, 0.5))
    peak = b - 0.25 * (a - c) * d
    return d, peak


def find_partials(
    x: np.ndarray,
    sr: int,
    f0_nominal: float,
    max_partials: int = 80,
    fmax: float | None = None,
    snr_db: float = 12.0,
) -> tuple[float, float, list[dict]]:
    """Track partials of an inharmonic string tone.

    Iteratively fits f0 and B in f_n = n f0 sqrt(1 + B n^2), locating peaks
    within a search window around each predicted partial.

    Returns (f0, B, partials) where each partial is
    {"n": int, "freq": Hz, "amp": linear peak magnitude (relative)}.
    """
    if fmax is None:
        fmax = min(sr / 2 * 0.95, 20000.0)

    # Analysis segment: from just after onset, long enough for resolution
    # but short enough that treble notes haven't fully decayed.
    onset = find_onset(x, sr)
    seg_len = int(min(len(x) - onset, max(0.3 * sr, min(2.0 * sr, 96 * sr / f0_nominal))))
    seg = x[onset : onset + seg_len]
    w = get_window("hann", len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg) * 4)))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    binw = sr / nfft

    def noise_floor(f):
        lo = max(1, int((f * 0.9) / binw))
        hi = min(len(spec) - 1, int((f * 1.1) / binw))
        if hi <= lo:
            return spec.max() * 1e-9
        return np.median(spec[lo:hi])

    def measure_peak(fpred: float, half: float):
        lo = int((fpred - half) / binw)
        hi = int((fpred + half) / binw)
        if lo < 1 or hi >= len(spec) - 1 or hi <= lo:
            return None
        k = lo + int(np.argmax(spec[lo:hi]))
        d, pk = parabolic_peak(spec, k)
        fmeas = (k + d) * binw
        nf = noise_floor(fpred)
        if pk < nf * 10 ** (snr_db / 20):
            return None
        # reject peaks clamped at the window edge (likely a neighbor's skirt)
        if k <= lo or k >= hi - 1:
            return None
        return float(fmeas), float(pk)

    def fit_f0_B(ns, fs, f0_init, B_init):
        """Weighted LS of (f_n/n)^2 = f0^2 + f0^2 B n^2 with outlier rejection."""
        f0_, B_ = f0_init, B_init
        ns = np.asarray(ns, float)
        fs = np.asarray(fs, float)
        keep = np.ones(len(ns), bool)
        for _ in range(4):
            if keep.sum() < 3:
                break
            narr, farr = ns[keep], fs[keep]
            y = (farr / narr) ** 2
            X = np.stack([np.ones_like(narr), narr ** 2], axis=1)
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            f0sq, f0sqB = coef
            if f0sq <= 0:
                break
            f0_ = math.sqrt(f0sq)
            B_ = max(0.0, f0sqB / f0sq)
            pred = ns * f0_ * np.sqrt(1 + B_ * ns ** 2)
            cents = 1200 * np.log2(np.maximum(fs, 1e-9) / np.maximum(pred, 1e-9))
            new_keep = np.abs(cents) < 25.0
            if new_keep.sum() < 3 or (new_keep == keep).all():
                keep = new_keep if new_keep.sum() >= 3 else keep
                break
            keep = new_keep
        return f0_, B_

    # --- phase 0: refine f0 by the strongest credible peak within ±8% of
    # nominal (robust against sparse-partial fit collapse in the top octave)
    f0, B = f0_nominal, 0.0
    f0_probe = None
    lo = int(f0_nominal * 0.92 / binw)
    hi = int(f0_nominal * 1.085 / binw)
    if 1 <= lo < hi < len(spec) - 1:
        k = lo + int(np.argmax(spec[lo:hi]))
        d, pk = parabolic_peak(spec, k)
        if pk > noise_floor(f0_nominal) * 10 ** (snr_db / 20):
            f0 = f0_probe = (k + d) * binw

    # --- phase 1: low partials with near-harmonic windows -> initial f0, B
    for _ in range(3):
        ns, fs = [], []
        for n in range(1, min(9, max_partials + 1)):
            fpred = n * f0 * math.sqrt(1 + B * n * n)
            if fpred > fmax:
                break
            half = max(3 * binw, f0 * 0.25)
            got = measure_peak(fpred, half)
            if got is None:
                continue
            ns.append(n)
            fs.append(got[0])
        if len(ns) >= 3:
            f0, B = fit_f0_B(ns, fs, f0, B)

    # --- phase 2: extend upward progressively, refitting as we go
    partials = []
    ns_all, fs_all = [], []
    for n in range(1, max_partials + 1):
        fpred = n * f0 * math.sqrt(1 + B * n * n)
        if fpred > fmax:
            break
        half = max(3 * binw, min(f0 * 0.35, fpred * 0.012 + f0 * 0.08))
        got = measure_peak(fpred, half)
        if got is None:
            continue
        fmeas, pk = got
        partials.append({"n": n, "freq": fmeas, "amp": pk})
        ns_all.append(n)
        fs_all.append(fmeas)
        if len(ns_all) >= 5 and n % 4 == 0:
            f0, B = fit_f0_B(ns_all, fs_all, f0, B)
    if len(ns_all) >= 5:
        f0, B = fit_f0_B(ns_all, fs_all, f0, B)

    # sparse treble: too few partials for a free (f0, B) fit — pin f0 to the
    # phase-0 spectral probe and fit only B. Above ~1.2 kHz the unisons are
    # detuned enough (10-30 cents) that the free fit mislocks, so pin there
    # regardless of partial count.
    if f0_probe is not None and (len(partials) < 5 or f0_nominal > 1200.0):
        f0 = f0_probe
        ratios = [((p["freq"] / (p["n"] * f0)) ** 2 - 1) / p["n"] ** 2
                  for p in partials if p["n"] >= 2]
        B = max(0.0, float(np.median(ratios))) if ratios else 0.0

    # drop tracked partials that disagree badly with the final fit
    kept = []
    for p in partials:
        pred = p["n"] * f0 * math.sqrt(1 + B * p["n"] ** 2)
        if abs(1200 * math.log2(p["freq"] / pred)) < 35.0:
            kept.append(p)
    partials = kept
    # normalize amplitudes to the strongest partial
    if partials:
        amax = max(p["amp"] for p in partials)
        for p in partials:
            p["amp"] /= amax
    return f0, B, partials


# ------------------------------------------------------------ decay fitting

def partial_envelope(
    x: np.ndarray, sr: int, freq: float, hop: float = 0.010,
    bw: float = 30.0, win_samples: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Amplitude envelope of one partial via complex demodulation + lowpass.

    Returns (t, amp) sampled every `hop` seconds. The lowpass is a moving
    average of `win_samples` (or ~sr/bw) samples; a moving average of length
    k*sr/df has spectral nulls at every multiple of df/k, which callers use
    to null out neighboring partials exactly.
    """
    from scipy.ndimage import uniform_filter1d

    n = len(x)
    t = np.arange(n) / sr
    analytic = x * np.exp(-2j * np.pi * freq * t)
    win = win_samples if win_samples else max(1, int(sr / bw))
    win = max(1, min(win, n))
    smooth = (uniform_filter1d(analytic.real, win)
              + 1j * uniform_filter1d(analytic.imag, win))
    hop_n = max(1, int(hop * sr))
    idx = np.arange(0, n, hop_n)
    return idx / sr, 2.0 * np.abs(smooth[idx])


def envelope_window(sr: int, spacing: float, f0: float | None = None) -> int:
    """Moving-average length W = 2k/spacing seconds: its spectral nulls land
    exactly on every multiple of spacing/2 for ANY integer k (neighbors and
    mid-way noise probes are nulled).

    k trades smoothing against passband: bass/mid uses k = ceil(spacing/60)
    (narrow, ~1/30 s window). Treble unisons are detuned 10-30 cents
    (tens of Hz at 3-4.5 kHz) — a narrow window nulls the detuned string
    components themselves, so above 800 Hz pick k for a ±100+ Hz passband."""
    if f0 is not None and f0 > 800.0:
        k = max(1, int(spacing // 350.0))
    else:
        k = max(1, math.ceil(spacing / 60.0))
    return max(1, int(round(2 * k * sr / spacing)))


@dataclass
class DecayFit:
    a_fast: float
    tau_fast: float
    a_slow: float
    tau_slow: float
    rmse_db: float


def _refine_double_decay(tt: np.ndarray, dd: np.ndarray, fit: DecayFit,
                         peak: float, t_anchor: float) -> DecayFit:
    """Nonlinear refinement of the sum-of-two-exponentials in dB domain,
    seeded by the piecewise fit. Falls back to the seed on failure.

    NOTE: dead code by default (refine=False) — systematically inflates
    amplitudes on real piano data; kept as a worked example. See the piano
    DEVLOG ("what failed and must not be retried naively")."""
    import warnings
    from scipy.optimize import curve_fit, OptimizeWarning
    warnings.simplefilter("ignore", OptimizeWarning)

    def model(ts, la1, lt1, la2, lt2):
        a = np.exp(la1) * np.exp(-ts / np.exp(lt1)) \
            + np.exp(la2) * np.exp(-ts / np.exp(lt2))
        return 20 * np.log10(a + 1e-15)

    # seed: shift amplitudes back to the local anchor for the fit domain
    a1s = max(fit.a_fast * math.exp(-t_anchor / max(fit.tau_fast, 1e-3)), peak * 1e-6)
    a2s = max(fit.a_slow * math.exp(-t_anchor / max(fit.tau_slow, 1e-3)), peak * 1e-7)
    p0 = [math.log(a1s), math.log(max(fit.tau_fast, 1e-3)),
          math.log(a2s), math.log(max(fit.tau_slow, 1e-3))]
    try:
        popt, _ = curve_fit(model, tt, dd, p0=p0, maxfev=400)
        la1, lt1, la2, lt2 = popt
        a1, t1 = math.exp(la1), math.exp(lt1)
        a2, t2 = math.exp(la2), math.exp(lt2)
        if t1 > t2:
            a1, a2, t1, t2 = a2, a1, t2, t1
        if not (1e-4 < t1 < 200 and 1e-4 < t2 < 200):
            return fit
        resid = float(np.sqrt(((model(tt, *popt) - dd) ** 2).mean()))
        if resid > fit.rmse_db + 0.5:
            return fit
        # extrapolate to absolute t=0 (fit domain starts at t_anchor)
        cap = 3.0
        a1 = min(a1 * math.exp(min(t_anchor / t1, cap)), 2.5 * peak)
        a2 = min(a2 * math.exp(min(t_anchor / t2, cap)), 2.5 * peak)
        return DecayFit(a_fast=a1, tau_fast=t1, a_slow=a2, tau_slow=t2,
                        rmse_db=resid)
    except Exception:
        return fit


def fit_double_decay(t: np.ndarray, amp: np.ndarray, floor_db: float = -80.0,
                     refine: bool = False) -> DecayFit | None:
    """Fit amp(t) ≈ a_f e^{-t/tau_f} + a_s e^{-t/tau_s} on the region above
    the noise floor. Robust approach: piecewise linear fit in dB with a
    breakpoint search; convert slopes to time constants."""
    amp = np.asarray(amp, float)
    peak = amp.max()
    if peak <= 0:
        return None
    db = 20 * np.log10(amp / peak + 1e-12)
    # usable region: from the peak until it hits the floor for good
    i0 = int(np.argmax(amp))
    valid = np.nonzero(db[i0:] > floor_db)[0]
    if len(valid) < 8:
        return None
    i1 = i0 + valid[-1]
    tt = t[i0:i1] - t[i0]
    dd = db[i0:i1]
    if len(tt) < 8 or tt[-1] <= 0:
        return None

    def linfit(ts, ds):
        if len(ts) < 2:
            return 0.0, ds.mean() if len(ds) else 0.0, 0.0
        A = np.stack([ts, np.ones_like(ts)], axis=1)
        coef, res, *_ = np.linalg.lstsq(A, ds, rcond=None)
        pred = A @ coef
        rmse = float(np.sqrt(((ds - pred) ** 2).mean()))
        return coef[0], coef[1], rmse

    # single-line baseline
    s_all, b_all, r_all = linfit(tt, dd)
    best = (r_all, None)  # (rmse, breakpoint index)
    n = len(tt)
    for k in range(4, n - 4, max(1, n // 60)):
        s1, b1, r1 = linfit(tt[:k], dd[:k])
        s2, b2, r2 = linfit(tt[k:], dd[k:])
        rmse = (r1 * k + r2 * (n - k)) / n
        if rmse < best[0] - 1e-9:
            best = (rmse, k)

    def slope_to_tau(slope_db_per_s):
        # e^{-t/tau} -> -8.686/tau dB/s
        if slope_db_per_s >= -1e-3:
            return 100.0  # effectively no decay
        return -8.686 / slope_db_per_s

    # Fits are anchored at t[i0] (the kept-envelope peak). When the attack
    # region was masked out (noise-dominated), t[i0] > 0: extrapolate each
    # stage back to absolute t = 0 along its own decay (max 3 e-foldings).
    t_anchor = float(t[i0])

    def to_t0(a, tau):
        return a * math.exp(min(t_anchor / max(tau, 1e-3), 3.0))

    def single(slope, intercept, rmse):
        tau = slope_to_tau(slope)
        a = to_t0(min(peak * 10 ** (intercept / 20), 2 * peak), tau)
        return DecayFit(a_fast=float(a), tau_fast=float(tau),
                        a_slow=0.0, tau_slow=float(tau), rmse_db=float(rmse))

    def maybe_refine(base):
        if refine:
            return _refine_double_decay(tt, dd, base, peak, t_anchor)
        return base

    if best[1] is None:
        return maybe_refine(single(s_all, b_all, r_all))
    k = best[1]
    s1, b1, _ = linfit(tt[:k], dd[:k])
    s2, b2, _ = linfit(tt[k:], dd[k:])
    tau1, tau2 = slope_to_tau(s1), slope_to_tau(s2)
    # A sum of two decaying exponentials is convex in dB: the late stage must
    # be the slower one. Accelerating (concave) decay can't be represented —
    # use the single-line fit instead of extrapolating a bogus intercept.
    if tau2 <= tau1 * 1.05:
        return maybe_refine(single(s_all, b_all, r_all))
    a1 = to_t0(min(peak * 10 ** (b1 / 20), 2 * peak), tau1)
    a2 = to_t0(min(peak * 10 ** (b2 / 20), 2 * peak), tau2)
    base = DecayFit(a_fast=float(a1), tau_fast=float(tau1),
                    a_slow=float(a2), tau_slow=float(tau2), rmse_db=float(best[0]))
    return maybe_refine(base)
