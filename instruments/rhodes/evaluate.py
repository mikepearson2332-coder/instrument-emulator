"""Evaluate the rhodes model vs reference.

  python -m instruments.rhodes.evaluate [--engine=rust] [--seed=N] [--save]
                                        [--null] [B3v2 ...]

--null: no round robins exist, so the metric noise floor is estimated by
perturbed self-comparison — reference vs itself with a small time trim
and gain jitter (deterministic per case). This bounds how low the
metrics can meaningfully go; the seed-to-seed synth null (--seed) bounds
render-to-render variation.
"""

import json
import os
import sys

import numpy as np

from lab.audio import load_mono
from lab.evalharness import EvalCase
from lab.notes import name_to_midi

from .benchmark import compare, composite_score
from .calibrate import LAYER_TO_VEL, LAYERS, NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "rhodes", "samples")
OUTDIR = os.path.join(ROOT, "output")

DUR_CAP = 8.0


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
        print(f"{c.name:8s} score={m['score']:6.3f}  pc={m['partial_cents']} "
              f"harm={m['harm_db']} dec={m['decay_logerr']} "
              f"atk={m['attack_db']} env={m['env_db']} "
              f"lsdE={m['lsd_early']} lsdM={m['lsd_mid']} "
              f"cent={m['centroid_ratio']}", flush=True)
        if save_wav_dir:
            os.makedirs(save_wav_dir, exist_ok=True)
            peak = np.max(np.abs(y)) + 1e-12
            sf.write(os.path.join(save_wav_dir, f"{c.name}.wav"),
                     (y / peak * 0.9).astype(np.float32), synth.sr)
    if rows:
        scores = [r["score"] for r in rows]
        print(f"\nmean score: {np.mean(scores):.3f}   "
              f"median: {np.median(scores):.3f}   worst: {max(scores):.3f} "
              f"({rows[int(np.argmax(scores))]['name']})")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=1)
    return rows


class _PerturbedRef:
    """Reference rendered as 'synth': trimmed by a few ms, gain-jittered."""

    def __init__(self, path, sr, idx):
        self.path = path
        self.sr = sr
        rng = np.random.default_rng(1000 + idx)
        self.trim_s = float(rng.uniform(0.002, 0.008))
        self.gain = float(10 ** (rng.uniform(-0.5, 0.5) / 20))

    def synth_note(self, midi, velocity, dur=4.0, release_at=None):
        x, sr = load_mono(self.path)
        return self.gain * x[int(self.trim_s * sr):]


def main():
    args = sys.argv[1:]
    save = "--save" in args
    engine = "rust" if "--engine=rust" in args else "python"
    null_mode = "--null" in args
    seed = 1234
    for a in args:
        if a.startswith("--seed="):
            seed = int(a.split("=")[1])
    only = set(a for a in args if not a.startswith("--")) or None

    all_cases = []
    for note in NOTES:
        for layer in LAYERS:
            name = f"{note}v{layer}"
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            all_cases.append(EvalCase(name=name, midi=name_to_midi(note),
                                      velocity=LAYER_TO_VEL[layer],
                                      ref_path=ref_path, note=note,
                                      dur_cap=DUR_CAP))

    if null_mode:
        rows_all = []
        for i, c in enumerate(all_cases):
            _, sr = load_mono(c.ref_path)
            rows_all += run([c], _PerturbedRef(c.ref_path, sr, i),
                            os.path.join(OUTDIR, "eval_rhodes_null.json"))
        scores = [r["score"] for r in rows_all]
        with open(os.path.join(OUTDIR, "eval_rhodes_null.json"), "w") as f:
            json.dump(rows_all, f, indent=1)
        print(f"\nNULL (perturbed self): mean {np.mean(scores):.3f} "
              f"std {np.std(scores):.3f}")
        return

    quality = None
    for a in args:
        if a.startswith("--quality="):
            quality = int(a.split("=")[1])

    if engine == "rust":
        from .synth_rs import Rhodes
    else:
        from .synth import Rhodes
    rhodes = Rhodes(seed=seed)
    if quality is not None:
        rhodes.set_quality(max_partials=quality)

    cases = [c for c in all_cases if not only or c.name in only]

    out_name = "eval_rhodes_rust.json" if engine == "rust" else "eval_rhodes.json"
    if seed != 1234:
        out_name = out_name.replace(".json", f"_seed{seed}.json")
    run(cases, rhodes, os.path.join(OUTDIR, out_name),
        save_wav_dir=os.path.join(OUTDIR, "synth_rhodes") if save else None)


if __name__ == "__main__":
    main()
