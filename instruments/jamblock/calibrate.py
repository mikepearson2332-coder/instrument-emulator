"""Build the jam block parameter table from analysis JSONs.

4 keys (E5/F#5/G5/C6 — 4 distinct plastic blocks anchored at their
measured dominant modes) x ONE recorded dynamic. The reference has no
velocity layers (SOURCES.md), so playable soft/loud layers are DERIVED:
the VCSL woodblock's calibrated table (same modal family, real pp->ff
measurement) supplies level + spectral-tilt + click deltas between its
soft/mid/loud layers, which are applied to each block's measured layer.
Derived layers are for playability only — the benchmark scores the
recorded dynamic (vel 96).
"""

from __future__ import annotations

import json
import math
import os

import numpy as np

from lab.notes import name_to_midi

NOTES = ["E5", "F#5", "G5", "C6"]
LAYERS = [1]
LAYER_TO_VEL = {1: 96}

DERIVED_VELS = {"soft": 20, "loud": 127}

WB_TABLE = os.path.join(os.path.dirname(__file__), "..", "woodblock",
                        "params", "block.json")


def _amp(p):
    return p["a1"] + p["a2"]


def _layer_delta(wb_key, vel_from, vel_to):
    """(level_db, tilt_db_per_oct, thump_delta[bands]) from woodblock."""
    layers = {L["vel"]: L for L in wb_key["layers"]}
    a, b = layers[vel_from], layers[vel_to]
    bp = {p["n"]: p for p in b["partials"]}
    ds, lf = [], []
    for p in a["partials"]:
        q = bp.get(p["n"])
        if q is None or _amp(p) <= 0 or _amp(q) <= 0:
            continue
        ds.append(20 * math.log10(_amp(p) / _amp(q)))
        lf.append(math.log2(p["fr"]))
    A = np.stack([np.ones(len(lf)), np.array(lf)], axis=1)
    (c0, c1), *_ = np.linalg.lstsq(A, np.array(ds), rcond=None)
    ta = a.get("thump_db") or []
    tb = b.get("thump_db") or []
    thump_d = [(x - y) if (x is not None and y is not None) else 0.0
               for x, y in zip(ta, tb)]
    return float(c0), float(c1), thump_d


def _derive_layer(base, vel, c0, c1, thump_d):
    out = {
        "vel": vel,
        "layer": 0,
        "peak": base["peak"] * 10 ** (c0 / 20),
        "rms": base["rms"] * 10 ** (c0 / 20),
        "centroid": base["centroid"],
        "thump_db": [
            (v + d) if v is not None else None
            for v, d in zip(base["thump_db"], thump_d)
        ] if base.get("thump_db") else None,
        "bed_db": None,
        "bed_t60": None,
        "bed_anchor_s": base.get("bed_anchor_s", 0.2),
        "partials": [],
    }
    for p in base["partials"]:
        g = 10 ** ((c0 + c1 * math.log2(max(p["fr"], 1e-6))) / 20)
        out["partials"].append({**p, "a1": p["a1"] * g, "a2": p["a2"] * g})
    return out


def build_table(analysis_dir: str, out_path: str) -> dict:
    with open(os.path.abspath(WB_TABLE)) as f:
        wb_key = json.load(f)["keys"][0]
    c0s, c1s, td_s = _layer_delta(wb_key, 20, 96)    # soft vs mid
    c0l, c1l, td_l = _layer_delta(wb_key, 127, 96)   # loud vs mid

    keys = []
    for note in NOTES:
        p = os.path.join(analysis_dir, f"{note}v1.json")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            a = json.load(f)
        f0 = a["f0"]
        partials = []
        amax = max((m["a_fast"] + m["a_slow"] for m in a["modes"]
                    if "a_fast" in m), default=0.0)
        for i, m in enumerate(a["modes"]):
            if "a_fast" not in m:
                continue
            a1, t1 = m["a_fast"], m["tau_fast"]
            a2, t2 = m["a_slow"], m["tau_slow"]
            # codec-floor guards: the Vorbis noise floor flattens ring-out
            # envelopes, minting "no decay" (tau 100 s) slow stages and
            # -60 dB junk modes with meaningless taus. A plastic block is
            # silent within ~0.3 s — anything slower is the codec.
            if a1 + a2 < amax * 10 ** (-50 / 20):
                continue
            if t2 > 0.3:
                if a2 < 0.1 * a1:
                    a2, t2 = 0.0, t1        # drop the phantom tail
                else:
                    t2 = 0.3
            t1 = min(t1, 0.3)
            partials.append({
                "n": i + 1,
                "fr": m["freq"] / f0,
                "a1": a1 * a["peak_abs"],
                "t1": t1,
                "a2": a2 * a["peak_abs"],
                "t2": t2,
            })
        if not partials:
            continue
        # -6 dB codec compensation: the Vorbis/MP3 previews noise-fill
        # the quiet inter-mode bins around the transient, inflating the
        # measured click level (band diag: +7 dB at 1.6-2.8 kHz early;
        # mute-one-component attribution confirmed the direction). Redo
        # from original WAVs when available (SOURCES.md upgrade path).
        thump = a.get("thump_db")
        if thump:
            thump = [None if v is None else v - 6.0 for v in thump]
        measured = {
            "vel": LAYER_TO_VEL[1],
            "layer": 1,
            "peak": a["peak_abs"],
            "rms": a["rms_max"],
            "centroid": a["centroid_60ms"],
            "thump_db": thump,
            # bed dropped (woodblock precedent: bed = recording room)
            "bed_db": None,
            "bed_t60": None,
            "bed_anchor_s": a.get("bed_anchor_s", 0.2),
            "partials": partials,
        }
        layers_out = [
            _derive_layer(measured, DERIVED_VELS["soft"], c0s, c1s, td_s),
            measured,
            _derive_layer(measured, DERIVED_VELS["loud"], c0l, c1l, td_l),
        ]
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
    # 12 ms cap (woodblock uses 20): this reference is DI-dry, and the
    # measured band slopes flatten on the codec noise floor — the real
    # stick-on-plastic click is <=10 ms (band diag: mid-time +10..+29 dB
    # with 20 ms taus)
    thump_tau_bands = [round(min(float(v), 0.012), 4) if v == v else 0.01
                       for v in med]

    table = {
        "version": 1,
        "instrument": "jamblock",
        "config": {
            "sr": 44100,
            "thump_tau_s": 0.010,
            "thump_tau_bands": thump_tau_bands,
            "attack_s": 0.0015,
            "release_fade_s": None,   # no dampers: note-off is a no-op
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
    analysis_dir = os.path.join(root, "reference", "jamblock", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "jam.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t = build_table(analysis_dir, out)
    size = os.path.getsize(out)
    for k in t["keys"]:
        print(f"{k['note']:3s} midi={k['midi']} f0={k['f0']:7.1f} Hz "
              f"layers={len(k['layers'])} "
              f"modes={len(k['layers'][1]['partials'])}")
    print(f"table: {size/1024:.1f} KiB -> {out}")


if __name__ == "__main__":
    main()
