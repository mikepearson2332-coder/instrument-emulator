"""Analysis of bowed string-section sustains (VSCO-2-CE).

A sustained ensemble note is measured as: a steady harmonic amplitude
table (body formants baked in), a per-band bow-noise bed (same scipy
STFT median convention as the modal bed — the engine self-calibrates
against it), a macro envelope (rise, sustain undulation depth/rate,
two-stage release via fit_double_decay), and vibrato AM (rate + depth
from the strongest low harmonic). Ensemble detune spread and vibrato
FM depth are NOT robustly measurable from section recordings (vibrato
sidebands and player spread smear together) — they are config-level
parameters fitted against the modulation-spectrum benchmark.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import stft, get_window

from lab.audio import find_onset, load_mono
from lab.notes import midi_to_freq, name_to_midi
from lab.partials import fit_double_decay
from lab.sustained import BAND_EDGES, NOISE_HOP_S, NOISE_WIN_S

MAX_HARM = 40


def rms_env(x, sr, hop_s=0.01):
    hop = int(hop_s * sr)
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    return np.sqrt((fr ** 2).mean(axis=1) + 1e-20)


def envelope_marks(x, sr):
    """(t_rise_end, t_sus_end, rise_s) from a SMOOTHED (0.3 s) RMS
    envelope, anchored to the median sustain level — anchoring to the
    max makes the marks hostage to whichever undulation peak the
    (stochastic) realization happens to have."""
    from scipy.ndimage import uniform_filter1d

    env = uniform_filter1d(rms_env(x, sr), 31)
    t = np.arange(len(env)) * 0.01
    occ = env[env > env.max() * 0.1]
    lvl = float(np.percentile(occ, 60)) if len(occ) else float(env.max())
    edb = 20 * np.log10(env / (lvl + 1e-20) + 1e-12)
    above20 = np.nonzero(edb > -20)[0]
    above3 = np.nonzero(edb > -3)[0]
    last6 = np.nonzero(edb > -6)[0]
    if not len(above3) or not len(last6):
        return 0.1, t[-1], 0.3
    t_on = t[above20[0]] if len(above20) else 0.0
    rise = max(t[above3[0]] - t_on, 0.02)
    return float(t[above3[0]]), float(t[last6[-1]]), float(rise)


def steady_spectrum(x, sr, f0n, t0, t1):
    """(f0, harm[{n, db}], strongest_lin) over the sustain window."""
    seg = x[int(t0 * sr): int(t1 * sr)]
    w = get_window("hann", len(seg))
    nfft = int(2 ** math.ceil(math.log2(len(seg))))
    spec = np.abs(np.fft.rfft(seg * w, nfft))
    fax = np.fft.rfftfreq(nfft, 1 / sr)
    binw = fax[1]
    lo, hi = int(f0n * 0.94 / binw), int(f0n * 1.06 / binw)
    if hi <= lo + 1:
        return f0n, [], 1.0
    k0 = lo + int(np.argmax(spec[lo:hi]))
    f0 = k0 * binw
    harm = []
    amps = []
    for n in range(1, MAX_HARM + 1):
        fc = n * f0
        if fc > min(16000.0, fax[-1]):
            break
        l = int((fc - 0.35 * f0) / binw)
        h = int((fc + 0.35 * f0) / binw)
        if h <= l + 2:
            break
        amps.append(float(spec[l + int(np.argmax(spec[l:h]))]))
        harm.append(n)
    amax = max(amps) if amps else 1.0
    out = [{"n": n, "db": round(20 * math.log10(a / amax + 1e-12), 2)}
           for n, a in zip(harm, amps)]
    out = [h for h in out if h["db"] > -70.0]
    return float(f0), out, float(amax)


def noise_bed(x, sr, f0, harm_ns, t0, t1):
    """Per-band median STFT magnitude (dB) of NON-harmonic bins over the
    sustain — 0.2 s windows (the modal 46 ms convention cannot resolve
    non-harmonic bins between low-string harmonics), synth
    self-calibrates through the identical metric (lab.sustained)."""
    seg = x[int(t0 * sr): int(t1 * sr)]
    nper = int(NOISE_WIN_S * sr)
    nover = nper - int(NOISE_HOP_S * sr)
    f, t, Z = stft(seg, sr, nperseg=nper, noverlap=nover, padded=False)
    A = np.abs(Z)
    pf = np.array([n * f0 for n in harm_ns], float)
    if len(pf):
        dist = np.min(np.abs(f[:, None] - pf[None, :]), axis=1)
    else:
        dist = np.full(len(f), 1e9)
    guard = max(1.5 * (f[1] - f[0]), 0.12 * f0)
    non_harm = dist > guard
    # above the last tracked harmonic everything is noise
    fmax_h = (max(harm_ns) + 0.5) * f0 if harm_ns else 0.0
    non_harm |= f > fmax_h
    out = []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1]) & non_harm
        if sel.sum() < 2:
            out.append(None)
            continue
        med = float(np.median(A[sel]))
        out.append(round(20 * math.log10(med + 1e-12), 2))
    return out


def sustain_modulation(x, sr, t0, t1):
    """(und_db, und_hz, vib_hz, vib_am_db) from the sustain envelope."""
    env = rms_env(x, sr, 0.005)
    i0, i1 = int(t0 / 0.005), int(t1 / 0.005)
    sus = env[i0:i1]
    if len(sus) < 200:
        return 1.0, 0.5, 5.0, 0.5
    d = 20 * np.log10(sus / (sus.mean() + 1e-20) + 1e-12)
    d = d - d.mean()
    w = np.hanning(len(d))
    spec = np.abs(np.fft.rfft(d * w))
    frq = np.fft.rfftfreq(len(d), 0.005)
    # coherent amplitude of a sine in dB-domain: 2|X|/sum(w)
    amp = 2.0 * spec / w.sum()
    slow = (frq > 0.15) & (frq < 3.0)
    vib = (frq >= 3.0) & (frq < 9.0)
    und_hz = float(frq[slow][np.argmax(spec[slow])]) if slow.any() else 0.5
    lo_d = d[np.abs(d) < 20]
    und_db = float(np.std(lo_d)) if len(lo_d) else 1.0
    if vib.any():
        kv = np.argmax(spec[vib])
        vib_hz = float(frq[vib][kv])
        vib_am_db = float(amp[vib][kv])
    else:
        vib_hz, vib_am_db = 5.0, 0.5
    return und_db, und_hz, vib_hz, vib_am_db


def release_fit(x, sr, t_sus_end):
    """Two-stage release from the envelope after sustain end."""
    env = rms_env(x, sr, 0.005)
    i0 = int(t_sus_end / 0.005)
    tail = env[i0:]
    if len(tail) < 40:
        return 0.3, 0.0, 1.0
    t = np.arange(len(tail)) * 0.005
    fit = fit_double_decay(t, tail, floor_db=-45.0)
    if fit is None:
        return 0.3, 0.0, 1.0
    a1 = fit.a_fast
    a2 = fit.a_slow
    rel_s = float(min(fit.tau_fast, 2.0))
    tail_s = float(min(fit.tau_slow, 6.0))
    rem = float(a2 / (a1 + a2 + 1e-20))
    return rel_s, rem, tail_s


def analyze_note(path: str, note: str) -> dict:
    x, sr = load_mono(path)
    onset = find_onset(x, sr)
    xo = x[onset:]
    peak_abs = float(np.max(np.abs(x)) + 1e-20)
    midi = name_to_midi(note)
    f0n = midi_to_freq(midi)

    t_rise_end, t_sus_end, rise_s = envelope_marks(xo, sr)
    span = t_sus_end - t_rise_end
    s0 = t_rise_end + 0.15 * span
    s1 = t_rise_end + 0.85 * span

    f0, harm, _ = steady_spectrum(xo, sr, f0n, s0, s1)
    bed = noise_bed(xo, sr, f0, [h["n"] for h in harm], s0, s1)
    und_db, und_hz, vib_hz, vib_am_db = sustain_modulation(xo, sr, s0, s1)
    rel_s, rel_rem, rel_tail_s = release_fit(xo, sr, t_sus_end)

    env = rms_env(xo, sr)
    i0, i1 = int(s0 / 0.01), int(s1 / 0.01)
    rms_ss = float(np.median(env[i0:i1])) if i1 > i0 + 2 else float(env.max())

    return {
        "note": note, "midi": midi, "sr": sr,
        "duration": len(x) / sr, "onset_s": onset / sr,
        "f0_nominal": f0n, "f0": f0,
        "peak_abs": peak_abs, "rms_ss": rms_ss,
        "rise_s": rise_s,
        "t_rise_end": t_rise_end, "t_sus_end": t_sus_end,
        "und_db": round(und_db, 3), "und_hz": round(und_hz, 3),
        "vib_hz": round(vib_hz, 3), "vib_am_db": round(vib_am_db, 3),
        "rel_s": round(rel_s, 4), "rel_remnant": round(rel_rem, 4),
        "rel_tail_s": round(rel_tail_s, 3),
        "harm": harm,
        "noise_db": bed,
    }


def analyze_to_json(path: str, note: str, out_path: str) -> dict:
    res = analyze_note(path, note)
    with open(out_path, "w") as f:
        json.dump(res, f)
    return res
