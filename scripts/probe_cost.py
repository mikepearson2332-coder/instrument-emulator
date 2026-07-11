"""Attribute render cost: partials vs noise vs symp, via quality toggles."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from instruments.piano.synth_rs import Piano

NOTES = [(21, 88), (36, 48), (48, 88), (60, 88), (72, 127), (84, 88), (105, 88)]


def t(p, label):
    p.synth_note(60, 88, dur=0.5)
    t0 = time.perf_counter()
    for m, v in NOTES:
        p.synth_note(m, v, dur=3.0)
    dt = time.perf_counter() - t0
    print(f"{label:28s}: {dt*1000/len(NOTES):6.1f} ms/note")
    return dt


p = Piano()
full = t(p, "full")
p.set_quality(noise=False)
t(p, "no noise")
p.set_quality(max_symp_lines=0)
t(p, "no symp")
p.set_quality(noise=False, max_symp_lines=0)
t(p, "partials only")
p.set_quality(max_partials=24)
t(p, "24 partials + noise + symp")
p.set_quality(max_partials=24, noise=False, max_symp_lines=0)
t(p, "24 partials only")
