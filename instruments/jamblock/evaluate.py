"""Evaluate the jam block model vs reference.

  python -m instruments.jamblock.evaluate [--engine=rust] [--seed=N]
                                          [--save] [--null] [--quality=N]

Scores only the recorded dynamic (v1, vel 96); derived soft/loud layers
are playability-only (see calibrate.py). --null scores the E5 alt take
(a different physical block with the same dominant mode) against the
primary — a deliberately generous strike-and-block variability floor.
Benchmark = the woodblock's (same struck-block percept, same weights).
"""

import json
import os
import sys

import numpy as np

from lab.audio import load_mono
from lab.evalharness import EvalCase
from lab.notes import name_to_midi

from instruments.woodblock.benchmark import compare, composite_score

from .calibrate import LAYER_TO_VEL, NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "jamblock", "samples")
OUTDIR = os.path.join(ROOT, "output")


def run(cases, synth, out_path, save_wav_dir=None):
    import soundfile as sf

    rows = []
    for c in cases:
        ref, sr = load_mono(c.ref_path)
        dur = min(len(ref) / sr, c.dur_cap)
        y = synth.synth_note(c.midi, c.velocity, dur=dur,
                             release_at=c.release_at)
        m = compare(y, synth.sr, c.ref_path, c.note)
        m["name"] = c.name
        m["score"] = composite_score(m)
        rows.append(m)
        print(f"{c.name:12s} score={m['score']:6.3f}  atk={m['attack_db']} "
              f"env={m['env_db']} modes={m['mode_cents']}c "
              f"dec={m['decay_logerr']} lsdE={m['lsd_early']} "
              f"lsdM={m['lsd_mid']} cent={m['centroid_ratio']}", flush=True)
        if save_wav_dir:
            os.makedirs(save_wav_dir, exist_ok=True)
            peak = np.max(np.abs(y)) + 1e-12
            sf.write(os.path.join(save_wav_dir, f"{c.name}.wav"),
                     (y / peak * 0.9).astype(np.float32), synth.sr)
    if rows:
        scores = [r["score"] for r in rows]
        print(f"\nmean score: {np.mean(scores):.3f}   "
              f"median: {np.median(scores):.3f}   worst: {max(scores):.3f}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=1)
    return rows


class _RefSynth:
    def __init__(self, path):
        self.path = path
        _, self.sr = load_mono(path)

    def synth_note(self, midi, velocity, dur=1.0, release_at=None):
        x, _ = load_mono(self.path)
        return x


def main():
    args = sys.argv[1:]
    save = "--save" in args
    engine = "rust" if "--engine=rust" in args else "python"
    null_mode = "--null" in args
    seed = 1234
    quality = None
    for a in args:
        if a.startswith("--seed="):
            seed = int(a.split("=")[1])
        if a.startswith("--quality="):
            quality = int(a.split("=")[1])

    if null_mode:
        rows = []
        for note in NOTES:
            primary = os.path.join(SAMPLES, f"{note}v1.flac")
            alt = os.path.join(SAMPLES, f"{note}v1_alt1.flac")
            if not (os.path.exists(primary) and os.path.exists(alt)):
                continue
            case = EvalCase(name=f"{note}v1~alt", midi=name_to_midi(note),
                            velocity=LAYER_TO_VEL[1], ref_path=primary,
                            note=note, dur_cap=1.0)
            rows += run([case], _RefSynth(alt),
                        os.path.join(OUTDIR, "eval_jam_null.json"))
        scores = [r["score"] for r in rows]
        with open(os.path.join(OUTDIR, "eval_jam_null.json"), "w") as f:
            json.dump(rows, f, indent=1)
        print(f"\nNULL (block-vs-block): mean {np.mean(scores):.3f} "
              f"std {np.std(scores):.3f}")
        return

    if engine == "rust":
        from .synth_rs import Jamblock
    else:
        from .synth import Jamblock
    jb = Jamblock(seed=seed)
    if quality is not None:
        jb.set_quality(max_partials=quality)

    cases = []
    for note in NOTES:
        ref_path = os.path.join(SAMPLES, f"{note}v1.flac")
        if not os.path.exists(ref_path):
            continue
        cases.append(EvalCase(name=f"{note}v1", midi=name_to_midi(note),
                              velocity=LAYER_TO_VEL[1], ref_path=ref_path,
                              note=note, dur_cap=1.0))

    out_name = "eval_jam_rust.json" if engine == "rust" else "eval_jam.json"
    if seed != 1234:
        out_name = out_name.replace(".json", f"_seed{seed}.json")
    run(cases, jb, os.path.join(OUTDIR, out_name),
        save_wav_dir=os.path.join(OUTDIR, "synth_jam") if save else None)


if __name__ == "__main__":
    main()
