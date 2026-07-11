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
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int = 48000, seed: int = 1234,
                 max_partials: int | None = None, noise: bool = True,
                 max_symp_lines: int | None = None):
        self._inner = instrument_core.Piano(table_path, sr, seed)
        if max_partials is not None or not noise or max_symp_lines is not None:
            self._inner.set_quality(max_partials, noise, max_symp_lines)
        self.sr = sr

    def set_quality(self, max_partials=None, noise=True, max_symp_lines=None):
        self._inner.set_quality(max_partials, noise, max_symp_lines)

    def benchmark(self):
        """Host throughput: {sec_per_partial_sample, sec_per_voice_sample,
        partials_per_sec}."""
        return json.loads(self._inner.benchmark_json())

    def pick_max_partials(self, polyphony: int, cpu_fraction: float) -> int:
        return self._inner.pick_max_partials(polyphony, cpu_fraction)

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


class StreamSynth:
    """Real-time streaming synth: note events in, buffers out."""

    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int = 48000, seed: int = 1234):
        self._inner = instrument_core.StreamSynth(table_path, sr, seed)
        self.sr = sr

    def set_quality(self, max_partials=None, noise=True, max_symp_lines=None):
        self._inner.set_quality(max_partials, noise, max_symp_lines)

    def note_on(self, midi: int, velocity: float):
        self._inner.note_on(midi, float(velocity))

    def note_off(self, midi: int):
        self._inner.note_off(midi)

    def set_pedal(self, down: bool):
        self._inner.set_pedal(down)

    def all_notes_off(self):
        self._inner.all_notes_off()

    def active_voices(self) -> int:
        return self._inner.active_voices()

    def render(self, n_frames: int):
        return np.frombuffer(self._inner.render(n_frames), dtype=np.float64)
