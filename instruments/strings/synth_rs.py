"""Rust-engine Strings with the same interface as synth.Strings.

Requires the native module built by scripts/build_core.ps1.
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

PARAMS = os.path.join(os.path.dirname(__file__), "params")


class Strings:
    def __init__(self, section: str = "vln", table_path: str | None = None,
                 sr: int | None = None, seed: int = 1234):
        if table_path is None:
            table_path = os.path.join(PARAMS, f"{section}.json")
        if sr is None:
            with open(table_path) as f:
                sr = json.load(f).get("config", {}).get("sr", 44100)
        self._inner = instrument_core.Piano(table_path, sr, seed)
        self.sr = sr

    def set_quality(self, max_partials=None, noise=True, max_symp_lines=None):
        self._inner.set_quality(max_partials, noise, max_symp_lines)

    def synth_note(self, midi, velocity, dur=6.0, release_at=None,
                   sustain_pedal=False):
        buf = self._inner.synth_note(midi, float(velocity), float(dur),
                                     release_at, sustain_pedal)
        return np.frombuffer(buf, dtype=np.float64).copy()

    def note_params(self, midi, velocity):
        return json.loads(self._inner.note_params_json(midi, float(velocity)))
