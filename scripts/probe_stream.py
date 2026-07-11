"""Functional check of the streaming API."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from instruments.piano.synth_rs import StreamSynth

s = StreamSynth()
nbuf = 240  # 5 ms
s.note_on(60, 90)
s.note_on(64, 90)
s.note_on(67, 90)
a = np.concatenate([s.render(nbuf) for _ in range(200)])  # 1 s
print(f"held: voices={s.active_voices()} rms={np.sqrt(np.mean(a**2)):.4f}")
s.note_off(60); s.note_off(64); s.note_off(67)
b = np.concatenate([s.render(nbuf) for _ in range(200)])  # 1 s after release
print(f"released: voices={s.active_voices()} rms={np.sqrt(np.mean(b**2)):.4f}")
for _ in range(200 * 28):  # 28 more seconds
    s.render(nbuf)
print(f"after ring-out: voices={s.active_voices()}")
assert s.active_voices() == 0, "voices not culled"
s.set_pedal(True)
s.note_on(48, 90); s.note_off(48)
c = np.concatenate([s.render(nbuf) for _ in range(100)])
print(f"pedal holds released key: voices={s.active_voices()} rms={np.sqrt(np.mean(c**2)):.4f}")
s.set_pedal(False)
d = np.concatenate([s.render(nbuf) for _ in range(400)])
print(f"pedal up -> damped: rms={np.sqrt(np.mean(d**2)):.4f}")
print("OK")
