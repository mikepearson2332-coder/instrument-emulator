"""Render all benchmark notes with the current synth and score vs reference.

Usage:
  python scripts/evaluate.py            -> all notes/velocities
  python scripts/evaluate.py C4v11 ...  -> subset
  python scripts/evaluate.py --save     -> also write synth WAVs to output/synth/
  python scripts/evaluate.py --engine=rust  -> use the Rust core (default: python)
                                               writes output/eval_rust.json
  python scripts/evaluate.py --seed=N   -> synth RNG seed (default 1234;
                                           non-default appends _seedN)
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lab.evalharness import EvalCase, run_eval
from instruments.piano.notes import SALAMANDER_NOTES, SALAMANDER_VELS, name_to_midi
from instruments.piano.calibrate import LAYER_TO_VEL
from instruments.piano.benchmark import compare, composite_score

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "piano", "samples")
OUTDIR = os.path.join(ROOT, "output")


def main():
    args = [a for a in sys.argv[1:]]
    save = "--save" in args
    engine = "rust" if "--engine=rust" in args else "python"
    seed = 1234
    for a in args:
        if a.startswith("--seed="):
            seed = int(a.split("=")[1])
    args = [a for a in args if not a.startswith("--")]
    only = set(args) or None

    if engine == "rust":
        from instruments.piano.synth_rs import Piano
    else:
        from instruments.piano.synth import Piano
    piano = Piano(seed=seed)

    cases = []
    for note in SALAMANDER_NOTES:
        for layer in SALAMANDER_VELS:
            name = f"{note}v{layer}"
            if only and name not in only:
                continue
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            release_at = None
            ana_path = os.path.join(ROOT, "reference", "piano", "analysis", f"{name}.json")
            if os.path.exists(ana_path):
                with open(ana_path) as f:
                    release_at = json.load(f).get("release_s")
            cases.append(EvalCase(name=name, midi=name_to_midi(note),
                                  velocity=LAYER_TO_VEL[layer], ref_path=ref_path,
                                  note=note, release_at=release_at))

    out_name = "eval_rust.json" if engine == "rust" else "eval.json"
    if seed != 1234:
        out_name = out_name.replace(".json", f"_seed{seed}.json")
    run_eval(cases, piano, compare, composite_score,
             out_path=os.path.join(OUTDIR, out_name),
             save_wav_dir=os.path.join(OUTDIR, "synth") if save else None)


if __name__ == "__main__":
    main()
