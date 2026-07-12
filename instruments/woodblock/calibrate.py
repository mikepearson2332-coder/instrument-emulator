"""Build the woodblock parameter table from reference analysis JSONs.

One block, four dynamic layers. Modes are clustered across layers by
frequency proximity so each physical mode keeps a stable index n (the
key/velocity interpolators match partials by n); per-layer frequencies are
stored as ratios `fr` to the key f0 (the engine's non-string mode series).
"""

from __future__ import annotations

import json
import os

import numpy as np

from lab.notes import name_to_midi

NOTES = ["F6"]
LAYERS = [1, 2, 3, 4]
LAYER_TO_VEL = {1: 20, 2: 56, 3: 96, 4: 127}

CLUSTER_TOL = 0.035  # modes within 3.5% across layers are the same mode


def _cluster_modes(per_layer: dict[int, list[dict]]) -> list[list[tuple[int, dict]]]:
    """Group modes of all layers into frequency clusters.

    Returns clusters as lists of (layer, mode-dict), sorted by frequency."""
    items = [(layer, m) for layer, ms in per_layer.items() for m in ms]
    items.sort(key=lambda im: im[1]["freq"])
    clusters: list[list[tuple[int, dict]]] = []
    for layer, m in items:
        placed = False
        for c in clusters:
            cf = np.mean([mm["freq"] for _, mm in c])
            if abs(m["freq"] - cf) / cf < CLUSTER_TOL and not any(
                    l == layer for l, _ in c):
                c.append((layer, m))
                placed = True
                break
        if not placed:
            clusters.append([(layer, m)])
    clusters.sort(key=lambda c: np.mean([m["freq"] for _, m in c]))
    return clusters


def build_table(analysis_dir: str, out_path: str) -> dict:
    keys = []
    for note in NOTES:
        raw = {}
        for layer in LAYERS:
            p = os.path.join(analysis_dir, f"{note}v{layer}.json")
            if os.path.exists(p):
                with open(p) as f:
                    raw[layer] = json.load(f)
        if not raw:
            continue

        per_layer = {layer: a["modes"] for layer, a in raw.items()}
        clusters = _cluster_modes(per_layer)

        # key f0: cluster holding the most per-layer dominant modes
        def dom_votes(c):
            return sum(1 for _, m in c if m["amp"] >= 0.999)

        anchor = max(clusters, key=lambda c: (dom_votes(c), len(c)))
        f0 = float(np.median([m["freq"] for _, m in anchor]))

        layers_out = []
        for layer in LAYERS:
            a = raw.get(layer)
            if a is None:
                continue
            partials = []
            for ci, c in enumerate(clusters):
                got = next((m for l, m in c if l == layer), None)
                if got is None or "a_fast" not in got:
                    continue
                partials.append({
                    "n": ci + 1,
                    "fr": got["freq"] / f0,
                    "a1": got["a_fast"] * a["peak_abs"],
                    "t1": got["tau_fast"],
                    "a2": got["a_slow"] * a["peak_abs"],
                    "t2": got["tau_slow"],
                })
            if not partials:
                continue
            layers_out.append({
                "vel": LAYER_TO_VEL[layer],
                "layer": layer,
                "peak": a["peak_abs"],
                "rms": a["rms_max"],
                "centroid": a["centroid_60ms"],
                "thump_db": a.get("thump_db"),
                # bed deliberately dropped: it is the VCSL room's early
                # reflections, not the instrument — modeled faithfully it
                # reads as a snare rattle when played dry (ears > score;
                # same class of call as the piano's hum lines)
                "bed_db": None,
                "bed_t60": None,
                "bed_anchor_s": a.get("bed_anchor_s", 0.2),
                "partials": partials,
            })
        if layers_out:
            keys.append({"note": note, "midi": name_to_midi(note),
                         "f0": f0, "B": 0.0, "layers": layers_out})

    # table-wide per-band click decay: median across all analyzed takes
    # (velocity dependence of the click tau is minor; keeping it in config
    # lets the engine calibrate each band's noise once at init)
    taus = []
    for fn in os.listdir(analysis_dir):
        with open(os.path.join(analysis_dir, fn)) as f:
            a = json.load(f)
        if a.get("thump_tau"):
            taus.append([t if t is not None else np.nan for t in a["thump_tau"]])
    if taus:
        med = np.nanmedian(np.array(taus, float), axis=0)
        # cap at 20 ms: the stick-contact click is 5-15 ms; anything
        # longer in the band medians is early room response (see bed note)
        thump_tau_bands = [round(min(float(v), 0.02), 4) if v == v else 0.01
                           for v in med]
    else:
        thump_tau_bands = None

    table = {
        "version": 1,
        "instrument": "woodblock",
        "config": {
            "sr": 44100,
            "thump_tau_s": 0.010,
            "thump_tau_bands": thump_tau_bands,
            "attack_s": 0.0015,
            "release_fade_s": None,   # no dampers: note-off is a no-op
            "release_remnant": 0.0,
            "undamped_above": None,
            # bank loudness normalization, piano-anchored
            # (scripts/measure_bank_loudness.py)
            "gain_db": 3.9,
        },
        "keys": keys,
    }
    with open(out_path, "w") as f:
        json.dump(table, f)
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "woodblock", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "block.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t = build_table(analysis_dir, out)
    size = os.path.getsize(out)
    for k in t["keys"]:
        print(f"{k['note']} midi={k['midi']} f0={k['f0']:.1f} Hz "
              f"layers={len(k['layers'])}")
        for L in k["layers"]:
            frs = " ".join(f"{p['fr']:.3f}" for p in L["partials"])
            print(f"  v{L['layer']} vel={L['vel']:3d} modes={len(L['partials'])} fr=[{frs}]")
    print(f"table: {size/1024:.1f} KiB -> {out}")


if __name__ == "__main__":
    main()
