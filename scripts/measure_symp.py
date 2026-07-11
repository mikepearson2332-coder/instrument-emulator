"""Extract the instrument's global sympathetic/body resonance lines and
measure per-note excitation levels.

Pass 1: peak-pick sustained spectral lines (1.0-2.5 s after onset) in every
sample; cluster across samples; keep lines present in >= 20% of samples
(these are instrument resonators, not note partials).
Pass 2: for every sample, demodulate each line -> level at anchor + t60.

Output: reference/symp.json
"""

import os
import sys
import json
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from scipy.ndimage import median_filter, maximum_filter

from pianomodel.notes import SALAMANDER_NOTES, SALAMANDER_VELS, name_to_midi, midi_to_freq
from pianomodel.analysis import load_mono, find_onset, partial_envelope

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "samples")
ANALYSIS = os.path.join(ROOT, "reference", "analysis")

FMIN, FMAX = 60.0, 8000.0
ANCHOR = 1.2  # s


def sample_names():
    for note in SALAMANDER_NOTES:
        for v in SALAMANDER_VELS:
            name = f"{note}v{v}"
            if os.path.exists(os.path.join(SAMPLES, f"{name}.flac")):
                yield name, note


def note_partial_freqs(name, note):
    """Predicted partial frequencies of the played note (to exclude)."""
    p = os.path.join(ANALYSIS, f"{name}.json")
    f0 = midi_to_freq(name_to_midi(note))
    B = 3e-4
    freqs = []
    if os.path.exists(p):
        with open(p) as f:
            a = json.load(f)
        f0, B = a["f0"], a["B"]
        freqs = [q["freq"] for q in a["partials"]]
    n = 1
    while True:
        fp = n * f0 * math.sqrt(1 + B * n * n)
        if fp > FMAX * 1.2:
            break
        freqs.append(fp)
        n += 1
    return freqs


def late_peaks(x, sr):
    seg = x[int(1.0 * sr): int(2.5 * sr)]
    if len(seg) < sr // 2:
        return []
    w = np.hanning(len(seg))
    spec = 20 * np.log10(np.abs(np.fft.rfft(seg * w)) + 1e-12)
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    sel = (fax > FMIN) & (fax < FMAX)
    s, f = spec[sel], fax[sel]
    locmed = median_filter(s, 201)
    ismax = (s == maximum_filter(s, 25)) & (s > locmed + 10)
    idx = np.nonzero(ismax)[0]
    idx = idx[np.argsort(-s[idx])][:50]
    return [(float(f[i]), float(s[i])) for i in idx]


def main():
    # ---- pass 1: collect candidate lines
    hits = []  # (freq, sample_index)
    names = list(sample_names())
    for si, (name, note) in enumerate(names):
        x, sr = load_mono(os.path.join(SAMPLES, f"{name}.flac"))
        x = x[find_onset(x, sr):]
        pf = note_partial_freqs(name, note)
        for freq, _lvl in late_peaks(x, sr):
            if min((abs(freq - q) / q for q in pf), default=1.0) < 0.04:
                continue  # the note's own partial
            hits.append((freq, si))
        if si % 20 == 0:
            print(f"pass1 {si}/{len(names)}", flush=True)

    hits.sort()
    lines = []
    used = np.zeros(len(hits), bool)
    freqs = np.array([h[0] for h in hits])
    for i in range(len(hits)):
        if used[i]:
            continue
        sel = np.abs(freqs - freqs[i]) < freqs[i] * 0.012
        members = [hits[j] for j in np.nonzero(sel)[0] if not used[j]]
        used |= sel
        n_samples = len(set(m[1] for m in members))
        if n_samples >= len(names) * 0.15:
            lines.append(float(np.median([m[0] for m in members])))
    lines = sorted(lines)
    print(f"global lines ({len(lines)}):", [round(l, 1) for l in lines])

    # ---- pass 2: per-sample levels
    win = None
    result = {"anchor_s": ANCHOR, "lines": [], "notes": {}}
    t60s = [[] for _ in lines]
    for name, note in names:
        x, sr = load_mono(os.path.join(SAMPLES, f"{name}.flac"))
        x = x[find_onset(x, sr):]
        win = int(0.15 * sr)
        pf = note_partial_freqs(name, note)
        levels = []
        for li, lf in enumerate(lines):
            if min((abs(lf - q) / q for q in pf), default=1.0) < 0.04:
                levels.append(None)  # masked by the note's own partial
                continue
            t, env = partial_envelope(x, sr, lf, win_samples=win)
            sel = (t >= 0.8) & (t <= min(2.5, t[-1] * 0.8))
            if sel.sum() < 5:
                levels.append(None)
                continue
            lvl = float(np.median(env[sel]))
            levels.append(round(20 * math.log10(lvl + 1e-12), 2))
            # t60 from slope 0.8..min(4, 0.9T)
            sel2 = (t >= 0.8) & (t <= min(4.0, t[-1] * 0.9))
            if sel2.sum() > 10:
                ts, ds = t[sel2], 20 * np.log10(env[sel2] + 1e-12)
                A = np.stack([ts, np.ones_like(ts)], axis=1)
                coef, *_ = np.linalg.lstsq(A, ds, rcond=None)
                if coef[0] < -1.0:
                    t60s[li].append(min(60.0, -60.0 / coef[0]))
        result["notes"][name] = levels

    for li, lf in enumerate(lines):
        t60 = float(np.median(t60s[li])) if t60s[li] else 8.0
        result["lines"].append({"freq": round(lf, 2), "t60": round(t60, 2)})

    out = os.path.join(ROOT, "reference", "symp.json")
    with open(out, "w") as f:
        json.dump(result, f)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
