"""Evaluate the woodblock model vs reference.

  python -m instruments.woodblock.evaluate            # 4 layers, Python synth
  python -m instruments.woodblock.evaluate --null     # reference-vs-reference
                                                      # noise floor (alt takes)
  python -m instruments.woodblock.evaluate --engine=rust
  python -m instruments.woodblock.evaluate --seed=N --save
"""

import os
import sys

from lab.audio import load_mono
from lab.evalharness import EvalCase
from lab.notes import name_to_midi

from .benchmark import compare, composite_score
from .calibrate import LAYER_TO_VEL, LAYERS, NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "woodblock", "samples")
OUTDIR = os.path.join(ROOT, "output")


def run(cases, synth, out_path, save_wav_dir=None):
    """Like lab.evalharness.run_eval but with woodblock metric columns."""
    import json

    import numpy as np
    import soundfile as sf

    rows = []
    for c in cases:
        ref, sr = load_mono(c.ref_path)
        dur = min(len(ref) / sr, c.dur_cap)
        y = synth.synth_note(c.midi, c.velocity, dur=dur, release_at=c.release_at)
        m = compare(y, synth.sr, c.ref_path, c.note)
        m["name"] = c.name
        m["score"] = composite_score(m)
        rows.append(m)
        print(f"{c.name:10s} score={m['score']:6.3f}  atk={m['attack_db']} "
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
        import numpy as np
        print(f"\nmean score: {np.mean(scores):.3f}   median: {np.median(scores):.3f}"
              f"   worst: {max(scores):.3f}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(rows, f, indent=1)
    return rows


class _RefSynth:
    """Plays an alternate reference take instead of synthesizing —
    measures the benchmark's noise floor (strike-to-strike variability)."""

    def __init__(self, alt_paths, sr):
        self.alt_paths = alt_paths
        self.sr = sr
        self._i = 0

    def synth_note(self, midi, velocity, dur=1.0, release_at=None):
        x, sr = load_mono(self.alt_paths[self._i % len(self.alt_paths)])
        self._i += 1
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

    if null_mode:
        # score each alt take against the primary take of the same layer
        rows_all = []
        for note in NOTES:
            for layer in LAYERS:
                primary = os.path.join(SAMPLES, f"{note}v{layer}.flac")
                for k in (1, 2):
                    alt = os.path.join(SAMPLES, f"{note}v{layer}_alt{k}.flac")
                    if not (os.path.exists(primary) and os.path.exists(alt)):
                        continue
                    _, sr = load_mono(primary)
                    synth = _RefSynth([alt], sr)
                    case = EvalCase(name=f"{note}v{layer}~alt{k}",
                                    midi=name_to_midi(note),
                                    velocity=LAYER_TO_VEL[layer],
                                    ref_path=primary, note=note, dur_cap=1.0)
                    rows_all += run([case], synth,
                                    os.path.join(OUTDIR, "eval_wb_null_tmp.json"))
        import json
        import numpy as np
        out = os.path.join(OUTDIR, "eval_wb_null.json")
        with open(out, "w") as f:
            json.dump(rows_all, f, indent=1)
        os.remove(os.path.join(OUTDIR, "eval_wb_null_tmp.json"))
        scores = [r["score"] for r in rows_all]
        print(f"\nNULL (take-vs-take): mean {np.mean(scores):.3f} "
              f"std {np.std(scores):.3f} -> {out}")
        return

    if engine == "rust":
        from .synth_rs import Woodblock
    else:
        from .synth import Woodblock
    wb = Woodblock(seed=seed)

    cases = []
    for note in NOTES:
        for layer in LAYERS:
            name = f"{note}v{layer}"
            ref_path = os.path.join(SAMPLES, f"{name}.flac")
            if not os.path.exists(ref_path):
                continue
            cases.append(EvalCase(name=name, midi=name_to_midi(note),
                                  velocity=LAYER_TO_VEL[layer],
                                  ref_path=ref_path, note=note, dur_cap=1.0))

    out_name = "eval_wb_rust.json" if engine == "rust" else "eval_wb.json"
    if seed != 1234:
        out_name = out_name.replace(".json", f"_seed{seed}.json")
    run(cases, wb, os.path.join(OUTDIR, out_name),
        save_wav_dir=os.path.join(OUTDIR, "synth_wb") if save else None)


if __name__ == "__main__":
    main()
