"""Analyze string-section reference samples -> reference/strings/analysis/

  python -m instruments.strings.analyze [vln_G3v1 ...]
"""

import os
import sys
import traceback

from .analysis import analyze_to_json

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "strings", "samples")
OUT = os.path.join(ROOT, "reference", "strings", "analysis")


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or None
    done, failed = 0, []
    for fn in sorted(os.listdir(SAMPLES)):
        if not fn.endswith(".flac"):
            continue
        name = fn[:-5]
        if only and name not in only:
            continue
        src = os.path.join(SAMPLES, fn)
        dst = os.path.join(OUT, f"{name}.json")
        if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
            done += 1
            continue
        try:
            note = name.split("_")[-1].split("v")[0]
            res = analyze_to_json(src, note, dst)
            print(f"{name}: f0={res['f0']:.1f} harm={len(res['harm'])} "
                  f"rise={res['rise_s']:.2f}s vib={res['vib_hz']:.1f}Hz",
                  flush=True)
            done += 1
        except Exception:
            failed.append(name)
            traceback.print_exc()
    print(f"analyzed {done}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
