"""String-section synthesizer — sustained-engine reference + tables.

One synth per section table (vln/vla/vc/cb). Reference: VSCO-2-CE
section sustains (see SOURCES.md).
"""

from __future__ import annotations

import os

from lab.sustained import SustainedSynth

PARAMS = os.path.join(os.path.dirname(__file__), "params")


class Strings(SustainedSynth):
    def __init__(self, section: str = "vln", table_path: str | None = None,
                 sr: int | None = None, seed: int = 1234):
        if table_path is None:
            table_path = os.path.join(PARAMS, f"{section}.json")
        super().__init__(table_path, sr=sr, seed=seed)
