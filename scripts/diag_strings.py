"""Diagnose broken strings eval cells: render stats vs reference.

  python scripts/diag_strings.py cb_F#1v2 vc_D3v2 vln_E5v1
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.evaluate import _vel_map, cases_for
from instruments.strings.synth import Strings
from instruments.strings.analysis import envelope_marks, rms_env
from lab.audio import load_mono

ROOT = os.path.join(os.path.dirname(__file__), "..")


def diag(name):
    sec = name.split("_")[0]
    cases = {c["name"]: c for c in cases_for(sec)}
    c = cases[name]
    vm = _vel_map(sec)
    vel = vm.get((c["midi"], c["layer"]), 90)
    ref, sr = load_mono(c["ref"])
    dur = min(len(ref) / sr, 12.0)
    rel = c["release_at"] or dur * 0.75
    synth = Strings(section=sec)
    p = synth.note_params(c["midi"], vel)
    y = synth.synth_note(c["midi"], vel, dur=dur,
                         release_at=min(rel, dur - 0.1))
    er, es = rms_env(ref, sr), rms_env(y, sr)
    r0, r1, rise_r = envelope_marks(ref, sr)
    s0, s1, rise_s = envelope_marks(y, sr)
    print(f"\n=== {name} midi={c['midi']} vel={vel} dur={dur:.1f} "
          f"release_at={rel:.2f}")
    print(f"  ref: peak_rms={er.max():.4f} rise={rise_r:.2f} "
          f"marks=({r0:.2f},{r1:.2f})")
    print(f"  syn: peak_rms={es.max():.4f} rise={rise_s:.2f} "
          f"marks=({s0:.2f},{s1:.2f})")
    print(f"  params: f0={p['f0']:.1f} rise_s={p['rise_s']:.2f} "
          f"und={p['und_db']:.2f}@{p['und_hz']:.2f} vib={p['vib_hz']:.2f} "
          f"rel={p['rel_s']:.2f} harm={len(p['harm'])}")
    hs = sorted(p["harm"], key=lambda h: -h["a"])[:5]
    print("  top harm:", [(h["n"], round(h["a"], 5)) for h in hs])
    print("  noise_db:", [round(v) for v in p["noise_db"]])


if __name__ == "__main__":
    for n in sys.argv[1:] or ["cb_F#1v2", "vc_D3v2", "vln_E5v1"]:
        diag(n)
