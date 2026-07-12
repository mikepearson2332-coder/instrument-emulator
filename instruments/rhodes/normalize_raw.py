"""Normalize jRhodes3d mono takes into the reference grid.

  python -m instruments.rhodes.normalize_raw

jRhodes3d file names are `A_{midi:03d}__{Note}{Octave}_{k}.flac` where
k=1 is the LOUDEST take and k=5 the softest (sfz velocity groups:
_5: 1-47, _4: 48-72, _3: 73-95, _2: 96-111, _1: 112-127). We renumber
soft->loud as v1..v5 to match the bank convention (piano/koto), i.e.
v-layer L maps to file suffix 6-L. High notes miss some takes (the sfz
reuses neighbours there): B4/E5 lack _3 (no v3); A5/D6/G6/C7 lack _1
and _3 (no v3/v5). Missing layers are simply absent — the calibrator
interpolates over the layers that exist.
"""

from __future__ import annotations

import os
import re

import soundfile as sf

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RAW = os.path.join(ROOT, "reference", "rhodes", "raw", "jRhodes3d",
                   "jRhodes3d-mono")
OUT = os.path.join(ROOT, "reference", "rhodes", "samples")

FNAME = re.compile(r"^A_(\d{3})__([A-G]b?\d)_(\d)\.flac$")


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for fn in sorted(os.listdir(RAW)):
        m = FNAME.match(fn)
        if not m:
            continue
        note, k = m.group(2), int(m.group(3))
        layer = 6 - k
        x, sr = sf.read(os.path.join(RAW, fn), always_2d=True)
        dst = f"{note}v{layer}.flac"
        sf.write(os.path.join(OUT, dst), x, sr)
        print(f"{fn:22s} -> {dst}  ({len(x)/sr:5.1f}s @ {sr})")
        n += 1
    print(f"normalized {n} files")


if __name__ == "__main__":
    main()
