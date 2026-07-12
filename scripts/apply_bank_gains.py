"""Write measured bank-normalization gains into the params tables.

  python scripts/apply_bank_gains.py

Values from scripts/measure_bank_loudness.py (A-weighted RMS at vel 96,
median over 3 register points, anchored to the piano). The same values
live in each instrument's calibrate config so recalibration keeps them.
"""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")

GAINS = {
    "instruments/woodblock/params/block.json": 3.9,
    "instruments/vibraphone/params/vibes.json": 4.7,
    "instruments/koto/params/tranh.json": 12.1,
    "instruments/rhodes/params/mk1.json": -14.1,
    "instruments/jamblock/params/jam.json": -4.0,
    "instruments/strings/params/vln.json": 5.6,
    "instruments/strings/params/vla.json": 3.4,
    "instruments/strings/params/vc.json": 1.0,
    "instruments/strings/params/cb.json": 17.9,
}


def main():
    for rel, gain in GAINS.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            print(f"MISSING: {rel}")
            continue
        with open(path) as f:
            t = json.load(f)
        t.setdefault("config", {})["gain_db"] = gain
        with open(path, "w") as f:
            json.dump(t, f)
        print(f"{rel}: gain_db={gain:+.1f}")


if __name__ == "__main__":
    main()
