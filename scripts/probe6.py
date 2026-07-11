"""Which component makes which part of the C8v6 spectrum?"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from pianomodel.synth import Piano
from pianomodel.analysis import load_mono, find_onset

ROOT = os.path.join(os.path.dirname(__file__), "..")


def band_levels(y, sr, t0, t1):
    seg = y[int(t0 * sr): int(t1 * sr)]
    w = np.hanning(len(seg))
    mag = np.abs(np.fft.rfft(seg * w))
    fax = np.fft.rfftfreq(len(seg), 1 / sr)
    out = []
    for lo, hi in [(100, 500), (500, 2000), (2000, 4500), (4500, 6000), (6000, 12000)]:
        sel = (fax >= lo) & (fax < hi)
        out.append(round(20 * np.log10(np.sqrt((mag[sel] ** 2).mean()) + 1e-12), 1))
    return out


piano = Piano()
midi, vel = 108, 48

ref, sr = load_mono(os.path.join(ROOT, "reference", "samples", "C8v6.flac"))
ref = ref[find_onset(ref, sr):]

full = piano.synth_note(midi, vel, dur=3.5)

# mute components by monkeypatching profiles
def render(mutate):
    orig = piano.note_params
    def patched(m, v):
        q = orig(m, v)
        mutate(q)
        return q
    piano.note_params = patched
    y = piano.synth_note(midi, vel, dur=3.5)
    piano.note_params = orig
    return y

no_thump = render(lambda q: q.update(thump_db=[-140] * 10))
no_bed = render(lambda q: q.update(bed_db=[-140] * 10))
no_symp = render(lambda q: q.update(symp_db=[-140] * len(q.get("symp_db", []))))
only_partials = render(lambda q: q.update(thump_db=[-140] * 10, bed_db=[-140] * 10,
                                          symp_db=[-140] * len(q.get("symp_db", []))))

print("bands: 100-500 | 500-2k | 2k-4.5k | 4.5k-6k | 6k-12k   (dB, 0-0.5 s)")
for label, y in [("ref", ref), ("full", full), ("no_thump", no_thump),
                 ("no_bed", no_bed), ("no_symp", no_symp), ("partials", only_partials)]:
    print(f"{label:10s}", band_levels(y, sr if label == 'ref' else piano.sr, 0.0, 0.5))
print("\nsame, 1.0-2.5 s")
for label, y in [("ref", ref), ("full", full), ("no_thump", no_thump),
                 ("no_bed", no_bed), ("no_symp", no_symp), ("partials", only_partials)]:
    print(f"{label:10s}", band_levels(y, sr if label == 'ref' else piano.sr, 1.0, 2.5))
