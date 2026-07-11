"""Generic evaluation harness: render each benchmark case with a synth,
score it against its reference with an instrument-specific compare/score
pair, print progress, save rows.

Per-instrument eval scripts (e.g. scripts/evaluate.py for the piano) build
the case list and supply the compare/score functions."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable

import numpy as np

from .audio import load_mono


@dataclass
class EvalCase:
    name: str          # row label, e.g. "C4v11"
    midi: int
    velocity: float
    ref_path: str
    note: str          # note name passed to compare()
    release_at: float | None = None
    dur_cap: float = 8.0


def run_eval(
    cases: list[EvalCase],
    synth,                              # object with .synth_note(midi, vel, dur=, release_at=) and .sr
    compare_fn: Callable,               # (y, sr, ref_path, note) -> metrics dict
    score_fn: Callable,                 # (metrics dict) -> float
    out_path: str | None = None,
    save_wav_dir: str | None = None,
) -> list[dict]:
    import soundfile as sf

    rows = []
    for c in cases:
        ref, sr = load_mono(c.ref_path)
        dur = min(len(ref) / sr, c.dur_cap)
        y = synth.synth_note(c.midi, c.velocity, dur=dur, release_at=c.release_at)
        m = compare_fn(y, synth.sr, c.ref_path, c.note)
        m["name"] = c.name
        m["score"] = score_fn(m)
        rows.append(m)
        print(f"{c.name:8s} score={m['score']:6.3f}  f0c={m['f0_cents']:7.2f} "
              f"pc={m['partial_cents']}  dec={m['decay_logerr']} "
              f"lsdE={m['lsd_early']} lsdM={m['lsd_mid']} "
              f"env={m['env_db']} cent={m['centroid_ratio']}", flush=True)
        if save_wav_dir:
            os.makedirs(save_wav_dir, exist_ok=True)
            peak = np.max(np.abs(y)) + 1e-12
            sf.write(os.path.join(save_wav_dir, f"{c.name}.wav"),
                     (y / peak * 0.9).astype(np.float32), synth.sr)

    if rows:
        scores = [r["score"] for r in rows]
        print(f"\nmean score: {np.mean(scores):.3f}   median: {np.median(scores):.3f}"
              f"   worst: {max(scores):.3f} ({rows[int(np.argmax(scores))]['name']})")
        if out_path:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(rows, f, indent=1)
    return rows
