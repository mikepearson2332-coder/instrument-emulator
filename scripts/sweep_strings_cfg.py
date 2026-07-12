"""Grid-fit the unmeasurable ensemble config params (vib_cents,
drift_cents) against the benchmark on a representative subset.

  python scripts/sweep_strings_cfg.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.benchmark import compare, composite_score
from instruments.strings.evaluate import _vel_map, cases_for
from lab.audio import load_mono
from lab.sustained import SustainedSynth

ROOT = os.path.join(os.path.dirname(__file__), "..")
PARAMS = os.path.join(ROOT, "instruments", "strings", "params")

SUBSET = ["vln_G3v1", "vln_A4v2", "vln_D6v1", "vla_C3v1", "vla_D4v1",
          "vla_C5v2", "vc_C2v2", "vc_A3v1", "vc_D5v2", "cb_G1v1",
          "cb_C#3v2", "cb_G#3v1"]

GRID_VIB = [3.0, 5.0, 7.0]
GRID_DRIFT = [2.0, 4.0, 6.0]


def main():
    by_sec = {}
    for name in SUBSET:
        sec = name.split("_")[0]
        by_sec.setdefault(sec, []).append(name)

    cases = {}
    for sec, names in by_sec.items():
        vm = _vel_map(sec)
        for c in cases_for(sec):
            if c["name"] in names:
                c["vel"] = vm.get((c["midi"], c["layer"]), 90)
                cases[c["name"]] = c

    for vib in GRID_VIB:
        for drift in GRID_DRIFT:
            scores, harms, mods = [], [], []
            for sec in by_sec:
                with open(os.path.join(PARAMS, f"{sec}.json")) as f:
                    t = json.load(f)
                t["config"]["vib_cents"] = vib
                t["config"]["drift_cents"] = drift
                with tempfile.NamedTemporaryFile("w", suffix=".json",
                                                 delete=False) as f:
                    json.dump(t, f)
                    path = f.name
                synth = SustainedSynth(path, seed=1234)
                os.unlink(path)
                for name in by_sec[sec]:
                    c = cases[name]
                    ref, sr = load_mono(c["ref"])
                    dur = min(len(ref) / sr, 12.0)
                    rel = c["release_at"] or dur * 0.75
                    y = synth.synth_note(c["midi"], c["vel"], dur=dur,
                                         release_at=min(rel, dur - 0.1))
                    m = compare(y, synth.sr, c["ref"], c["note"])
                    scores.append(composite_score(m))
                    harms.append(m["harm_db"] or 0)
                    mods.append(m["mod_db"] or 0)
            print(f"vib={vib:.0f}c drift={drift:.0f}c  "
                  f"score={np.mean(scores):.3f}  harm={np.mean(harms):.2f}  "
                  f"mod={np.mean(mods):.2f}", flush=True)


if __name__ == "__main__":
    main()
