"""Compare two eval runs note-by-note (default: output/eval.json vs
output/eval_rust.json). Reports mean/median deltas and the largest movers."""

import json
import os
import sys

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load(name):
    with open(os.path.join(ROOT, "output", name)) as f:
        return {r["name"]: r for r in json.load(f)}


def main():
    a_name = sys.argv[1] if len(sys.argv) > 1 else "eval.json"
    b_name = sys.argv[2] if len(sys.argv) > 2 else "eval_rust.json"
    a, b = load(a_name), load(b_name)
    common = sorted(set(a) & set(b))
    da = np.array([a[n]["score"] for n in common])
    db = np.array([b[n]["score"] for n in common])
    d = db - da
    print(f"{a_name}: mean {da.mean():.3f}   {b_name}: mean {db.mean():.3f}   "
          f"delta {db.mean() - da.mean():+.4f}")
    print(f"per-note delta: median {np.median(d):+.3f}  std {d.std():.3f}  "
          f"worse {int((d > 0).sum())}/{len(d)} notes")
    order = np.argsort(-np.abs(d))
    print("largest movers:")
    for i in order[:8]:
        n = common[i]
        print(f"  {n:8s} {da[i]:6.3f} -> {db[i]:6.3f}  ({d[i]:+.3f})")


if __name__ == "__main__":
    main()
