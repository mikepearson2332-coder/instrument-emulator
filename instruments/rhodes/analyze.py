"""Analyze rhodes reference samples -> reference/rhodes/analysis/*.json

  python -m instruments.rhodes.analyze [B3v2 ...]
"""

import os
import sys
import traceback

from .analysis import analyze_to_json
from .calibrate import LAYERS, NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "rhodes", "samples")
OUT = os.path.join(ROOT, "reference", "rhodes", "analysis")


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or None
    names = [f"{note}v{v}" for note in NOTES for v in LAYERS]
    done, failed = 0, []
    for name in names:
        if only and name not in only:
            continue
        src = os.path.join(SAMPLES, f"{name}.flac")
        dst = os.path.join(OUT, f"{name}.json")
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
            done += 1
            continue
        try:
            note = name.split("v")[0]
            res = analyze_to_json(src, note, dst)
            print(f"{name}: f0={res['f0']:.1f} partials={res['n_partials']}",
                  flush=True)
            done += 1
        except Exception:
            failed.append(name)
            traceback.print_exc()
    print(f"analyzed {done}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
