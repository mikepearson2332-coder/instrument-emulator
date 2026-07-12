"""Evaluate the string-section model vs reference.

  python -m instruments.strings.evaluate [--engine=rust] [--seed=N]
      [--save] [--null] [--sec=vln] [vln_G3v1 ...]

Each render is released where the reference stops sustaining
(t_sus_end from the analysis JSON) so macro envelopes align. --null:
perturbed self-comparison (trim 30-120 ms + gain jitter).
"""

import json
import os
import sys

import numpy as np

from lab.audio import load_mono
from lab.notes import name_to_midi

from .benchmark import compare, composite_score
from .calibrate import LAYER_TO_VEL, SECTIONS

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "strings", "samples")
ANALYSIS = os.path.join(ROOT, "reference", "strings", "analysis")
OUTDIR = os.path.join(ROOT, "output")

DUR_CAP = 12.0


def cases_for(sec):
    out = []
    for fn in sorted(os.listdir(SAMPLES)):
        if not fn.startswith(sec + "_") or "_alt" in fn:
            continue
        if sec == "cb" and fn.startswith("cb_nv"):
            continue
        name = fn[:-5]
        note, layer = name[len(sec) + 1:].split("v")
        apath = os.path.join(ANALYSIS, f"{name}.json")
        rel_at = None
        if os.path.exists(apath):
            with open(apath) as f:
                a = json.load(f)
            rel_at = a["t_sus_end"]
        out.append({"name": name, "note": note, "midi": name_to_midi(note),
                    "layer": int(layer), "ref": os.path.join(SAMPLES, fn),
                    "release_at": rel_at})
    return out


def _vel_map(sec):
    """(midi, file-layer) -> table velocity. The calibrator orders table
    layers by measured loudness, which can invert the file numbering."""
    path = os.path.join(os.path.dirname(__file__), "params", f"{sec}.json")
    out = {}
    if os.path.exists(path):
        with open(path) as f:
            t = json.load(f)
        for k in t["keys"]:
            for L in k["layers"]:
                out[(k["midi"], L["layer"])] = L["vel"]
    return out


def run_cases(cases, synth, rows, vel_map=None, save_wav_dir=None):
    import soundfile as sf

    for c in cases:
        ref, sr = load_mono(c["ref"])
        dur = min(len(ref) / sr, DUR_CAP)
        rel = c["release_at"] if c["release_at"] else dur * 0.75
        vel = (vel_map or {}).get((c["midi"], c["layer"]),
                                  LAYER_TO_VEL.get(c["layer"], 90))
        y = synth.synth_note(c["midi"], vel, dur=dur,
                             release_at=min(rel, dur - 0.1))
        m = compare(y, synth.sr, c["ref"], c["note"])
        m["name"] = c["name"]
        m["score"] = composite_score(m)
        rows.append(m)
        print(f"{c['name']:12s} score={m['score']:6.3f}  harm={m['harm_db']} "
              f"lsd={m['lsd_sus']} env={m['env_db']} mod={m['mod_db']} "
              f"rise={m['rise_err']} rel={m['rel_err']}", flush=True)
        if save_wav_dir:
            os.makedirs(save_wav_dir, exist_ok=True)
            peak = np.max(np.abs(y)) + 1e-12
            sf.write(os.path.join(save_wav_dir, f"{c['name']}.wav"),
                     (y / peak * 0.9).astype(np.float32), synth.sr)


class _PerturbedRef:
    def __init__(self, path, idx):
        self.path = path
        _, self.sr = load_mono(path)
        rng = np.random.default_rng(2000 + idx)
        self.trim_s = float(rng.uniform(0.03, 0.12))
        self.gain = float(10 ** (rng.uniform(-0.5, 0.5) / 20))

    def synth_note(self, midi, velocity, dur=6.0, release_at=None):
        x, sr = load_mono(self.path)
        return self.gain * x[int(self.trim_s * sr):]


def main():
    args = sys.argv[1:]
    save = "--save" in args
    engine = "rust" if "--engine=rust" in args else "python"
    null_mode = "--null" in args
    seed = 1234
    secs = SECTIONS
    for a in args:
        if a.startswith("--seed="):
            seed = int(a.split("=")[1])
        if a.startswith("--sec="):
            secs = [a.split("=")[1]]
    only = set(a for a in args if not a.startswith("--")) or None

    rows = []
    for sec in secs:
        cases = cases_for(sec)
        if only:
            cases = [c for c in cases if c["name"] in only]
        if not cases:
            continue
        if null_mode:
            for i, c in enumerate(cases):
                run_cases([c], _PerturbedRef(c["ref"], i), rows)
            continue
        if engine == "rust":
            from .synth_rs import Strings
        else:
            from .synth import Strings
        synth = Strings(section=sec, seed=seed)
        run_cases(cases, synth, rows, vel_map=_vel_map(sec),
                  save_wav_dir=os.path.join(OUTDIR, "synth_strings")
                  if save else None)

    if rows:
        scores = [r["score"] for r in rows]
        tag = "null" if null_mode else engine
        print(f"\n[{tag}] mean score: {np.mean(scores):.3f}   "
              f"median: {np.median(scores):.3f}   worst: {max(scores):.3f} "
              f"({rows[int(np.argmax(scores))]['name']})")
        out_name = {"null": "eval_strings_null.json",
                    "rust": "eval_strings_rust.json",
                    "python": "eval_strings.json"}[tag]
        if seed != 1234:
            out_name = out_name.replace(".json", f"_seed{seed}.json")
        os.makedirs(OUTDIR, exist_ok=True)
        with open(os.path.join(OUTDIR, out_name), "w") as f:
            json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
