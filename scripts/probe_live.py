"""Live-audio smoke test: opens the default output device, plays a short
chord + scale, prints meters. Audible!"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "dist"))
import instrument_core

TABLE = os.path.join(os.path.dirname(__file__), "..", "instruments", "piano",
                     "params", "grand.json")

live = instrument_core.Live(TABLE)
print(f"device: {live.device_name}  sr: {live.sr}")
print(f"midi ports: {instrument_core.Live.midi_ports()}")

for m in (60, 64, 67):
    live.note_on(m, 85)
time.sleep(1.2)
print(f"meters (chord held): voices={live.meters()[0]} load={live.meters()[1]:.1%} "
      f"peak={live.meters()[2]:.2f}")
for m in (60, 64, 67):
    live.note_off(m)
time.sleep(0.5)

live.set_pedal(True)
for i, m in enumerate([48, 55, 60, 64, 67, 72]):
    live.note_on(m, 70 + i * 8)
    time.sleep(0.22)
    live.note_off(m)
live.set_pedal(False)
time.sleep(1.0)
v, load, peak = live.meters()
print(f"meters (after pedal arpeggio): voices={v} load={load:.1%} peak={peak:.2f}")
live.all_notes_off()
time.sleep(0.6)
print("OK")
