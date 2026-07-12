"""Band-level comparison ref vs synth for jam block cases, first 60 ms
and 60-200 ms, per lab.modal BAND_EDGES band.

  python scripts/diag_jam_bands.py [E5 ...]
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from scipy.signal import stft

from instruments.jamblock.calibrate import LAYER_TO_VEL, NOTES
from instruments.jamblock.synth import Jamblock
from lab.audio import find_onset, load_mono
from lab.notes import name_to_midi

ROOT = os.path.join(os.path.dirname(__file__), "..")
SAMPLES = os.path.join(ROOT, "reference", "jamblock", "samples")
BAND_EDGES = np.geomspace(40.0, 8000.0, 11)


def band_levels(x, sr, t0, t1):
    nper = int(0.012 * sr)
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nper - int(0.002 * sr),
                   padded=False)
    A = np.abs(Z)
    sel_t = (t >= t0) & (t < t1)
    out = []
    for i in range(len(BAND_EDGES) - 1):
        sel_f = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1])
        if not sel_f.any() or not sel_t.any():
            out.append(float("nan"))
            continue
        v = A[np.ix_(sel_f, sel_t)].max()
        out.append(20 * math.log10(v + 1e-12))
    return np.array(out)


def main():
    notes = sys.argv[1:] or NOTES
    synth = Jamblock()
    for note in notes:
        ref, sr = load_mono(os.path.join(SAMPLES, f"{note}v1.flac"))
        ref = ref[find_onset(ref, sr):]
        y = synth.synth_note(name_to_midi(note), LAYER_TO_VEL[1],
                             dur=min(len(ref) / sr, 1.0))
        y = y[find_onset(y, sr):]
        gain = np.sqrt((ref[:sr // 5] ** 2).mean() / (y[:sr // 5] ** 2).mean())
        y = y * gain
        r_e = band_levels(ref, sr, 0.0, 0.06)
        s_e = band_levels(y, sr, 0.0, 0.06)
        r_m = band_levels(ref, sr, 0.06, 0.2)
        s_m = band_levels(y, sr, 0.06, 0.2)
        ref_pk = np.nanmax(r_e)
        print(f"\n=== {note}  (dB rel ref early peak; syn-ref)")
        print("band       early(ref/syn/diff)      mid(ref/syn/diff)")
        for i in range(len(BAND_EDGES) - 1):
            lo, hi = BAND_EDGES[i], BAND_EDGES[i + 1]
            print(f"{lo:5.0f}-{hi:5.0f} {r_e[i]-ref_pk:7.1f} {s_e[i]-ref_pk:7.1f} "
                  f"{s_e[i]-r_e[i]:+6.1f}   {r_m[i]-ref_pk:7.1f} "
                  f"{s_m[i]-ref_pk:7.1f} {s_m[i]-r_m[i]:+6.1f}")


if __name__ == "__main__":
    main()
