"""Build the koto (long-zither) parameter table from analysis JSONs.

14 sampled pitches B2-B5 (pentatonic-ish grid) x up to 3 dynamics
(mf/f/ff -> velocities 45/90/127; B2 has no mf take). Partials use the
engine's native inharmonic string series — n + per-key (f0, B), no `fr`.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from lab.notes import name_to_midi

NOTES = ["B2", "D#3", "F#3", "G#3", "B3", "C#4", "D#4", "F#4", "G#4",
         "B4", "C#5", "D#5", "F#5", "G#5", "B5"]
LAYERS = [1, 2, 3]
LAYER_TO_VEL = {1: 45, 2: 90, 3: 127}

MAX_PARTIALS = 40


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

        # key-level f0 / B: median across layers (weight by partial count)
        f0 = float(np.median([a["f0"] for a in present.values()]))
        bs = [a["B"] for a in present.values()
              if a["B"] > 1e-8 and a["n_partials"] >= 5]
        B = float(np.median(bs)) if bs else 0.0

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
                "bed_db": a.get("bed_db"),
                "bed_t60": a.get("bed_t60"),
                "bed_anchor_s": a.get("bed_anchor_s", 1.25),
                "partials": partials,
            })
        if layers_out:
            keys.append({"note": note, "midi": name_to_midi(note),
                         "f0": f0, "B": B, "layers": layers_out})

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
        "instrument": "koto",
        "config": {
            "sr": 44100,
            "thump_tau_s": 0.02,
            "thump_tau_bands": thump_tau_bands,
            "attack_s": 0.0015,
            # palm damp on note-off; strings ring if never released
            "release_fade_s": 0.12,
            "release_remnant": 0.0,
            "undamped_above": None,
            # pol_beat_* deliberately absent: dual-polarization beating
            # lost to the plain render on the benchmark (see DEVLOG)
        },
        "keys": keys,
    }
    with open(out_path, "w") as f:
        json.dump(table, f)
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "koto", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "tranh.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t = build_table(analysis_dir, out)
    size = os.path.getsize(out)
    print(f"table: {len(t['keys'])} keys, "
          f"{sum(len(k['layers']) for k in t['keys'])} layers, "
          f"{size/1024:.0f} KiB")
    for k in t["keys"]:
        dev = 1200 * math.log2(k["f0"] / (440.0 * 2 ** ((k["midi"] - 69) / 12)))
        print(f"  {k['note']:4s} midi={k['midi']:3d} f0={k['f0']:7.1f} "
              f"({dev:+5.1f}c) B={k['B']:.2e} layers={len(k['layers'])} "
              f"partials={len(k['layers'][-1]['partials'])}")


if __name__ == "__main__":
    main()
