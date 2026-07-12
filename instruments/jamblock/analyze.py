"""Analyze jam block reference samples -> reference/jamblock/analysis/*.json

  python -m instruments.jamblock.analyze

Reuses the woodblock analysis verbatim (same struck-idiophone class:
mode finder + demod decay fits + short-event thump/bed profile).
"""

import os
import sys
import traceback

from instruments.woodblock.analysis import analyze_to_json

from .calibrate import NOTES

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SAMPLES = os.path.join(ROOT, "reference", "jamblock", "samples")
OUT = os.path.join(ROOT, "reference", "jamblock", "analysis")


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] or None
    names = [f"{n}v1" for n in NOTES] + [f"{n}v1_alt1" for n in NOTES]
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
            # tighter separation than the woodblock: jam block mode
            # clusters sit 5-8% apart but each mode is only ~30 Hz wide
            # (tau 9-18 ms) — they are distinct resonances, and folding
            # them into "thump" made the click 6+ dB too bright
            res = analyze_to_json(src, name.split("v")[0], dst,
                                  unmask_rel=0.5,
                                  min_sep_rel=0.055, min_sep_hz=40.0,
                                  max_modes=12)
            print(f"{name}: f0={res['f0']:.1f} modes={res['n_modes']}",
                  flush=True)
            done += 1
        except Exception:
            failed.append(name)
            traceback.print_exc()
    print(f"analyzed {done}, failed {len(failed)}: {failed}")


if __name__ == "__main__":
    main()
