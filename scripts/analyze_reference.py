"""Analyze all downloaded Salamander reference samples -> reference/analysis/*.json"""

import os
import sys
import json
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pianomodel.notes import SALAMANDER_NOTES, SALAMANDER_VELS
from pianomodel.analysis import analyze_to_json

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "samples")
OUT = os.path.join(ROOT, "reference", "analysis")
os.makedirs(OUT, exist_ok=True)


def main():
    only = sys.argv[1:] or None
    done, skipped, failed = 0, 0, []
    for note in SALAMANDER_NOTES:
        for v in SALAMANDER_VELS:
            name = f"{note}v{v}"
            if only and name not in only:
                continue
            src = os.path.join(SAMPLES, f"{name}.flac")
            dst = os.path.join(OUT, f"{name}.json")
            if not os.path.exists(src):
                skipped += 1
                continue
            if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
                done += 1
                continue
            try:
                res = analyze_to_json(src, note, dst)
                print(f"{name}: f0={res['f0']:.2f} Hz  B={res['B']:.2e}  "
                      f"partials={res['n_partials']}", flush=True)
                done += 1
            except Exception:
                failed.append(name)
                traceback.print_exc()
    print(f"\nanalyzed {done}, skipped {skipped}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
