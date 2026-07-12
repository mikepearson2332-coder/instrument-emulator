"""Rhodes (tine EP) synthesizer — generic modal renderer + table.

Partials are exact harmonics (engine n-series with B = 0; the pickup
nonlinearity's spectrum is baked into the per-layer amplitude tables).
Hammer/key thunk via per-band thump; damper fade on note-off.
Reference instrument: jRhodes3d 1977 Mark I Stage 73 (see SOURCES.md).
"""

from __future__ import annotations

import os

from lab.modal import ModalSynth

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "mk1.json")


class Rhodes(ModalSynth):
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int | None = None,
                 seed: int = 1234):
        super().__init__(table_path, sr=sr, seed=seed)
