import json, os, sys
import numpy as np

rows = json.load(open(os.path.join(os.path.dirname(__file__), "..", "output", "eval.json")))
rows.sort(key=lambda r: -r["score"])
print("worst 12:")
for r in rows[:12]:
    print(f"  {r['name']:8s} {r['score']:6.3f}  pc={r['partial_cents']} dec={r['decay_logerr']} "
          f"lsdE={r['lsd_early']} lsdM={r['lsd_mid']} env={r['env_db']} cent={r['centroid_ratio']}")
print("\nby register:")
regs = {"bass A0-A1": (21, 34), "low C2-A2": (35, 46), "mid C3-A3": (47, 58),
        "mid C4-A4": (59, 70), "hi C5-A5": (71, 82), "hi C6-A6": (83, 94),
        "top C7-C8": (95, 109)}
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from instruments.piano.notes import name_to_midi  # noqa
for lab, (lo, hi) in regs.items():
    sel = [r for r in rows if lo <= name_to_midi(r["name"].split("v")[0]) <= hi]
    if sel:
        print(f"  {lab:11s} mean {np.mean([r['score'] for r in sel]):.3f}  "
              f"env {np.mean([r['env_db'] for r in sel]):.1f}  "
              f"lsdE {np.mean([r['lsd_early'] for r in sel]):.1f}  "
              f"lsdM {np.mean([r['lsd_mid'] for r in sel]):.1f}  "
              f"cent {np.mean([r['centroid_ratio'] for r in sel]):.2f}")
print("\nmetric means:", {k: round(float(np.mean([r[k] for r in rows if r[k] is not None])), 3)
      for k in ["partial_cents", "decay_logerr", "lsd_early", "lsd_mid", "env_db", "centroid_ratio", "score"]})
