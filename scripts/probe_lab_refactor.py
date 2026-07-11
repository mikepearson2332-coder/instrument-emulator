"""Gate for the lab/ extraction: re-analyze notes and byte-compare against
the committed analysis JSONs (the moved code must reproduce them exactly)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from instruments.piano.analysis import analyze_to_json

ROOT = os.path.join(os.path.dirname(__file__), "..")

for name in ("C4v11", "A0v16", "C8v6", "F#6v1"):
    ref_json = os.path.join(ROOT, "reference", "piano", "analysis", f"{name}.json")
    flac = os.path.join(ROOT, "reference", "piano", "samples", f"{name}.flac")
    note = name.split("v")[0]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "test.json")
        analyze_to_json(flac, note, out)
        a = open(out, "rb").read()
        b = open(ref_json, "rb").read()
        verdict = "IDENTICAL" if a == b else "DIFFERS"
        print(f"{name}: {verdict} ({len(a)} vs {len(b)} bytes)")
        assert a == b, f"{name} analysis output changed after refactor"
print("OK")
