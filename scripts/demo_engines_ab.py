"""A/B listening demo: Python engine vs Rust engine, same notes back-to-back.
Writes output/demo/engine_ab.wav — for each test note: python render, then
rust render, then 0.4 s silence."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import soundfile as sf

from instruments.piano.synth import Piano as PianoPy
from instruments.piano.synth_rs import Piano as PianoRs

OUT = os.path.join(os.path.dirname(__file__), "..", "output", "demo")
os.makedirs(OUT, exist_ok=True)

py, rs = PianoPy(), PianoRs()
sr = py.sr
gap = np.zeros(int(0.4 * sr))
parts = []
for midi, vel in [(36, 88), (48, 88), (60, 88), (60, 32), (72, 112), (84, 88), (96, 88)]:
    for eng in (py, rs):
        y = eng.synth_note(midi, vel, dur=2.5, release_at=2.0)
        peak = np.max(np.abs(y)) + 1e-12
        parts.extend([y / peak * 0.7, gap])
full = np.concatenate(parts).astype(np.float32)
sf.write(os.path.join(OUT, "engine_ab.wav"), full, sr)
print(f"wrote output/demo/engine_ab.wav ({len(full)/sr:.1f} s; "
      f"pairs are python-then-rust)")
