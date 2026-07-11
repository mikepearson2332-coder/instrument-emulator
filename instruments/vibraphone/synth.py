"""Vibraphone synthesizer — generic modal renderer + the calibrated table.

Sound model in `lab.modal.ModalSynth`: modes with explicit frequency
ratios, per-band mallet thump, damper release (`release_fade_s` measured
from the MIS dampen takes). Motor/tremolo is not modeled (reference was
recorded motor off).
"""

from __future__ import annotations

import os

from lab.modal import ModalSynth

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "vibes.json")


class Vibraphone(ModalSynth):
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int | None = None,
                 seed: int = 1234):
        super().__init__(table_path, sr=sr, seed=seed)
