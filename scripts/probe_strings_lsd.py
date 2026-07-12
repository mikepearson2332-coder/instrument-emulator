"""Run strings compare() on one cell and dissect the lsd_sus value.

  python scripts/probe_strings_lsd.py cb_C#3v2
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.strings.benchmark import compare
from instruments.strings.evaluate import _vel_map, cases_for
from instruments.strings.synth import Strings
from instruments.strings.analysis import envelope_marks
from lab.audio import find_onset, load_mono
from lab.metrics import band_spectrogram


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "cb_C#3v2"
    sec = name.split("_")[0]
    c = {q["name"]: q for q in cases_for(sec)}[name]
    vel = _vel_map(sec).get((c["midi"], c["layer"]), 90)
    ref, sr = load_mono(c["ref"])
    dur = min(len(ref) / sr, 12.0)
    synth = Strings(section=sec)
    y = synth.synth_note(c["midi"], vel, dur=dur,
                         release_at=min(c["release_at"] or dur * 0.75,
                                        dur - 0.1))
    m = compare(y, synth.sr, c["ref"], c["note"])
    print(m)

    # dissect: reproduce the lsd computation
    s = np.asarray(y, float)
    s = s[find_onset(s, sr):]
    r = ref[find_onset(ref, sr):]
    n = int(min(len(s), len(r), 12.0 * sr))
    s, r = s[:n], r[:n]
    r0, r1, _ = envelope_marks(r, sr)
    span = r1 - r0
    w0, w1 = r0 + 0.15 * span, r0 + 0.85 * span
    tt, bs = band_spectrogram(s, sr)
    _, br = band_spectrogram(r, sr)
    m2 = min(bs.shape[1], br.shape[1])
    bs, br, tt = bs[:, :m2], br[:, :m2], tt[:m2]
    sel = (tt >= w0) & (tt < w1)
    a = bs[:, sel] - bs.max()
    b = br[:, sel] - br.max()
    print(f"window {w0:.2f}..{w1:.2f}  bs.max={bs.max():.1f} br.max={br.max():.1f}")
    mask = (a > -45) | (b > -45)
    d = np.abs(a - b)
    print(f"masked cells: {mask.sum()}  mean|diff|={d[mask].mean():.1f}")
    # worst bands
    edges = np.geomspace(25.0, 18000.0, 61)
    band_mean = np.where(mask, d, np.nan)
    bm = np.nanmean(band_mean, axis=1)
    order = np.argsort(np.nan_to_num(bm))[::-1][:8]
    for i in order:
        print(f"  band {edges[i]:7.0f}Hz mean|diff|={bm[i]:6.1f} "
              f"a_med={np.median(a[i]):7.1f} b_med={np.median(b[i]):7.1f}")


if __name__ == "__main__":
    main()
