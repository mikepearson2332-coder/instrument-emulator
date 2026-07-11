"""Note-name / MIDI / frequency utilities (instrument-agnostic)."""

from __future__ import annotations

NOTE_TO_SEMITONE = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10,
    "B": 11,
}
SEMITONE_TO_NAME = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

A4_MIDI = 69
A4_FREQ = 440.0


def name_to_midi(name: str) -> int:
    """'C4' -> 60, 'D#1' -> 27, 'A0' -> 21."""
    i = 1
    if len(name) > 1 and name[1] in "#b":
        i = 2
    pitch = NOTE_TO_SEMITONE[name[:i]]
    octave = int(name[i:])
    return (octave + 1) * 12 + pitch


def midi_to_name(midi: int) -> str:
    octave = midi // 12 - 1
    return f"{SEMITONE_TO_NAME[midi % 12]}{octave}"


def midi_to_freq(midi: float) -> float:
    return A4_FREQ * 2.0 ** ((midi - A4_MIDI) / 12.0)


def freq_to_midi(freq: float) -> float:
    import math
    return A4_MIDI + 12.0 * math.log2(freq / A4_FREQ)
