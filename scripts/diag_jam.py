"""Attribute jam block mismatch: mute one component at a time (probe6
pattern) and print score/centroid deltas per case.

  python scripts/diag_jam.py
"""

import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from instruments.jamblock.calibrate import LAYER_TO_VEL, NOTES
from instruments.jamblock.synth import Jamblock, DEFAULT_TABLE
from instruments.woodblock.benchmark import compare, composite_score
from lab.audio import load_mono
from lab.notes import name_to_midi

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "jamblock", "samples")

VARIANTS = ["full", "no_thump", "no_modes", "thump-6dB", "thump_hi_off"]


def variant_table(base, variant):
    t = copy.deepcopy(base)
    for k in t["keys"]:
        for L in k["layers"]:
            if variant == "no_thump":
                L["thump_db"] = None
            elif variant == "thump-6dB":
                if L.get("thump_db"):
                    L["thump_db"] = [None if v is None else v - 6.0
                                     for v in L["thump_db"]]
            elif variant == "thump_hi_off":
                # kill thump above ~1.5 kHz (last 4 of 10 bands)
                if L.get("thump_db"):
                    L["thump_db"] = [v if i < 6 else None
                                     for i, v in enumerate(L["thump_db"])]
            elif variant == "no_modes":
                for p in L["partials"]:
                    p["a1"] = p["a2"] = 1e-9
    return t


def main():
    base = json.load(open(DEFAULT_TABLE))
    for variant in VARIANTS:
        t = variant_table(base, variant)
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump(t, f)
            path = f.name
        synth = Jamblock(table_path=path)
        scores = []
        cents = []
        for note in NOTES:
            ref_path = os.path.join(SAMPLES, f"{note}v1.flac")
            ref, sr = load_mono(ref_path)
            y = synth.synth_note(name_to_midi(note), LAYER_TO_VEL[1],
                                 dur=min(len(ref) / sr, 1.0))
            m = compare(y, synth.sr, ref_path, note)
            scores.append(composite_score(m))
            cents.append(m["centroid_ratio"])
        os.unlink(path)
        print(f"{variant:14s} mean={sum(scores)/len(scores):6.3f}  "
              f"scores={[f'{s:.2f}' for s in scores]}  "
              f"centroids={[f'{c:.2f}' for c in cents]}")


if __name__ == "__main__":
    main()
