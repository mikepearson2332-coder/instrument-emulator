"""Grand piano synthesizer — sample-free, offline.

Usage examples:
  python piano.py C4 --vel 100
  python piano.py "C4 E4 G4" --vel 90 --dur 5 --out chord.wav
  python piano.py 60 64 67 --vel 80 --play
Notes may be names (C4, F#3, Bb2) or MIDI numbers. A chord is multiple notes.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))

from instruments.piano.notes import name_to_midi
from instruments.piano.synth import Piano


def parse_note(tok: str) -> int:
    try:
        return int(tok)
    except ValueError:
        return name_to_midi(tok)


def main():
    ap = argparse.ArgumentParser(description="Model-based grand piano synth")
    ap.add_argument("notes", nargs="+", help="note names (C4, F#3) or MIDI numbers; multiple = chord")
    ap.add_argument("--vel", type=int, default=96, help="MIDI velocity 1-127")
    ap.add_argument("--dur", type=float, default=4.0, help="render length seconds")
    ap.add_argument("--release", type=float, default=None, help="key release time (s)")
    ap.add_argument("--out", default="note.wav", help="output WAV path")
    ap.add_argument("--play", action="store_true", help="play after rendering (Windows)")
    args = ap.parse_args()

    toks = []
    for a in args.notes:
        toks.extend(a.replace(",", " ").split())
    midis = [parse_note(t) for t in toks]

    piano = Piano()
    y = piano.synth_chord([(m, args.vel) for m in midis],
                          dur=args.dur, release_at=args.release)
    peak = np.max(np.abs(y)) + 1e-12
    y = (y / peak * 0.9).astype(np.float32)
    sf.write(args.out, y, piano.sr)
    print(f"wrote {args.out}  ({len(y)/piano.sr:.2f} s, {piano.sr} Hz)")

    if args.play:
        import winsound
        winsound.PlaySound(args.out, winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
