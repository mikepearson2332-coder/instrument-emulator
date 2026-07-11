"""Diagnostic plots: synth vs reference spectrogram + envelope + spectrum.

Usage: python scripts/diagnose.py C4v11 [A0v16 ...]
Writes output/diag/<name>.png
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from instruments.piano.notes import name_to_midi
from instruments.piano.calibrate import LAYER_TO_VEL
from instruments.piano.synth import Piano
from instruments.piano.analysis import load_mono, find_onset
from instruments.piano.benchmark import _band_spectrogram

ROOT = os.path.join(os.path.dirname(__file__), "..")


def rms_env_db(x, sr, hop=0.01):
    h = int(hop * sr)
    m = len(x) // h
    fr = x[: m * h].reshape(m, h)
    r = np.sqrt((fr ** 2).mean(axis=1) + 1e-20)
    return np.arange(m) * hop, 20 * np.log10(r / r.max() + 1e-12)


def main():
    piano = Piano()
    outdir = os.path.join(ROOT, "output", "diag")
    os.makedirs(outdir, exist_ok=True)
    for name in sys.argv[1:]:
        note = name.split("v")[0]
        layer = int(name.split("v")[1])
        ref_path = os.path.join(ROOT, "reference", "piano", "samples", f"{name}.flac")
        ref, sr = load_mono(ref_path)
        ref = ref[find_onset(ref, sr):]
        dur = min(len(ref) / sr, 8.0)
        y = piano.synth_note(name_to_midi(note), LAYER_TO_VEL[layer], dur=dur)
        y = y[find_onset(y, piano.sr):]
        n = int(min(len(y), len(ref)))
        y, ref = y[:n], ref[:n]
        y = y * (np.abs(ref).max() / (np.abs(y).max() + 1e-20))

        fig, axes = plt.subplots(2, 2, figsize=(15, 9))
        for ax, sig, title in [(axes[0, 0], ref, "reference"), (axes[0, 1], y, "synth")]:
            t, b = _band_spectrogram(sig, sr)
            im = ax.imshow(b - b.max(), aspect="auto", origin="lower",
                           extent=[t[0], t[-1], 0, b.shape[0]],
                           vmin=-80, vmax=0, cmap="magma")
            ax.set_title(f"{name} {title}")
            ax.set_xlabel("s")
            ax.set_ylabel("log-band")
        plt.colorbar(im, ax=axes[0, :], shrink=0.8)

        tr, er = rms_env_db(ref, sr)
        ts, es = rms_env_db(y, sr)
        axes[1, 0].plot(tr, er, label="ref")
        axes[1, 0].plot(ts, es, label="synth", alpha=0.8)
        axes[1, 0].set_ylim(-80, 3)
        axes[1, 0].set_title("RMS envelope (dB)")
        axes[1, 0].legend()

        for sig, lab in [(ref, "ref"), (y, "synth")]:
            seg = sig[: int(0.5 * sr)]
            w = np.hanning(len(seg))
            mag = 20 * np.log10(np.abs(np.fft.rfft(seg * w)) + 1e-9)
            fax = np.fft.rfftfreq(len(seg), 1 / sr)
            sel = fax < 12000
            axes[1, 1].plot(fax[sel], mag[sel] - mag.max(), label=lab, alpha=0.75, lw=0.7)
        axes[1, 1].set_ylim(-90, 3)
        axes[1, 1].set_title("spectrum, first 500 ms (dB)")
        axes[1, 1].legend()

        fig.savefig(os.path.join(outdir, f"{name}.png"), dpi=90)
        plt.close(fig)
        print(f"wrote output/diag/{name}.png")


if __name__ == "__main__":
    main()
