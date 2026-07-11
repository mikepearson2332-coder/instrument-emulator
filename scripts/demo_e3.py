"""Interpolation test: real D#3 (v11) -> synth E3 (vel 70) -> real F#3 (v11)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
import soundfile as sf
from pianomodel.synth import Piano
from pianomodel.analysis import load_mono, find_onset

ROOT = os.path.join(os.path.dirname(__file__), "..")
piano = Piano()
sr = piano.sr

parts = []
for kind, arg in [("ref", "D#3v11"), ("synth", (52, 70)), ("ref", "F#3v11")]:
    if kind == "ref":
        x, rsr = load_mono(os.path.join(ROOT, "reference", "samples", f"{arg}.flac"))
        o = find_onset(x, rsr)
        y = x[o: o + int(4 * rsr)]
    else:
        y = piano.synth_note(arg[0], arg[1], dur=4.0)
    y = y / (np.abs(y).max() + 1e-12) * 0.8
    parts.append(y)
    parts.append(np.zeros(int(0.6 * sr)))

out = os.path.join(ROOT, "output", "demo", "interp_E3v70.wav")
sf.write(out, np.concatenate(parts).astype(np.float32), sr)
print("wrote", out)
