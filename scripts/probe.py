import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from instruments.piano.synth import Piano

p = Piano()
for midi, vel, label in [(21, 127, "A0v16"), (84, 48, "C6v6"), (60, 88, "C4v11")]:
    pr = p.note_params(midi, vel)
    parts = pr["partials"]
    print(label, "npartials", len(parts), "f0", round(pr["f0"], 2), "B", f"{pr['B']:.2e}")
    for q in parts[:6]:
        print("  n", q["n"], "a1", f"{q['a1']:.4g}", "t1", f"{q['t1']:.3g}",
              "a2", f"{q['a2']:.4g}", "t2", f"{q['t2']:.3g}")
    y = p.synth_note(midi, vel, dur=2.0)
    print("  peak", float(np.abs(y).max()), "rms", float(np.sqrt((y**2).mean())))
