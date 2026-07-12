"""Build string-section parameter tables from analysis JSONs.

One table per section (vln/vla/vc/cb) -> params/{sec}.json, appearing
in the testbed as `strings / vln` etc. Layers: VSCO's two dynamics,
ordered by measured steady RMS (soft -> vel 60, loud -> vel 110).
Harmonic amplitudes are stored absolute: the strongest harmonic's
amplitude A solves rms_ss^2 = sum((A*r_n)^2 / 2).

Ensemble/config parameters that section recordings cannot cleanly
separate (drift vs vibrato FM depth, per-harmonic AM) live in `config`
and are fitted against the modulation benchmark — see DEVLOG.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

SECTIONS = ["vln", "vla", "vc", "cb"]
LAYER_TO_VEL = {1: 60, 2: 110}

# drift/vib depths are benchmark-fitted (scripts/sweep_strings_cfg.py:
# vib 3c + drift 4c minimized harm_db+score; deeper vibrato double-smears
# the already-section-smeared harmonic peaks), not measured — see DEVLOG
CONFIG = {
    "engine": "sustained",
    "sr": 44100,
    "drift_cents": 4.0,
    "drift_hz": 1.0,
    "vib_cents": 3.0,
    "harm_am_db": 1.0,
}


def build_section(analysis_dir: str, sec: str, out_path: str) -> dict | None:
    files = [f for f in os.listdir(analysis_dir)
             if f.startswith(sec + "_") and f.endswith(".json")
             and "_alt" not in f and not f.startswith("cb_nv" if sec == "cb" else "\0")]
    if sec == "cb":
        files = [f for f in files if not f.startswith("cb_nv")]
    by_note: dict[str, dict[int, dict]] = {}
    for fn in files:
        with open(os.path.join(analysis_dir, fn)) as f:
            a = json.load(f)
        stem = fn[:-5]
        note, layer = stem[len(sec) + 1:].split("v")
        by_note.setdefault(note, {})[int(layer)] = a
    if not by_note:
        return None

    keys = []
    for note, layers in sorted(by_note.items(),
                               key=lambda kv: next(iter(kv[1].values()))["midi"]):
        f0 = float(np.median([a["f0"] for a in layers.values()]))
        # order layers soft -> loud by steady rms
        order = sorted(layers.items(), key=lambda kv: kv[1]["rms_ss"])
        layers_out = []
        for li, (orig_layer, a) in enumerate(order, start=1):
            rs = [10 ** (h["db"] / 20) for h in a["harm"]]
            if not rs:
                continue
            A = a["rms_ss"] * math.sqrt(2.0 / sum(r * r for r in rs))
            harm = [{"n": h["n"], "a": A * 10 ** (h["db"] / 20)}
                    for h in a["harm"]]
            layers_out.append({
                "vel": LAYER_TO_VEL[li],
                "layer": orig_layer,
                "peak": a["peak_abs"],
                "rms": a["rms_ss"],
                "harm": harm,
                "noise_db": a["noise_db"],
                "rise_s": a["rise_s"],
                # caps: bow-change notches in solo takes measure as
                # enormous log-domain modulation "depths" and the
                # exponentiating renderer blows up (cb peaks hit 1e5).
                # Steady ensemble texture is a few dB at most.
                "und_db": min(a["und_db"], 3.5),
                "und_hz": a["und_hz"],
                "vib_hz": a["vib_hz"],
                "vib_am_db": min(a["vib_am_db"], 2.5),
                "rel_s": a["rel_s"], "rel_remnant": a["rel_remnant"],
                "rel_tail_s": a["rel_tail_s"],
            })
        if layers_out:
            midi = next(iter(layers.values()))["midi"]
            keys.append({"note": note, "midi": midi, "f0": f0,
                         "layers": layers_out})

    table = {"version": 1, "instrument": f"strings-{sec}",
             "config": dict(CONFIG), "keys": keys}
    with open(out_path, "w") as f:
        json.dump(table, f)
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "strings", "analysis")
    outdir = os.path.join(os.path.dirname(__file__), "params")
    os.makedirs(outdir, exist_ok=True)
    for sec in SECTIONS:
        out = os.path.join(outdir, f"{sec}.json")
        t = build_section(analysis_dir, sec, out)
        if t is None:
            print(f"{sec}: no analysis")
            continue
        size = os.path.getsize(out)
        ks = t["keys"]
        print(f"{sec}: {len(ks)} keys midi {ks[0]['midi']}..{ks[-1]['midi']} "
              f"{size/1024:.0f} KiB")


if __name__ == "__main__":
    main()
