"""Throughput benchmark: how much faster than real time does each engine
render? Baseline for the phase-3 quality/performance system.

Renders a spread of keys/velocities at 3 s each and reports the real-time
factor (render seconds of audio per wall-clock second)."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NOTES = [(21, 88), (36, 48), (48, 88), (60, 88), (72, 127), (84, 88), (105, 88)]
DUR = 3.0


def bench(piano_cls, label):
    piano = piano_cls()
    # warmup (also amortizes band-noise calibration in __init__ timing note below)
    piano.synth_note(60, 88, dur=0.5)
    t0 = time.perf_counter()
    for midi, vel in NOTES:
        piano.synth_note(midi, vel, dur=DUR)
    dt = time.perf_counter() - t0
    audio_s = DUR * len(NOTES)
    print(f"{label:8s}: {audio_s:.0f} s audio in {dt:6.2f} s wall -> {audio_s / dt:6.1f}x realtime "
          f"({dt / len(NOTES) * 1000:6.0f} ms/note)")
    return audio_s / dt


def main():
    t0 = time.perf_counter()
    from instruments.piano.synth_rs import Piano as PianoRs
    PianoRs()
    init_rs = time.perf_counter() - t0
    print(f"rust engine init (band-noise calibration): {init_rs * 1000:.0f} ms")

    from instruments.piano.synth import Piano as PianoPy
    bench(PianoPy, "python")
    bench(PianoRs, "rust")


if __name__ == "__main__":
    main()
