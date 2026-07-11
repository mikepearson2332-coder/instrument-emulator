"""Koto (long-zither) synthesizer — generic modal renderer + table.

Partials follow the engine's native inharmonic string series (per-key
f0 + B); plectrum click via per-band thump; palm-damp release on
note-off. Reference instrument: VCSL đàn tranh (see SOURCES.md).
"""

from __future__ import annotations

import os

from lab.modal import ModalSynth

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "tranh.json")


class Koto(ModalSynth):
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int | None = None,
                 seed: int = 1234):
        super().__init__(table_path, sr=sr, seed=seed)
