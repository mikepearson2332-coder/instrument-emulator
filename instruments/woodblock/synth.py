"""Woodblock synthesizer — generic modal renderer + the calibrated table.

The sound model lives in `lab.modal.ModalSynth` (modes with explicit
frequency ratios, per-band thump + short bed, no dampers); this module just
binds the table and native sample rate.
"""

from __future__ import annotations

import os

from lab.modal import ModalSynth

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "block.json")


class Woodblock(ModalSynth):
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int | None = None,
                 seed: int = 1234):
        super().__init__(table_path, sr=sr, seed=seed)
