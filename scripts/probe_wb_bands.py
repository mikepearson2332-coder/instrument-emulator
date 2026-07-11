"""Probe: woodblock synth vs reference, per-band level decomposition.

Renders one layer, prints per-band dB (median STFT magnitude) at three time
slices for reference vs synth, plus synth with components muted
(modes-only / noise-only) to attribute discrepancies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
from scipy.signal import stft

from lab.audio import find_onset, load_mono
from instruments.woodblock.synth import Woodblock
from instruments.woodblock.calibrate import LAYER_TO_VEL

ROOT = os.path.join(os.path.dirname(__file__), "..")
BAND_EDGES = np.geomspace(40.0, 8000.0, 11)


def band_slices(x, sr):
    nper = int(0.046 * sr)
    nover = nper - int(0.010 * sr)
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
    A = np.abs(Z)
    out = []
    for i in range(len(BAND_EDGES) - 1):
        sel = (f >= BAND_EDGES[i]) & (f < BAND_EDGES[i + 1])
        med = np.median(A[sel], axis=0)
        row = []
        for lo, hi in [(0.0, 0.06), (0.06, 0.15), (0.15, 0.35)]:
            ts = (t >= lo) & (t < hi)
            v = med[ts].max() if ts.any() else 0.0
            row.append(20 * np.log10(v + 1e-12))
        out.append(row)
    return np.array(out)


def main():
    layer = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    name = f"F6v{layer}"
    ref, sr = load_mono(os.path.join(ROOT, "reference", "woodblock",
                                     "samples", f"{name}.flac"))
    ref = ref[find_onset(ref, sr):]
    dur = len(ref) / sr

    wb = Woodblock()
    y = wb.synth_note(89, LAYER_TO_VEL[layer], dur=dur)

    # component isolation: mute noise / mute modes
    wb2 = Woodblock()
    p = wb2.note_params(89, LAYER_TO_VEL[layer])
    import copy
    t_only_modes = copy.deepcopy(wb2.table)
    for k in t_only_modes["keys"]:
        for L in k["layers"]:
            L["thump_db"] = None
            L["bed_db"] = None
    import json
    import tempfile
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(t_only_modes, tmp)
    tmp.close()
    wb_modes = Woodblock(table_path=tmp.name)
    y_modes = wb_modes.synth_note(89, LAYER_TO_VEL[layer], dur=dur)

    t_only_noise = copy.deepcopy(wb2.table)
    for k in t_only_noise["keys"]:
        for L in k["layers"]:
            for prt in L["partials"]:
                prt["a1"] = 0.0
                prt["a2"] = 0.0
    tmp2 = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(t_only_noise, tmp2)
    tmp2.close()
    wb_noise = Woodblock(table_path=tmp2.name)
    y_noise = wb_noise.synth_note(89, LAYER_TO_VEL[layer], dur=dur)

    # match eval gain convention: peak 2 ms RMS
    def rms_env(x, hop=0.002):
        h = int(hop * sr)
        m = len(x) // h
        return np.sqrt((x[:m*h].reshape(m, h) ** 2).mean(axis=1) + 1e-20)

    gain = rms_env(ref).max() / (rms_env(y).max() + 1e-20)
    print(f"{name}: gain applied to synth = {gain:.3f} "
          f"(ref peak {np.abs(ref).max():.3f}, synth peak {np.abs(y).max():.3f})")

    br = band_slices(ref, sr)
    bs = band_slices(y * gain, sr)
    bm = band_slices(y_modes * gain, sr)
    bn = band_slices(y_noise * gain, sr)
    print(f"{'band':>12s} | {'ref 0-60ms':>10s} {'syn':>7s} {'modes':>7s} {'noise':>7s} | "
          f"{'ref 60-150':>10s} {'syn':>7s} | {'ref 150-350':>11s} {'syn':>7s}")
    for i in range(len(BAND_EDGES) - 1):
        print(f"{BAND_EDGES[i]:6.0f}-{BAND_EDGES[i+1]:5.0f} | "
              f"{br[i,0]:10.1f} {bs[i,0]:7.1f} {bm[i,0]:7.1f} {bn[i,0]:7.1f} | "
              f"{br[i,1]:10.1f} {bs[i,1]:7.1f} | "
              f"{br[i,2]:11.1f} {bs[i,2]:7.1f}")
    os.unlink(tmp.name)
    os.unlink(tmp2.name)


if __name__ == "__main__":
    main()
