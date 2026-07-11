"""Shared instrument lab: the instrument-agnostic half of the
analysis / calibration / evaluation pipeline.

Modules:
  notes        note-name / MIDI / frequency utilities
  audio        loading, onset detection
  partials     partial tracking, per-partial envelopes, decay fitting
               (the modal engine family's shared measurement machinery)
  metrics      band spectrogram, log-spectral distance
  evalharness  generic render-and-score benchmark runner

Per-instrument code (instruments/<name>/) supplies: the analysis recipe,
calibration (fits the parameter table), the compare() metric set, and the
composite-score weights. See .claude/skills/instrument-dev/ for the workflow.
"""
