"""Evaluate the koto model vs reference.

  python -m instruments.koto.evaluate [--engine=rust] [--seed=N] [--save]
                                      [--null] [B3v2 ...]
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
SAMPLES = os.path.join(ROOT, "reference", "koto", "samples")
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
        print(f"{c.name:8s} score={m['score']:6.3f}  pc={m['partial_cents']} "
              f"dec={m['decay_logerr']} atk={m['attack_db']} env={m['env_db']} "
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


class _RefSynth:
    def __init__(self, path, sr):
        self.path = path
        self.sr = sr

    def synth_note(self, midi, velocity, dur=4.0, release_at=None):
        x, _ = load_mono(self.path)
        return x


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

    if null_mode:
        rows_all = []
        for note in NOTES:
            for layer in LAYERS:
                primary = os.path.join(SAMPLES, f"{note}v{layer}.flac")
                alt = os.path.join(SAMPLES, f"{note}v{layer}_alt1.flac")
                if not (os.path.exists(primary) and os.path.exists(alt)):
                    continue
                _, sr = load_mono(primary)
                case = EvalCase(name=f"{note}v{layer}~alt", midi=name_to_midi(note),
                                velocity=LAYER_TO_VEL[layer],
                                ref_path=primary, note=note, dur_cap=5.0)
                rows_all += run([case], _RefSynth(alt, sr),
                                os.path.join(OUTDIR, "eval_koto_null.json"))
        scores = [r["score"] for r in rows_all]
        with open(os.path.join(OUTDIR, "eval_koto_null.json"), "w") as f:
            json.dump(rows_all, f, indent=1)
        print(f"\nNULL (take-vs-take): mean {np.mean(scores):.3f} "
              f"std {np.std(scores):.3f}")
        return

    if engine == "rust":
        from .synth_rs import Koto
    else:
        from .synth import Koto
    koto = Koto(seed=seed)

    cases = []
    for note in NOTES:
        for layer in LAYERS:
            name = f"{note}v{layer}"
            if only and name not in only:
                continue
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            cases.append(EvalCase(name=name, midi=name_to_midi(note),
                                  velocity=LAYER_TO_VEL[layer],
                                  ref_path=ref_path, note=note, dur_cap=5.0))

    out_name = "eval_koto_rust.json" if engine == "rust" else "eval_koto.json"
    if seed != 1234:
        out_name = out_name.replace(".json", f"_seed{seed}.json")
    run(cases, koto, os.path.join(OUTDIR, out_name),
        save_wav_dir=os.path.join(OUTDIR, "synth_koto") if save else None)


if __name__ == "__main__":
    main()
