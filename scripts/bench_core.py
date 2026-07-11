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


def bench_streaming(quality_kw, label, polyphony=16):
    """Sustained streaming: `polyphony` held notes, 5 ms buffers."""
    from instruments.piano.synth_rs import StreamSynth
    s = StreamSynth()
    if quality_kw:
        s.set_quality(**quality_kw)
    midis = [21 + (i * 5) % 88 for i in range(polyphony)]
    for m in midis:
        s.note_on(m, 88)
    nbuf = int(0.005 * s.sr)
    s.render(nbuf)  # warmup
    n_iters = 400  # 2 s of audio
    t0 = time.perf_counter()
    for _ in range(n_iters):
        s.render(nbuf)
    dt = time.perf_counter() - t0
    audio_s = n_iters * nbuf / s.sr
    print(f"stream {label:14s}: {polyphony} voices, {audio_s / dt:5.1f}x realtime "
          f"({dt / n_iters * 1e3:5.2f} ms per 5 ms buffer, "
          f"{s.active_voices()} voices alive)")


def main():
    t0 = time.perf_counter()
    from instruments.piano.synth_rs import Piano as PianoRs
    p = PianoRs()
    init_rs = time.perf_counter() - t0
    print(f"rust engine init (band-noise calibration): {init_rs * 1000:.0f} ms")

    from instruments.piano.synth import Piano as PianoPy
    bench(PianoPy, "python")
    bench(PianoRs, "rust")

    print("\nhost benchmark:", p.benchmark())
    for poly, frac in [(32, 0.5), (64, 0.5), (128, 0.5)]:
        print(f"  {poly} voices @ {frac:.0%} core -> max_partials "
              f"{p.pick_max_partials(poly, frac)}")

    print()
    bench_streaming(None, "full", 16)
    bench_streaming(dict(max_partials=32), "p32", 16)
    bench_streaming(dict(max_partials=24, max_symp_lines=12), "p24_s12", 16)
    bench_streaming(dict(max_partials=24, max_symp_lines=12), "p24_s12", 64)


if __name__ == "__main__":
    main()
