"""Build a compact synthesis parameter table from reference analysis JSONs.

The table is the only data the synthesizer ships: per sampled key the
fundamental (with Railsback stretch) and inharmonicity B, plus per velocity
layer the per-partial (initial amplitude, fast/slow decay constants).
B and f0 are smoothed across the keyboard so sparse-treble notes (only 3-4
partials below Nyquist) don't get nonsense fits.
"""

from __future__ import annotations

import json
import os
import math

import numpy as np

from .notes import SALAMANDER_NOTES, SALAMANDER_VELS, name_to_midi, midi_to_freq

# Salamander layer -> approximate MIDI velocity (16 layers spread over 1..127)
LAYER_TO_VEL = {1: 8, 6: 48, 11: 88, 16: 127}

MAX_PARTIALS = 80


def _robust_polyfit(x, y, deg, w=None, iters=4, thresh=2.5):
    """Least-squares polyfit with iterative outlier rejection."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    w = np.ones_like(x) if w is None else np.asarray(w, float)
    keep = np.ones(len(x), bool)
    coef = np.polyfit(x, y, deg, w=w)
    for _ in range(iters):
        if keep.sum() <= deg + 1:
            break
        coef = np.polyfit(x[keep], y[keep], deg, w=w[keep])
        resid = y - np.polyval(coef, x)
        s = np.std(resid[keep]) + 1e-12
        new_keep = np.abs(resid) < thresh * s
        if (new_keep == keep).all():
            break
        keep = new_keep
    return coef


def build_table(analysis_dir: str, out_path: str, symp_path: str | None = None) -> dict:
    raw = {}
    for note in SALAMANDER_NOTES:
        for layer in SALAMANDER_VELS:
            p = os.path.join(analysis_dir, f"{note}v{layer}.json")
            if os.path.exists(p):
                with open(p) as f:
                    raw[(note, layer)] = json.load(f)

    symp = None
    if symp_path and os.path.exists(symp_path):
        with open(symp_path) as f:
            symp = json.load(f)

    def _cluster_logB(vals, wts, radius=0.2):
        """Largest agreeing cluster of log10(B) layer estimates.
        Returns (weighted mean, member count) of the heaviest window."""
        order = np.argsort(vals)
        vals = np.asarray(vals)[order]
        wts = np.asarray(wts, float)[order]
        best = (0.0, 0, 0.0)  # (weight, count, mean)
        for i in range(len(vals)):
            sel = np.abs(vals - vals[i]) <= radius
            wsum = wts[sel].sum()
            if wsum > best[0]:
                best = (wsum, int(sel.sum()), float(np.average(vals[sel], weights=wts[sel])))
        return best[2], best[1]

    # ---- pass 1: per-key B consensus across velocity layers ---------------
    key_b: dict[str, tuple[float, int]] = {}
    for note in SALAMANDER_NOTES:
        vals, wts = [], []
        for layer in SALAMANDER_VELS:
            a = raw.get((note, layer))
            if a and a["B"] > 1e-7 and a["n_partials"] >= 3:
                vals.append(math.log10(a["B"]))
                wts.append(min(a["n_partials"], 30))
        if vals:
            key_b[note] = _cluster_logB(vals, wts)

    # ---- pass 2: keyboard trend from cluster-confident keys ---------------
    midis, logBs, wgts, devs = [], [], [], []
    for note, (logb, count) in key_b.items():
        if count >= 2:
            midis.append(name_to_midi(note))
            logBs.append(logb)
            wgts.append(count)
    for (note, layer), a in raw.items():
        m = name_to_midi(note)
        if a["n_partials"] >= 2:
            dev = 1200 * math.log2(a["f0"] / midi_to_freq(m))
            if abs(dev) < 60:
                devs.append((m, dev, min(a["n_partials"], 30)))

    b_coef = _robust_polyfit(midis, logBs, 3, w=wgts)
    d_m = [d[0] for d in devs]
    d_v = [d[1] for d in devs]
    d_w = [d[2] for d in devs]
    stretch_coef = _robust_polyfit(d_m, d_v, 3, w=d_w)

    def b_trend(m):
        return 10 ** float(np.polyval(b_coef, m))

    def stretch_trend(m):
        return float(np.polyval(stretch_coef, m))

    # ---- per-key values ----------------------------------------------------
    keys = []
    for note in SALAMANDER_NOTES:
        midi = name_to_midi(note)
        present = [(l, raw[(note, l)]) for l in SALAMANDER_VELS if (note, l) in raw]
        if not present:
            continue

        # key-level B: cluster consensus if >=2 layers agree, else trend
        trend = b_trend(midi)
        B = trend
        if note in key_b:
            logb, count = key_b[note]
            if count >= 2 or abs(logb - math.log10(trend)) < 0.5:
                B = 10 ** logb

        # key-level f0: cluster-consensus of layer deviations; the Railsback
        # trend only backstops keys whose layers disagree
        devs_k = np.array([1200 * math.log2(a["f0"] / midi_to_freq(midi))
                           for _, a in present])
        tr = stretch_trend(midi)
        dev = tr
        best_members = 0
        for d0 in devs_k:
            sel = np.abs(devs_k - d0) <= 6.0
            if sel.sum() > best_members:
                best_members = int(sel.sum())
                dev = float(np.median(devs_k[sel]))
        if best_members < 2 and abs(dev - tr) > 25:
            dev = tr
        f0 = midi_to_freq(midi) * 2 ** (dev / 1200)

        layers = []
        for layer, a in present:
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
            layers.append({
                "vel": LAYER_TO_VEL[layer],
                "layer": layer,
                "peak": a["peak_abs"],
                "rms": a["rms_max"],
                "centroid": a["centroid_300ms"],
                "thump_db": a.get("thump_db"),
                "bed_db": a.get("bed_db"),
                "bed_t60": a.get("bed_t60"),
                "bed_anchor_s": a.get("bed_anchor_s", 1.5),
                "symp_db": (symp["notes"].get(f"{note}v{layer}")
                            if symp else None),
                "partials": partials,
            })
        if layers:
            keys.append({"note": note, "midi": midi, "f0": f0, "B": B,
                         "stretch_cents": round(dev, 2), "layers": layers})

    table = {
        "version": 3,
        "b_trend_coef": [float(c) for c in b_coef],
        "stretch_coef": [float(c) for c in stretch_coef],
        "symp_lines": symp["lines"] if symp else [],
        "symp_anchor_s": symp["anchor_s"] if symp else 1.2,
        "keys": keys,
    }
    with open(out_path, "w") as f:
        json.dump(table, f)
    return table


def main():
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    analysis_dir = os.path.join(root, "reference", "piano", "analysis")
    out = os.path.join(os.path.dirname(__file__), "params", "grand.json")
    symp = os.path.join(root, "reference", "piano", "symp.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    t = build_table(analysis_dir, out, symp_path=symp)
    n_keys = len(t["keys"])
    n_layers = sum(len(k["layers"]) for k in t["keys"])
    size = os.path.getsize(out)
    print(f"table: {n_keys} keys, {n_layers} layers, {size/1024:.0f} KiB")
    for k in t["keys"]:
        print(f"  {k['note']:4s} midi={k['midi']:3d} f0={k['f0']:8.2f} "
              f"B={k['B']:.2e} stretch={k['stretch_cents']:+.1f}c "
              f"layers={len(k['layers'])}")


if __name__ == "__main__":
    main()
