"""Render listening demos into output/demo/:
 - scale.wav       chromatic-ish sweep across the range at mf
 - velocities.wav  C4 at velocities 16..127
 - chords.wav      a short chord progression
 - synth_vs_ref_*.wav  paired A/B (synth first, then reference sample)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import soundfile as sf

from instruments.piano.notes import name_to_midi
from instruments.piano.synth import Piano
from instruments.piano.analysis import load_mono, find_onset

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "output", "demo")
os.makedirs(OUT, exist_ok=True)

piano = Piano()
sr = piano.sr


def norm(y):
    return (y / (np.max(np.abs(y)) + 1e-12) * 0.85).astype(np.float32)


def place(canvas, y, at):
    i0 = int(at * sr)
    n = min(len(y), len(canvas) - i0)
    canvas[i0:i0 + n] += y[:n]


# --- scale across the range
notes = [21, 28, 36, 43, 48, 55, 60, 64, 67, 72, 79, 84, 91, 96, 103, 108]
canvas = np.zeros(int((len(notes) * 0.6 + 4) * sr))
for i, m in enumerate(notes):
    place(canvas, piano.synth_note(m, 96, dur=4.0, release_at=1.2), i * 0.6)
sf.write(os.path.join(OUT, "scale.wav"), norm(canvas), sr)

# --- velocity sweep on C4
canvas = np.zeros(int(8 * 1.0 * sr) + 4 * sr)
for i, v in enumerate([16, 32, 48, 64, 80, 96, 112, 127]):
    place(canvas, piano.synth_note(60, v, dur=3.5, release_at=0.9), i * 1.0)
sf.write(os.path.join(OUT, "velocities.wav"), norm(canvas), sr)

# --- chord progression (C - Am - F - G7 - C)
prog = [
    (["C3", "E3", "G3", "C4", "E4"], 96),
    (["A2", "E3", "A3", "C4", "E4"], 88),
    (["F2", "C3", "F3", "A3", "C4"], 92),
    (["G2", "D3", "G3", "B3", "F4"], 96),
    (["C2", "G2", "E3", "G3", "C4"], 104),
]
canvas = np.zeros(int((len(prog) * 1.6 + 6) * sr))
for i, (chord, vel) in enumerate(prog):
    y = piano.synth_chord([(name_to_midi(n), vel) for n in chord],
                          dur=5.0, release_at=1.5 if i < len(prog) - 1 else None)
    place(canvas, y, i * 1.6)
sf.write(os.path.join(OUT, "chords.wav"), norm(canvas), sr)

# --- A/B pairs: synth then reference
for name, midi, vel in [("C4v11", 60, 88), ("A0v16", 21, 127),
                        ("C6v6", 84, 48), ("F#2v11", 42, 88)]:
    ref, rsr = load_mono(os.path.join(ROOT, "reference", "piano", "samples", f"{name}.flac"))
    ref = ref[find_onset(ref, rsr):int(find_onset(ref, rsr) + 5 * rsr)]
    y = piano.synth_note(midi, vel, dur=5.0)
    y = y * (np.abs(ref).max() / (np.abs(y).max() + 1e-12))
    gap = np.zeros(int(0.7 * sr))
    both = np.concatenate([y, gap, ref])
    sf.write(os.path.join(OUT, f"ab_{name}.wav"), norm(both), sr)

print("demos written to output/demo/:", sorted(os.listdir(OUT)))
