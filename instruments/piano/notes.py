"""Piano note utilities: generic helpers re-exported from the lab, plus the
Salamander reference-grid constants."""

from __future__ import annotations

from lab.notes import (  # noqa: F401  (re-exported)
    A4_FREQ,
    A4_MIDI,
    NOTE_TO_SEMITONE,
    SEMITONE_TO_NAME,
    freq_to_midi,
    midi_to_freq,
    midi_to_name,
    name_to_midi,
)

# The 30 pitches sampled in the Salamander set (minor thirds from A0).
SALAMANDER_NOTES = [
    "A0", "C1", "D#1", "F#1", "A1", "C2", "D#2", "F#2", "A2", "C3", "D#3",
    "F#3", "A3", "C4", "D#4", "F#4", "A4", "C5", "D#5", "F#5", "A5", "C6",
    "D#6", "F#6", "A6", "C7", "D#7", "F#7", "A7", "C8",
]
SALAMANDER_VELS = [1, 6, 11, 16]
