"""Normalize VSCO-2-CE string-section sustains into the reference grid.

  python -m instruments.strings.normalize_raw

VSCO file names sit ~1 octave below sounding pitch (VCSL/koto
precedent) and ensembles blur f0, so every file's pitch is verified by
a harmonic-product spectrum over a mid-file window and snapped to the
nearest octave-shifted candidate of the named pitch. Output grid:
`reference/strings/samples/{sec}_{Note}{Octave}v{1|2}.flac` with
sec in {vln, vla, vc, cb} (cello/contrabass v3 -> v2; contrabass is
solo — no bass section exists in VSCO2-CE; SusNV kept as `cb_nv`).
"""

from __future__ import annotations

import math
import os
import re

import numpy as np
import soundfile as sf

from lab.notes import midi_to_freq, midi_to_name, name_to_midi

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "reference", "strings", "raw", "VSCO-2-CE", "Strings")
OUT = os.path.join(ROOT, "reference", "strings", "samples")

SETS = [
    ("vln", os.path.join("Violin Section", "susVib"),
     re.compile(r"VlnEns_susVib_([A-G]#?\d)_v(\d)\.wav$"), {1: 1, 2: 2}),
    ("vla", os.path.join("Viola Section", "susvib"),
     re.compile(r".*susvib_([A-G]#?\d)_v(\d)(?:_\d)?\.wav$"), {1: 1, 2: 2}),
    ("vc", os.path.join("Cello Section", "susvib"),
     re.compile(r".*susvib_([A-G]#?\d)_v(\d)(?:_\d)?\.wav$"), {1: 1, 3: 2}),
    ("cb", os.path.join("Solo Contrabass", "SusVib"),
     re.compile(r".*_([A-G]#?\d)_v(\d)(?:_rr\d|_\d)?\.wav$", re.IGNORECASE),
     {1: 1, 3: 2}),
    ("cb_nv", os.path.join("Solo Contrabass", "SusNV"),
     re.compile(r".*_([A-G]#?\d)_v(\d)(?:_rr\d|_\d)?\.wav$", re.IGNORECASE),
     {1: 1, 3: 2}),
]


def detect_f0(x: np.ndarray, sr: int, f_named: float) -> float:
    """Autocorrelation peak at a lag near f_named * 2^k, k in {0,1,2}.

    HPS mislocks an octave up on weak-fundamental low strings (violin
    low G); the ACF period survives both missing fundamentals and
    ensemble detune (players share the period, not the phase).
    """
    n0 = int(len(x) * 0.3)
    seg = x[n0: n0 + 4 * sr].astype(float)
    if len(seg) < sr:
        seg = x.astype(float)
    seg = seg - seg.mean()
    n = len(seg)
    nfft = int(2 ** math.ceil(math.log2(2 * n)))
    S = np.fft.rfft(seg, nfft)
    ac = np.fft.irfft(S * np.conj(S))[: n]
    ac = ac / (ac[0] + 1e-20)
    best_f, best_v = f_named, -1e18
    for k in (0, 1, 2):
        fc = f_named * 2 ** k
        lo = max(2, int(sr / (fc * 1.06)))
        hi = min(n - 2, int(sr / (fc * 0.94)))
        if hi <= lo:
            continue
        i = lo + int(np.argmax(ac[lo: hi]))
        if ac[i] > best_v:
            best_v, best_f = ac[i], sr / i
    return best_f


def main():
    os.makedirs(OUT, exist_ok=True)
    n_out = 0
    for sec, sub, pat, layer_map in SETS:
        d = os.path.join(RAW, sub)
        for fn in sorted(os.listdir(d)):
            m = pat.match(fn)
            if not m:
                print(f"  SKIP (name): {sub}\\{fn}")
                continue
            named, vraw = m.group(1), int(m.group(2))
            if vraw not in layer_map:
                print(f"  SKIP (layer): {sub}\\{fn}")
                continue
            layer = layer_map[vraw]
            x, sr = sf.read(os.path.join(d, fn), always_2d=True)
            mono = x.mean(axis=1)
            f_named = midi_to_freq(name_to_midi(named))
            f0 = detect_f0(mono, sr, f_named)
            midi = int(round(69 + 12 * math.log2(f0 / 440.0)))
            note = midi_to_name(midi)
            dev = 1200 * math.log2(f0 / midi_to_freq(midi))
            dst = f"{sec}_{note}v{layer}"
            path = os.path.join(OUT, f"{dst}.flac")
            if os.path.exists(path):
                dst += "_alt1"
                path = os.path.join(OUT, f"{dst}.flac")
            sf.write(path, x, sr)
            oct_shift = round(12 * math.log2(f0 / f_named)) // 12
            print(f"{fn:34s} -> {dst}.flac  f0={f0:7.1f} ({dev:+5.1f}c) "
                  f"[named {named}, +{oct_shift} oct] {len(x)/sr:5.1f}s")
            n_out += 1
    print(f"normalized {n_out} files")


if __name__ == "__main__":
    main()
