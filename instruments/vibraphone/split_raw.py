"""Split Iowa MIS multi-note range AIFFs into per-note FLACs.

  python -m instruments.vibraphone.split_raw

Each `Vibraphone.<art>.<dyn>.<range>.aif` holds a chromatic run of struck
notes, each ringing out before the next. Segmentation: RMS gate at -48 dB
of the file peak, gaps under 0.5 s bridged; each region is one note.
Pitch: FFT peak of the first 0.5 s constrained to the vibraphone range,
mapped to the nearest equal-tempered MIDI note.

Output: reference/vibraphone/samples/{Note}{Octave}v{layer}.flac
(sustain pp/mf/ff -> v1/v2/v3) and .../dampen/{Note}{Octave}.flac
(dampen.mf, used only to measure the damper fade).
"""

from __future__ import annotations

import glob
import os

import numpy as np
import soundfile as sf

from lab.notes import midi_to_name

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "reference", "vibraphone", "raw")
OUT = os.path.join(ROOT, "reference", "vibraphone", "samples")

DYN_TO_LAYER = {"pp": 1, "mf": 2, "ff": 3}
# MIS vibraphone is a 4-octave instrument, C3 (131 Hz) .. F6 (1397 Hz),
# tuned ~A442 (+10 c systematic)
FMIN, FMAX = 120.0, 1500.0


def segments(x: np.ndarray, sr: int, min_gap_s=1.0, ratio=5.0,
             floor_db=-45.0):
    """Mallet-attack onsets via high-frequency flux: the strike transient
    carries broadband HF the ring lacks, so a soft pp attack over a loud
    still-ringing previous note is still a sharp HF rise. Segment = onset
    to next onset."""
    from scipy.signal import butter, sosfilt

    sos = butter(4, 1500.0, btype="highpass", fs=sr, output="sos")
    hf = sosfilt(sos, x)
    hop = int(0.005 * sr)
    m = len(hf) // hop
    rms = np.sqrt((hf[: m * hop].reshape(m, hop) ** 2).mean(axis=1) + 1e-20)
    peak = rms.max()
    floor = peak * 10 ** (floor_db / 20)
    gap = int(min_gap_s / 0.005)
    onsets = []
    last = -10 ** 9
    for i in range(40, m):
        trail = np.median(rms[i - 40: i - 4]) + 1e-20
        if (rms[i] > floor and rms[i] > ratio * trail
                and rms[i] == rms[max(0, i - 4): i + 5].max()
                and i - last >= gap):
            onsets.append(i)
            last = i
    segs = []
    for j, o in enumerate(onsets):
        a = max(0, o * hop - int(0.03 * sr))
        b = onsets[j + 1] * hop - int(0.05 * sr) if j + 1 < len(onsets) else len(x)
        segs.append((a, b))
    return segs


def detect_f0(x: np.ndarray, sr: int) -> float:
    seg = x[: int(0.5 * sr)]
    w = np.hanning(len(seg))
    spec = np.abs(np.fft.rfft(seg * w, 1 << 17))
    fax = np.fft.rfftfreq(1 << 17, 1 / sr)
    sel = (fax >= FMIN) & (fax <= FMAX)
    s = spec.copy()
    s[~sel] = 0
    k = int(np.argmax(s))
    return float(fax[k])


def freq_to_midi(f: float) -> int:
    return int(round(69 + 12 * np.log2(f / 440.0)))


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "dampen"), exist_ok=True)
    for path in sorted(glob.glob(os.path.join(RAW, "*.aif"))):
        base = os.path.basename(path)  # Vibraphone.sustain.pp.C3B3.aif
        parts = base.split(".")
        art, dyn = parts[1], parts[2]
        if art == "sustain":
            layer = DYN_TO_LAYER[dyn]
        elif art == "dampen" and dyn == "mf":
            layer = None
        else:
            continue
        x, sr = sf.read(path, always_2d=True)
        mono = x.mean(axis=1)
        expected = {"C3B3": 12, "C4B4": 12, "C5B5": 12, "C6F6": 6}[parts[3]]
        # pp strikes carry little HF: loosen thresholds until the expected
        # chromatic count appears (pitch checks below reject false onsets)
        segs = []
        for ratio, floor_db in [(5.0, -45.0), (3.0, -52.0), (2.2, -58.0),
                                (1.8, -62.0), (1.5, -66.0), (1.35, -70.0)]:
            segs = segments(mono, sr, ratio=ratio, floor_db=floor_db)
            # false onsets mid-ring produce short fragments; a real note
            # rings for many seconds
            segs = [(a, b) for a, b in segs if (b - a) / sr >= 2.5]
            if len(segs) >= expected:
                break
        print(f"{base}: {len(segs)} segments (expected {expected})")
        for a, b in segs:
            f0 = detect_f0(mono[a:b], sr)
            midi = freq_to_midi(f0)
            name = midi_to_name(midi)
            cents = 1200 * np.log2(f0 / (440.0 * 2 ** ((midi - 69) / 12)))
            if abs(cents) > 40:
                print(f"  ! seg {a/sr:7.1f}s f0={f0:7.1f} -> {name} "
                      f"({cents:+.0f}c) — dubious, skipped")
                continue
            if layer is None:
                dst = os.path.join(OUT, "dampen", f"{name}.flac")
            else:
                dst = os.path.join(OUT, f"{name}v{layer}.flac")
            if os.path.exists(dst):
                print(f"  ! {dst} exists (duplicate pitch) — keeping first")
                continue
            sf.write(dst, x[a:b], sr)
            print(f"  {name:4s} f0={f0:7.1f} ({cents:+5.1f}c) "
                  f"{(b-a)/sr:5.1f}s -> {os.path.basename(dst)}")


if __name__ == "__main__":
    main()
