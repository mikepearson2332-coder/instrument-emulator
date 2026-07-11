"""Analyze vibraphone reference samples -> reference/vibraphone/analysis/*.json

  python -m instruments.vibraphone.analyze [C4v2 ...]
"""

import os
import sys
import traceback

from .analysis import analyze_to_json
from .calibrate import LAYERS, NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "vibraphone", "samples")
OUT = os.path.join(ROOT, "reference", "vibraphone", "analysis")


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or None
    done, failed = 0, []
    for note in NOTES:
        # ff first: its mode list anchors the softer layers (pp overtones
        # sit under the detection gates but the bar's modes don't move)
        ff_modes = None
        for v in sorted(LAYERS, reverse=True):
            name = f"{note}v{v}"
            src = os.path.join(SAMPLES, f"{name}.flac")
            dst = os.path.join(OUT, f"{name}.json")
            if not os.path.exists(src):
                continue
            if only and name not in only:
                # still need ff modes for anchoring when analyzing others
                if v == 3 and os.path.exists(dst):
                    import json
                    with open(dst) as f:
                        ff_modes = [m["freq"] for m in json.load(f)["modes"]]
                continue
            if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
                if v == 3:
                    import json
                    with open(dst) as f:
                        ff_modes = [m["freq"] for m in json.load(f)["modes"]]
                done += 1
                continue
            try:
                fixed = ff_modes if v != 3 else None
                res = analyze_to_json(src, note, dst, fixed_modes=fixed)
                if v == 3:
                    ff_modes = [m["freq"] for m in res["modes"]]
                print(f"{name}: f0={res['f0']:.1f} modes={res['n_modes']}"
                      f"{' (anchored)' if fixed else ''}", flush=True)
                done += 1
            except Exception:
                failed.append(name)
                traceback.print_exc()
    print(f"analyzed {done}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
