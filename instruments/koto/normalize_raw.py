"""Normalize VCSL Dan Tranh raw takes into the reference grid.

  python -m instruments.koto.normalize_raw

VCSL file names are one octave below sounding pitch (verified by
harmonic-product-spectrum detection during acquisition, see DEVLOG), with
two mislabels: `B1_mf_1` sounds B3, and the whole `C#2_*` group sounds
C#4 — the `C#3_*` group is the same string in another session, retuned
+35 c (movable bridges). The mapping below is the audited result; f/ff/mf
-> v2/v3/v1. Alternate takes become `_alt` files (benchmark null set).
"""

from __future__ import annotations

import os

import soundfile as sf

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "reference", "koto", "raw", "tranh")
OUT = os.path.join(ROOT, "reference", "koto", "samples")

# raw file (no .wav) -> normalized name (sounding pitch)
MAPPING = {
    "B1_f_1": "B2v2", "B1_ff_1": "B2v3",
    "D#2_mf_1": "D#3v1", "D#2_f_1": "D#3v2", "D#2_ff_1": "D#3v3",
    "F#2_mf_1": "F#3v1", "F#2_f_1": "F#3v2", "F#2_ff_1": "F#3v3",
    "G#2_mf_1": "G#3v1", "G#2_f_1": "G#3v2", "G#2_ff_1": "G#3v3",
    "B1_mf_1": "B3v1", "B2_f_1": "B3v2", "B2_ff_1": "B3v3",
    "b2_mf_1": "B3v1_alt1",
    "C#2_mf_1": "C#4v1", "C#2_f_1": "C#4v2", "C#2_ff_1": "C#4v3",
    "C#3_mf_1": "C#4v1_alt1", "C#3_f_1": "C#4v2_alt1",
    "D#3_mf_1": "D#4v1", "D#3_f_1": "D#4v2", "D#3_ff_1": "D#4v3",
    "F#3_mf_1": "F#4v1", "F#3_f_1": "F#4v2", "F#3_ff_1": "F#4v3",
    "G#3_mf_1": "G#4v1", "G#3_f_1": "G#4v2", "G#3_ff_1": "G#4v3",
    "B3_mf_1": "B4v1", "B3_f_1": "B4v2", "B3_ff_1": "B4v3",
    "C#4_mf_1": "C#5v1", "C#4_f_1": "C#5v2", "C#4_ff_1": "C#5v3",
    "D#4_mf_1": "D#5v1", "D#4_f_1": "D#5v2", "D#4_ff_1": "D#5v3",
    "F#4_mf_1": "F#5v1", "F#4_f_1": "F#5v2", "F#4_ff_1": "F#5v3",
    "G#4_mf_1": "G#5v1", "G#4_f_1": "G#5v2", "G#4_ff_1": "G#5v3",
    "B4_mf_1": "B5v1", "B4_f_1": "B5v2", "B4_ff_1": "B5v3",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, dst in sorted(MAPPING.items(), key=lambda kv: kv[1]):
        x, sr = sf.read(os.path.join(RAW, f"{src}.wav"), always_2d=True)
        sf.write(os.path.join(OUT, f"{dst}.flac"), x, sr)
        print(f"{src:12s} -> {dst}.flac  ({len(x)/sr:.1f}s)")


if __name__ == "__main__":
    main()
