"""Component attribution for the strings render: harmonics-only vs
noise-only band content, plus round-trip check of the bed calibration.

  python scripts/probe_strings_noise.py vla_C3v2
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.evaluate import _vel_map, cases_for
from instruments.strings.synth import Strings
from lab.sustained import BAND_EDGES, N_BANDS
from lab.audio import load_mono
from lab.metrics import band_spectrogram


def band_mean(x, sr, t0=2.0, t1=8.0):
    tt, b = band_spectrogram(x, sr)
    sel = (tt >= t0) & (tt < t1)
    return b[:, sel].mean(axis=1)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "vla_C3v2"
    sec = name.split("_")[0]
    c = {q["name"]: q for q in cases_for(sec)}[name]
    vel = _vel_map(sec).get((c["midi"], c["layer"]), 90)
    synth = Strings(section=sec)
    p = synth.note_params(c["midi"], vel)
    print("table noise_db:", [None if v <= -119 else round(v)
                              for v in p["noise_db"]])
    print("cal_bed:       ", [round(v) for v in synth._cal_bed])

    # round-trip: noise-only render measured through the same metric
    ref, sr = load_mono(c["ref"])
    dur = 10.0

    # harmonics only
    import copy
    p2 = synth.note_params(c["midi"], vel)
    saved = [dict(h) for h in p2["harm"]]

    def render(mute_noise=False, mute_harm=False):
        s = Strings(section=sec)  # fresh rng
        orig = s.note_params

        def patched(midi, velocity):
            q = orig(midi, velocity)
            if mute_noise:
                q["noise_db"] = [-999.0] * len(q["noise_db"])
            if mute_harm:
                for h in q["harm"]:
                    h["a"] = 0.0
            return q
        s.note_params = patched
        return s.synth_note(c["midi"], vel, dur=dur, release_at=9.0), s

    y_h, _ = render(mute_noise=True)
    y_n, s_n = render(mute_harm=True)
    bh = band_mean(y_h, synth.sr)
    bn = band_mean(y_n, synth.sr)
    br = band_mean(ref[: int(dur * synth.sr)], synth.sr)
    bmax = br.max()
    edges = np.geomspace(25.0, 18000.0, 61)
    print("band(Hz)   ref    harm   noise   (dB rel ref max)")
    for i in range(0, 60, 3):
        print(f"{edges[i]:7.0f} {br[i]-bmax:7.1f} {bh[i]-bmax:7.1f} "
              f"{bn[i]-bmax:7.1f}")

    # bed round-trip: measure noise-only render with the analysis metric
    from instruments.strings.analysis import noise_bed
    got = noise_bed(y_n, synth.sr, p["f0"], [], 2.0, 8.0)
    print("\nbed round-trip (band: table -> re-measured):")
    for i in range(N_BANDS):
        tv = p["noise_db"][i]
        gv = got[i]
        print(f"  {BAND_EDGES[i]:6.0f}-{BAND_EDGES[i+1]:6.0f}  "
              f"{'None' if tv <= -119 else round(tv, 1)} -> "
              f"{'None' if gv is None else round(gv, 1)}")


if __name__ == "__main__":
    main()
