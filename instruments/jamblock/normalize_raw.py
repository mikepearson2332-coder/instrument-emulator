"""Normalize jam block raw takes (Freesound HQ previews) into the grid.

  python -m instruments.jamblock.normalize_raw

Anchors were measured (scripts/probe_jamblock.py), not taken from file
names — "small" vs "smaller" do NOT order by pitch. large and medlarge
share a ~648 Hz dominant mode: medlarge becomes the E5 alt take (the
benchmark's take-vs-take null set, woodblock precedent).
"""

from __future__ import annotations

import os

import soundfile as sf

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "reference", "jamblock", "raw")
OUT = os.path.join(ROOT, "reference", "jamblock", "samples")

# raw file -> normalized name (dominant mode -> nearest key)
MAPPING = {
    "largegranitedry_544875.ogg": "E5v1",        # 649.7 Hz (-25c)
    "medlargegranitedry_544877.ogg": "E5v1_alt1",  # 647.0 Hz
    "mediumgranitedry_544879.ogg": "F#5v1",      # 732.1 Hz (-18c)
    "smallgranitedry_544883.ogg": "G5v1",        # 765.4 Hz (-42c)
    "smallergranitedry_544881.ogg": "C6v1",      # 1056.8 Hz (+17c)
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for src, dst in sorted(MAPPING.items(), key=lambda kv: kv[1]):
        x, sr = sf.read(os.path.join(RAW, src), always_2d=True)
        sf.write(os.path.join(OUT, f"{dst}.flac"), x, sr)
        print(f"{src:32s} -> {dst}.flac  ({len(x)/sr:.2f}s @ {sr})")


if __name__ == "__main__":
    main()
