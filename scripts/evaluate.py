"""Render all benchmark notes with the current synth and score vs reference.

Usage:
  python scripts/evaluate.py            -> all notes/velocities
  python scripts/evaluate.py C4v11 ...  -> subset
  python scripts/evaluate.py --save     -> also write synth WAVs to output/synth/
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import soundfile as sf

from instruments.piano.notes import SALAMANDER_NOTES, SALAMANDER_VELS, name_to_midi
from instruments.piano.calibrate import LAYER_TO_VEL
from instruments.piano.synth import Piano
from instruments.piano.benchmark import compare, composite_score
from instruments.piano.analysis import load_mono

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "piano", "samples")
OUTDIR = os.path.join(ROOT, "output")


def main():
    args = [a for a in sys.argv[1:]]
    save = "--save" in args
    args = [a for a in args if not a.startswith("--")]
    only = set(args) or None

    piano = Piano()
    rows = []
    for note in SALAMANDER_NOTES:
        for layer in SALAMANDER_VELS:
            name = f"{note}v{layer}"
            if only and name not in only:
                continue
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            midi = name_to_midi(note)
            vel = LAYER_TO_VEL[layer]
            ref, sr = load_mono(ref_path)
            dur = min(len(ref) / sr, 8.0)
            release_at = None
            ana_path = os.path.join(ROOT, "reference", "piano", "analysis", f"{name}.json")
            if os.path.exists(ana_path):
                with open(ana_path) as f:
                    release_at = json.load(f).get("release_s")
            y = piano.synth_note(midi, vel, dur=dur, release_at=release_at)
            m = compare(y, piano.sr, ref_path, note)
            m["name"] = name
            m["score"] = composite_score(m)
            rows.append(m)
            print(f"{name:8s} score={m['score']:6.3f}  f0c={m['f0_cents']:7.2f} "
                  f"pc={m['partial_cents']}  dec={m['decay_logerr']} "
                  f"lsdE={m['lsd_early']} lsdM={m['lsd_mid']} "
                  f"env={m['env_db']} cent={m['centroid_ratio']}", flush=True)
            if save:
                os.makedirs(os.path.join(OUTDIR, "synth"), exist_ok=True)
                peak = np.max(np.abs(y)) + 1e-12
                sf.write(os.path.join(OUTDIR, "synth", f"{name}.wav"),
                         (y / peak * 0.9).astype(np.float32), piano.sr)

    if rows:
        scores = [r["score"] for r in rows]
        print(f"\nmean score: {np.mean(scores):.3f}   median: {np.median(scores):.3f}"
              f"   worst: {max(scores):.3f} ({rows[int(np.argmax(scores))]['name']})")
        os.makedirs(OUTDIR, exist_ok=True)
        with open(os.path.join(OUTDIR, "eval.json"), "w") as f:
            json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
