"""Rust-engine Piano with the same interface as synth.Piano.

Requires the native module built by scripts/build_core.ps1
(core/dist/instrument_core.pyd).
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "core", "dist"))
if _DIST not in sys.path:
    sys.path.insert(0, _DIST)

import instrument_core  # noqa: E402

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "grand.json")


class Piano:
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int = 48000, seed: int = 1234):
        self._inner = instrument_core.Piano(table_path, sr, seed)
        self.sr = sr

    def synth_note(self, midi, velocity, dur=4.0, release_at=None, sustain_pedal=False):
        buf = self._inner.synth_note(midi, float(velocity), float(dur),
                                     release_at, sustain_pedal)
        return np.frombuffer(buf, dtype=np.float64).copy()

    def synth_chord(self, notes, dur=4.0, **kw):
        out = None
        for midi, vel in notes:
            y = self.synth_note(midi, vel, dur=dur, **kw)
            out = y if out is None else out + y
        return out

    def note_params(self, midi, velocity):
        return json.loads(self._inner.note_params_json(midi, float(velocity)))
