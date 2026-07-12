"""Reproduce the eval's sequential renders for one section and catch the
cell whose render goes bad (NaN/blowup/silence).

  python scripts/probe_strings_seq.py cb
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.benchmark import compare, composite_score
from instruments.strings.evaluate import _vel_map, cases_for
from instruments.strings.synth import Strings
from lab.audio import load_mono


def main():
    sec = sys.argv[1] if len(sys.argv) > 1 else "cb"
    synth = Strings(section=sec, seed=1234)
    vm = _vel_map(sec)
    for c in cases_for(sec):
        ref, sr = load_mono(c["ref"])
        dur = min(len(ref) / sr, 12.0)
        rel = c["release_at"] or dur * 0.75
        vel = vm.get((c["midi"], c["layer"]), 90)
        y = synth.synth_note(c["midi"], vel, dur=dur,
                             release_at=min(rel, dur - 0.1))
        stats = (f"peak={np.abs(y).max():9.3e} nan={np.isnan(y).any()} "
                 f"rms={np.sqrt((y**2).mean()):9.3e}")
        m = compare(y, synth.sr, c["ref"], c["note"])
        s = composite_score(m)
        flag = "  <<<" if (s > 2.0 or np.isnan(y).any()
                          or np.abs(y).max() > 10) else ""
        print(f"{c['name']:12s} score={s:6.3f} lsd={m['lsd_sus']} {stats}{flag}",
              flush=True)


if __name__ == "__main__":
    main()
