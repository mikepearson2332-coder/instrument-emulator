"""Score-vs-quality sweep for the Rust engine: how does the composite
benchmark degrade as partials/symp/noise are pruned, and what does each
level cost? Uses the v11 layer (30 notes) as a representative subset.

Writes output/quality_sweep.json and prints a table."""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.piano.notes import SALAMANDER_NOTES, name_to_midi
from instruments.piano.calibrate import LAYER_TO_VEL
from instruments.piano.benchmark import compare, composite_score
from instruments.piano.analysis import load_mono
from instruments.piano.synth_rs import Piano

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "piano", "samples")

LEVELS = [
    ("full", dict()),
    ("p48", dict(max_partials=48)),
    ("p32", dict(max_partials=32)),
    ("p24", dict(max_partials=24)),
    ("p16", dict(max_partials=16)),
    ("p8", dict(max_partials=8)),
    ("p24_s12", dict(max_partials=24, max_symp_lines=12)),
    ("p16_s8_nonoise", dict(max_partials=16, max_symp_lines=8, noise=False)),
]


def main():
    layer = 11
    vel = LAYER_TO_VEL[layer]
    rows = []
    for label, qkw in LEVELS:
        piano = Piano(**qkw)
        scores = []
        render_s = 0.0
        for note in SALAMANDER_NOTES:
            name = f"{note}v{layer}"
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            midi = name_to_midi(note)
            ref, sr = load_mono(ref_path)
            dur = min(len(ref) / sr, 8.0)
            ana = os.path.join(ROOT, "reference", "piano", "analysis", f"{name}.json")
            release_at = None
            if os.path.exists(ana):
                with open(ana) as f:
                    release_at = json.load(f).get("release_s")
            t0 = time.perf_counter()
            y = piano.synth_note(midi, vel, dur=dur, release_at=release_at)
            render_s += time.perf_counter() - t0
            m = compare(y, piano.sr, ref_path, note)
            scores.append(composite_score(m))
        row = {
            "level": label,
            "quality": qkw,
            "mean_score": float(np.mean(scores)),
            "ms_per_note": render_s * 1000 / len(scores),
        }
        rows.append(row)
        print(f"{label:16s} mean {row['mean_score']:.3f}   "
              f"{row['ms_per_note']:6.1f} ms/note", flush=True)

    with open(os.path.join(ROOT, "output", "quality_sweep.json"), "w") as f:
        json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
