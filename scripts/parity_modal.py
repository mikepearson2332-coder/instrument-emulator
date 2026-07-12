"""Python-vs-Rust note_params parity for a generic modal instrument.

  python scripts/parity_modal.py rhodes|jamblock|koto|woodblock
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np


def flatten(p):
    out = [p["f0"], p.get("B", 0.0)]
    for prt in sorted(p["partials"], key=lambda q: q["n"]):
        out += [prt["n"], prt.get("fr") or 0.0, prt["a1"], prt["t1"],
                prt["a2"], prt["t2"]]
    for k in ("thump_db", "bed_db", "bed_t60"):
        out += [v if v is not None else -999.0 for v in p.get(k) or []]
    return np.array(out, float)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "rhodes"
    py = importlib.import_module(f"instruments.{name}.synth")
    rs = importlib.import_module(f"instruments.{name}.synth_rs")
    import inspect
    cls = [c for c, o in vars(py).items()
           if inspect.isclass(o) and o.__module__ == py.__name__][0]
    a = getattr(py, cls)()
    b = getattr(rs, cls)()
    worst = 0.0
    for midi in range(21, 109, 4):
        for vel in (12, 40, 70, 100, 127):
            pa = flatten(a.note_params(midi, vel))
            pb = flatten(b.note_params(midi, vel))
            if len(pa) != len(pb):
                print(f"midi={midi} vel={vel}: LENGTH mismatch "
                      f"{len(pa)} vs {len(pb)}")
                worst = float("inf")
                continue
            denom = np.maximum(np.abs(pa), 1e-12)
            rel = float(np.max(np.abs(pa - pb) / denom))
            worst = max(worst, rel)
    print(f"{name}: worst rel diff = {worst:.3e}")


if __name__ == "__main__":
    main()
