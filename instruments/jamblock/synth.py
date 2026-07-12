"""Jam block synthesizer — generic modal renderer + table.

4 plastic blocks anchored at measured dominant-mode pitches, `fr` mode
ratios, per-band click decay, no dampers. Reference: CC0 Freesound
granite-block hits (see SOURCES.md).
"""

from __future__ import annotations

import os

from lab.modal import ModalSynth

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "jam.json")


class Jamblock(ModalSynth):
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int | None = None,
                 seed: int = 1234):
        super().__init__(table_path, sr=sr, seed=seed)
