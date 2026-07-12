"""Build the Rhodes (tine EP) parameter table from analysis JSONs.

15 sampled pitches F1-C7 x up to 5 dynamics (jRhodes3d sfz groups ->
velocities 24/60/84/104/120; B4/E5 lack v3, A5/D6/G6/C7 lack v3+v5).
Partials are exact harmonics: engine-native n-series with B = 0.

DI recording -> the 'bed' is preamp hiss + skirt leakage, not room:
bed entries quieter than BED_GATE_DB below that layer's loudest thump
band are dropped (None -> engine silence). The hammer/key thunk rides
in the thump bands.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from lab.notes import name_to_midi

NOTES = ["F1", "B1", "E2", "A2", "D3", "G3", "B3", "D4", "F4",
         "B4", "E5", "A5", "D6", "G6", "C7"]
LAYERS = [1, 2, 3, 4, 5]
LAYER_TO_VEL = {1: 24, 2: 60, 3: 84, 4: 104, 5: 120}

MAX_PARTIALS = 24
BED_GATE_DB = 45.0


def _gate_bed(thump_db, bed_db):
    if not bed_db:
        return bed_db
    tv = [v for v in (thump_db or []) if v is not None]
    if not tv:
        return bed_db
    gate = max(tv) - BED_GATE_DB
    return [None if (v is None or v < gate) else v for v in bed_db]


def build_table(analysis_dir: str, out_path: str) -> dict:
    keys = []
    for note in NOTES:
        present = {}
        for layer in LAYERS:
            p = os.path.join(analysis_dir, f"{note}v{layer}.json")
            if os.path.exists(p):
                with open(p) as f:
                    present[layer] = json.load(f)
        if not present:
            continue

        f0 = float(np.median([a["f0"] for a in present.values()]))

        layers_out = []
        for layer, a in sorted(present.items()):
            partials = []
            for prt in a["partials"][:MAX_PARTIALS]:
                if "a_fast" not in prt:
                    continue
                partials.append({
                    "n": prt["n"],
                    "a1": prt["a_fast"] * a["peak_abs"],
                    "t1": prt["tau_fast"],
                    "a2": prt["a_slow"] * a["peak_abs"],
                    "t2": prt["tau_slow"],
                })
            if not partials:
                continue
            layers_out.append({
                "vel": LAYER_TO_VEL[layer],
                "layer": layer,
                "peak": a["peak_abs"],
                "rms": a["rms_max"],
                "centroid": a["centroid_150ms"],
                "thump_db": a.get("thump_db"),
                "bed_db": _gate_bed(a.get("thump_db"), a.get("bed_db")),
                "bed_t60": a.get("bed_t60"),
                "bed_anchor_s": a.get("bed_anchor_s", 1.25),
                "partials": partials,
            })
        if layers_out:
            keys.append({"note": note, "midi": name_to_midi(note),
                         "f0": f0, "B": 0.0, "layers": layers_out})

    taus = []
    for fn in os.listdir(analysis_dir):
        with open(os.path.join(analysis_dir, fn)) as f:
            a = json.load(f)
        if a.get("thump_tau"):
            taus.append([t if t is not None else np.nan
                         for t in a["thump_tau"]])
    med = np.nanmedian(np.array(taus, float), axis=0)
    thump_tau_bands = [round(float(v), 4) if v == v else 0.02 for v in med]

    table = {
        "version": 1,
        "instrument": "rhodes",
        "config": {
            "sr": 44100,
            "thump_tau_s": 0.02,
            "thump_tau_bands": thump_tau_bands,
            "attack_s": 0.002,
            # felt/neoprene dampers: fast fade on key release, everywhere
            "release_fade_s": 0.15,
            "release_remnant": 0.0,
            "undamped_above": None,
        },
        "keys": keys,
    }
    with open(out_path, "w") as f:
        json.dump(table, f)
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "rhodes", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "mk1.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t = build_table(analysis_dir, out)
    size = os.path.getsize(out)
    print(f"table: {len(t['keys'])} keys, "
          f"{sum(len(k['layers']) for k in t['keys'])} layers, "
          f"{size/1024:.0f} KiB")
    for k in t["keys"]:
        dev = 1200 * math.log2(k["f0"] / (440.0 * 2 ** ((k["midi"] - 69) / 12)))
        print(f"  {k['note']:4s} midi={k['midi']:3d} f0={k['f0']:7.1f} "
              f"({dev:+5.1f}c) layers={len(k['layers'])} "
              f"partials={len(k['layers'][-1]['partials'])}")


if __name__ == "__main__":
    main()
