"""Python-vs-Rust sustained note_params parity (strings sections).

  python scripts/parity_sustained.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.synth import Strings as PyStrings
from instruments.strings.synth_rs import Strings as RsStrings

SECTIONS = ["vln", "vla", "vc", "cb"]
SCALARS = ["f0", "rise_s", "und_db", "und_hz", "vib_hz", "vib_am_db",
           "rel_s", "rel_remnant", "rel_tail_s"]


def flatten(p):
    out = [p[k] for k in SCALARS]
    for h in sorted(p["harm"], key=lambda h: h["n"]):
        out += [h["n"], h["a"]]
    out += list(p["noise_db"])
    return np.array(out, float)


def main():
    worst = 0.0
    for sec in SECTIONS:
        a = PyStrings(section=sec)
        b = RsStrings(section=sec)
        lo = a.keys[0]["midi"] - 3
        hi = a.keys[-1]["midi"] + 3
        for midi in range(lo, hi + 1, 2):
            for vel in (40, 60, 85, 110, 127):
                pa = a.note_params(midi, vel)
                pa = {**pa, "harm": pa["harm"]}
                pb = b.note_params(midi, vel)
                fa, fb = flatten(pa), flatten(pb)
                if len(fa) != len(fb):
                    print(f"{sec} midi={midi} vel={vel}: LENGTH {len(fa)} vs {len(fb)}")
                    worst = float("inf")
                    continue
                denom = np.maximum(np.abs(fa), 1e-12)
                rel = float(np.max(np.abs(fa - fb) / denom))
                worst = max(worst, rel)
    print(f"sustained parity: worst rel diff = {worst:.3e}")


if __name__ == "__main__":
    main()
