"""StreamSynth smoke test for the rhodes + jamblock tables: note-on,
render buffers, note-off behavior, voice culling.

  python scripts/smoke_stream_new.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "dist"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import instrument_core

TABLES = {
    "rhodes": "instruments/rhodes/params/mk1.json",
    "jamblock": "instruments/jamblock/params/jam.json",
    "strings-vln": "instruments/strings/params/vln.json",
    "strings-cb": "instruments/strings/params/cb.json",
}


def main():
    for name, path in TABLES.items():
        s = instrument_core.StreamSynth(path, 44100)
        s.note_on(60, 100)
        s.note_on(64, 80)
        peak = 0.0
        n_buf = int(44100 * 1.5 / 512)
        for i in range(n_buf):
            buf = np.frombuffer(s.render(512), dtype=np.float64)
            peak = max(peak, np.abs(buf).max())
            if i == int(n_buf * 0.4):
                s.note_off(60)
                s.note_off(64)
        tail = np.frombuffer(s.render(512), dtype=np.float64)
        print(f"{name:9s} peak={peak:.3f} "
              f"tail_rms={np.sqrt((tail**2).mean()):.2e}")


if __name__ == "__main__":
    main()
