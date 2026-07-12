"""Build the vibraphone parameter table from reference analysis JSONs.

42 chromatic keys (C3-F6) x 3 dynamics (pp/mf/ff -> velocities 24/80/127).
Modes are clustered across layers per key for stable indices; per-layer
frequencies stored as ratios `fr` to the key f0. Keys whose pp take is
missing (E4, G#4, C#6 — see DEVLOG gate 1) get an imputed pp layer: the mf
layer scaled by the global median pp/mf amplitude ratio and thump offset.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from lab.notes import midi_to_name, name_to_midi

NOTES = [midi_to_name(m) for m in range(48, 90)]  # C3..F6
LAYERS = [1, 2, 3]
LAYER_TO_VEL = {1: 24, 2: 80, 3: 127}

CLUSTER_TOL = 0.025


def _cluster_modes(per_layer: dict[int, list[dict]]):
    items = [(layer, m) for layer, ms in per_layer.items() for m in ms]
    items.sort(key=lambda im: im[1]["freq"])
    clusters = []
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


def _mode_ok(m: dict) -> bool:
    """Reject junk fits: noise-floor 'decays' and sub-SNR envelopes."""
    if "a_fast" not in m:
        return False
    if m.get("snr", 1e9) < 5.0:
        return False
    if m["tau_fast"] > 45.0 and m["a_slow"] <= 0:
        return False
    return True


def _layer_entry(a: dict, clusters, layer: int, f0: float, vel: float):
    partials = []
    for ci, c in enumerate(clusters):
        got = next((m for l, m in c if l == layer), None)
        if got is None or not _mode_ok(got):
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
        return None
    return {
        "vel": vel,
        "layer": layer,
        "peak": a["peak_abs"],
        "rms": a["rms_max"],
        "centroid": a["centroid_300ms"],
        "thump_db": a.get("thump_db"),
        "bed_db": a.get("bed_db"),
        "bed_t60": a.get("bed_t60"),
        "bed_anchor_s": a.get("bed_anchor_s", 2.15),
        "partials": partials,
    }


def _impute_pp(mf_layer: dict, amp_ratio: float, thump_off: float,
               vel: float) -> dict:
    out = json.loads(json.dumps(mf_layer))  # deep copy
    out["vel"] = vel
    out["layer"] = 1
    out["imputed"] = True
    for p in out["partials"]:
        p["a1"] *= amp_ratio
        p["a2"] *= amp_ratio
    for key in ("thump_db", "bed_db"):
        if out.get(key):
            out[key] = [None if v is None else round(v + thump_off, 2)
                        for v in out[key]]
    out["peak"] = mf_layer["peak"] * amp_ratio
    out["rms"] = mf_layer["rms"] * amp_ratio
    return out


def build_table(analysis_dir: str, out_path: str,
                damper_fade_s: float | None = None) -> dict:
    raw = {}
    for note in NOTES:
        for layer in LAYERS:
            p = os.path.join(analysis_dir, f"{note}v{layer}.json")
            if os.path.exists(p):
                with open(p) as f:
                    raw[(note, layer)] = json.load(f)

    # global pp/mf ratios from keys that have both (for imputation)
    ratios, offs = [], []
    for note in NOTES:
        a1 = raw.get((note, 1))
        a2 = raw.get((note, 2))
        if a1 and a2:
            ratios.append(a1["rms_max"] / (a2["rms_max"] + 1e-20))
            t1 = [v for v in (a1.get("thump_db") or []) if v is not None]
            t2 = [v for v in (a2.get("thump_db") or []) if v is not None]
            if t1 and t2:
                offs.append(np.median(t1) - np.median(t2))
    amp_ratio = float(np.median(ratios)) if ratios else 0.25
    thump_off = float(np.median(offs)) if offs else -12.0

    keys = []
    n_imputed = 0
    for note in NOTES:
        present = {l: raw[(note, l)] for l in LAYERS if (note, l) in raw}
        if not present:
            continue
        per_layer = {l: a["modes"] for l, a in present.items()}
        clusters = _cluster_modes(per_layer)
        f0 = float(np.median([a["f0"] for a in present.values()]))

        layers_out = []
        for layer in LAYERS:
            a = present.get(layer)
            if a is None:
                continue
            e = _layer_entry(a, clusters, layer, f0, LAYER_TO_VEL[layer])
            if e:
                layers_out.append(e)
        # pp per-key repair: soft strikes often lose weak modes to the SNR
        # gates — inherit them from mf scaled by this key's fundamental
        # pp/mf ratio. A pp layer whose FUNDAMENTAL is unfittable is
        # dropped entirely (whole-layer imputation below).
        mf = next((L for L in layers_out if L["layer"] == 2), None)
        pp = next((L for L in layers_out if L["layer"] == 1), None)
        if pp and mf:
            pp_by_n = {p["n"]: p for p in pp["partials"]}
            mf_by_n = {p["n"]: p for p in mf["partials"]}
            fund_n = min(mf_by_n,
                         key=lambda n: abs(mf_by_n[n]["fr"] - 1.0))
            if fund_n not in pp_by_n:
                layers_out.remove(pp)
            else:
                r = pp_by_n[fund_n]["a1"] / (mf_by_n[fund_n]["a1"] + 1e-20)
                r = min(max(r, 0.05), 1.5)
                for n, mp in mf_by_n.items():
                    if n not in pp_by_n:
                        q = dict(mp)
                        q["a1"] = mp["a1"] * r
                        q["a2"] = mp["a2"] * r
                        pp["partials"].append(q)
                pp["partials"].sort(key=lambda p: p["n"])
        # impute pp from mf if missing
        if not any(L["layer"] == 1 for L in layers_out):
            mf = next((L for L in layers_out if L["layer"] == 2), None)
            if mf:
                layers_out.insert(0, _impute_pp(mf, amp_ratio, thump_off,
                                                LAYER_TO_VEL[1]))
                n_imputed += 1
        layers_out.sort(key=lambda L: L["vel"])
        if layers_out:
            keys.append({"note": note, "midi": name_to_midi(note),
                         "f0": f0, "B": 0.0, "layers": layers_out})

    # table-wide per-band click decay
    taus = []
    for a in raw.values():
        if a.get("thump_tau"):
            taus.append([t if t is not None else np.nan
                         for t in a["thump_tau"]])
    med = np.nanmedian(np.array(taus, float), axis=0)
    thump_tau_bands = [round(float(v), 4) if v == v else 0.03 for v in med]

    table = {
        "version": 1,
        "instrument": "vibraphone",
        "config": {
            "sr": 44100,
            "thump_tau_s": 0.03,
            "thump_tau_bands": thump_tau_bands,
            "attack_s": 0.002,
            "release_fade_s": round(damper_fade_s or 0.15, 3),
            "release_remnant": 0.0,
            "undamped_above": None,   # every bar is damped
            # bank loudness normalization, piano-anchored
            # (scripts/measure_bank_loudness.py)
            "gain_db": 4.7,
        },
        "keys": keys,
    }
    with open(out_path, "w") as f:
        json.dump(table, f)
    print(f"imputed pp layers: {n_imputed}; damper fade "
          f"{table['config']['release_fade_s']}s; "
          f"pp/mf ratio {amp_ratio:.3f}, thump offset {thump_off:+.1f} dB")
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "vibraphone", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "vibes.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    from .analysis import measure_damper_fade
    dampen_dir = os.path.join(root, "reference", "vibraphone", "samples",
                              "dampen")
    fade = measure_damper_fade(dampen_dir)

    t = build_table(analysis_dir, out, damper_fade_s=fade)
    n_layers = sum(len(k["layers"]) for k in t["keys"])
    size = os.path.getsize(out)
    print(f"table: {len(t['keys'])} keys, {n_layers} layers, "
          f"{size/1024:.0f} KiB")
    for k in t["keys"][::6]:
        dev = 1200 * math.log2(k["f0"] / (440.0 * 2 ** ((k["midi"] - 69) / 12)))
        frs = " ".join(f"{p['fr']:.2f}" for p in k["layers"][-1]["partials"][:5])
        print(f"  {k['note']:4s} f0={k['f0']:7.1f} ({dev:+5.1f}c) "
              f"layers={len(k['layers'])} fr=[{frs}]")


if __name__ == "__main__":
    main()
