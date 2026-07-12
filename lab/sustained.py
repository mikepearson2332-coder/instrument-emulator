"""Generic sustained-instrument synthesizer (engine family 2 reference).

Continuous-excitation sibling of `lab/modal.py`: a bank of harmonic
oscillators with slow stochastic FM/AM (the ensemble effect), a shared
vibrato LFO, per-band steady bow/breath noise, and a sustain envelope
(rise -> undulating sustain -> two-stage release on note-off). This is
the executable reference for the Rust `sustained` engine family.

Table schema:

  {
    "version": 1,
    "instrument": "strings",
    "config": {
      "engine": "sustained",
      "sr": 44100,
      "drift_cents": 6.0,     # per-harmonic ensemble detune (rms, cents)
      "drift_hz": 1.0,        # ... bandwidth of the random detune walk
      "vib_cents": 7.0,       # shared vibrato FM depth (peak, cents)
      "harm_am_db": 1.0,      # per-harmonic slow AM (rms, dB)
      "release_floor_db": -80
    },
    "keys": [ {note, midi, f0, layers: [ {vel, peak, rms,
        harm: [{n, a}],                  # absolute linear amplitudes
        noise_db: [10 bands],            # steady bed, STFT-median dB
        rise_s, und_db, und_hz, vib_hz, vib_am_db,
        rel_s, rel_remnant, rel_tail_s} ]} ]
  }

All stochastic processes are piecewise-constant-frequency / lowpassed
noise updated the same way the Rust engine will do it, so the two
implementations match statistically.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import butter, sosfilt, stft

from .notes import midi_to_freq

# the sustained family has its own noise bands (bow/breath noise extends
# well past the modal family's 8 kHz) and its own measurement convention:
# 0.2 s STFT windows (a 46 ms window cannot resolve non-harmonic bins
# between low-string harmonics), hop 50 ms, median across non-harmonic
# bins. The synth self-calibrates through the IDENTICAL metric.
BAND_EDGES = np.geomspace(40.0, 16000.0, 13)
N_BANDS = len(BAND_EDGES) - 1
NOISE_WIN_S = 0.2
NOISE_HOP_S = 0.05

LN2_1200 = math.log(2.0) / 1200.0


def _lerp(a, b, w):
    return a + (b - a) * w


def _lerp_list(a, b, w, floor=-150.0):
    out = []
    for x, y in zip(a, b):
        x = floor if x is None else x
        y = floor if y is None else y
        out.append(x + (y - x) * w)
    return out


class SustainedSynth:
    """Offline reference renderer for sustained tables."""

    def __init__(self, table_path: str, sr: int | None = None, seed: int = 1234):
        with open(table_path) as f:
            self.table = json.load(f)
        cfg = self.table.get("config", {})
        assert cfg.get("engine") == "sustained"
        self.sr = int(sr or cfg.get("sr", 44100))
        self.drift_cents = float(cfg.get("drift_cents", 6.0))
        self.drift_hz = float(cfg.get("drift_hz", 1.0))
        self.vib_cents = float(cfg.get("vib_cents", 7.0))
        self.harm_am_db = float(cfg.get("harm_am_db", 1.0))
        # bank loudness normalization (dB), anchored to the piano
        self.gain_db = float(cfg.get("gain_db", 0.0) or 0.0)
        self.rng = np.random.default_rng(seed)
        self.keys = sorted(self.table["keys"], key=lambda k: k["midi"])
        self.key_midis = [k["midi"] for k in self.keys]
        self._init_band_noise()

    # ------------------------------------------------- noise calibration
    def _band_metric_steady(self, x: np.ndarray, band: int) -> float:
        sr = self.sr
        nper = int(NOISE_WIN_S * sr)
        nover = nper - int(NOISE_HOP_S * sr)
        f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
        A = np.abs(Z)
        sel = (f >= BAND_EDGES[band]) & (f < BAND_EDGES[band + 1])
        med = np.median(A[sel], axis=0)
        return 20 * math.log10(float(np.median(med)) + 1e-12)

    def _init_band_noise(self):
        sr = self.sr
        self._band_sos = []
        self._cal_bed = []
        rng = np.random.default_rng(99)
        probe = rng.standard_normal(sr)
        for i in range(N_BANDS):
            lo, hi = BAND_EDGES[i], BAND_EDGES[i + 1]
            sos = butter(4, [lo, min(hi, sr / 2 * 0.98)], btype="bandpass",
                         fs=sr, output="sos")
            self._band_sos.append(sos)
            nb = sosfilt(sos, probe)
            self._cal_bed.append(self._band_metric_steady(nb, i))

    # ------------------------------------------------------ interpolation
    def _neighbor_keys(self, midi: int):
        ms = self.key_midis
        if midi <= ms[0]:
            return self.keys[0], self.keys[0], 0.0
        if midi >= ms[-1]:
            return self.keys[-1], self.keys[-1], 0.0
        hi = next(i for i, m in enumerate(ms) if m >= midi)
        if ms[hi] == midi:
            return self.keys[hi], self.keys[hi], 0.0
        lo = hi - 1
        w = (midi - ms[lo]) / (ms[hi] - ms[lo])
        return self.keys[lo], self.keys[hi], w

    @staticmethod
    def _merge_harm(lo_h, hi_h, w):
        lo_m = {h["n"]: h["a"] for h in lo_h}
        hi_m = {h["n"]: h["a"] for h in hi_h}
        out = []
        for n in sorted(set(lo_m) | set(hi_m)):
            a = lo_m.get(n, hi_m.get(n, 0.0) * 1e-4)
            b = hi_m.get(n, lo_m.get(n, 0.0) * 1e-4)
            la, lb = math.log(max(a, 1e-12)), math.log(max(b, 1e-12))
            out.append({"n": n, "a": math.exp(la + (lb - la) * w)})
        return out

    _SCALARS = ("rise_s", "und_db", "und_hz", "vib_hz", "vib_am_db",
                "rel_s", "rel_remnant", "rel_tail_s")

    def _merge_layers(self, lo, hi, w):
        out = {k: _lerp(lo[k], hi[k], w) for k in self._SCALARS}
        out["harm"] = self._merge_harm(lo["harm"], hi["harm"], w)
        out["noise_db"] = _lerp_list(lo["noise_db"], hi["noise_db"], w)
        return out

    def _interp_layers(self, layers, velocity):
        def state(L):
            return {**{k: float(L[k]) for k in self._SCALARS},
                    "harm": [dict(h) for h in L["harm"]],
                    "noise_db": [(-150.0 if v is None else float(v))
                                 for v in L["noise_db"]]}
        vs = [L["vel"] for L in layers]
        if velocity <= vs[0]:
            return state(layers[0])
        if velocity >= vs[-1]:
            return state(layers[-1])
        j = next(i for i, v in enumerate(vs) if v >= velocity)
        if vs[j] == velocity:
            return state(layers[j])
        i = j - 1
        w = (velocity - vs[i]) / (vs[j] - vs[i])
        return self._merge_layers(state(layers[i]), state(layers[j]), w)

    def _apply_gain(self, p: dict) -> dict:
        """Bank loudness normalization (mirrors the Rust engine)."""
        if self.gain_db == 0.0:
            return p
        g = 10.0 ** (self.gain_db / 20.0)
        for h in p["harm"]:
            h["a"] *= g
        p["noise_db"] = [v + self.gain_db for v in p["noise_db"]]
        return p

    def note_params(self, midi: int, velocity: float) -> dict:
        klo, khi, w = self._neighbor_keys(midi)
        slo = self._interp_layers(klo["layers"], velocity)
        if klo is khi:
            f0 = klo["f0"] * 2.0 ** ((midi - klo["midi"]) / 12.0)
            return self._apply_gain({"f0": f0, **slo})
        shi = self._interp_layers(khi["layers"], velocity)
        dev_lo = 1200 * math.log2(klo["f0"] / midi_to_freq(klo["midi"]))
        dev_hi = 1200 * math.log2(khi["f0"] / midi_to_freq(khi["midi"]))
        dev = dev_lo + (dev_hi - dev_lo) * w
        f0 = midi_to_freq(midi) * 2 ** (dev / 1200)
        return self._apply_gain({"f0": f0, **self._merge_layers(slo, shi, w)})

    # --------------------------------------------------------- generators
    def _lp_noise(self, n_samp: int, f_c: float, hop: int = 64) -> np.ndarray:
        """Unit-rms lowpassed noise, updated every `hop` samples (matches
        the Rust per-block update) and linearly interpolated between."""
        sr = self.sr
        m = n_samp // hop + 2
        alpha = math.exp(-2.0 * math.pi * f_c * hop / sr)
        w = self.rng.standard_normal(m)
        y = np.empty(m)
        acc = 0.0
        for i in range(m):
            acc = alpha * acc + (1 - alpha) * w[i]
            y[i] = acc
        # analytic stationary gain of the one-pole (NOT the realized
        # std: that is data-dependent and a streaming engine cannot
        # reproduce it — the Rust voice uses this exact formula)
        g = math.sqrt((1 - alpha) / (1 + alpha))
        y = y / (g + 1e-12)
        t = np.arange(n_samp) / hop
        i0 = np.floor(t).astype(int)
        fr = t - i0
        return y[i0] * (1 - fr) + y[i0 + 1] * fr

    # ------------------------------------------------------------- render
    def synth_note(self, midi: int, velocity: float, dur: float = 6.0,
                   release_at: float | None = None,
                   sustain_pedal: bool = False) -> np.ndarray:
        sr = self.sr
        p = self.note_params(midi, velocity)
        f0 = p["f0"]
        n_samp = int(dur * sr)
        t = np.arange(n_samp) / sr
        out = np.zeros(n_samp)
        if release_at is None:
            release_at = max(dur - 3.0 * p["rel_s"], dur * 0.7)

        # ---- global envelope: smoothstep rise, undulation, vibrato AM
        rise = np.clip(t / max(p["rise_s"], 0.02), 0.0, 1.0)
        env = rise * rise * (3.0 - 2.0 * rise)
        und = self._lp_noise(n_samp, max(p["und_hz"], 0.15))
        vib_ph = self.rng.uniform(0, 2 * math.pi)
        vib = np.sin(2 * math.pi * p["vib_hz"] * t + vib_ph)
        # clamp the log-domain excursion: pathological table values must
        # degrade gracefully, never blow up the render (Rust mirrors this)
        exc = np.clip(p["und_db"] * und + p["vib_am_db"] * vib, -12.0, 12.0)
        gmod = 10.0 ** (exc / 20.0)
        env = env * gmod
        # release: exponential fade + slower remnant tail
        r0 = int(release_at * sr)
        if r0 < n_samp:
            tt = np.arange(n_samp - r0) / sr
            fade = np.exp(-tt / max(p["rel_s"], 0.02))
            if p["rel_remnant"] > 1e-4:
                fade = np.maximum(
                    fade, p["rel_remnant"]
                    * np.exp(-tt / max(p["rel_tail_s"], 0.05)))
            env[r0:] = env[r0:] * fade

        # ---- harmonics with shared vibrato FM + per-harmonic drift/AM
        nyq = sr * 0.5 * 0.95
        for h in p["harm"]:
            fn = h["n"] * f0
            if fn >= nyq or h["a"] <= 0:
                continue
            drift = self._lp_noise(n_samp, self.drift_hz)
            cents = self.vib_cents * vib + self.drift_cents * drift
            freq = fn * (1.0 + LN2_1200 * cents)
            phase = (2 * math.pi * np.cumsum(freq) / sr
                     + self.rng.uniform(0, 2 * math.pi))
            am = 1.0 + (10.0 ** (self.harm_am_db / 20.0) - 1.0) \
                * self._lp_noise(n_samp, max(p["und_hz"], 0.3))
            out += h["a"] * env * np.maximum(am, 0.05) * np.sin(phase)

        # ---- steady bow-noise bed, follows the envelope
        # NOTE: absolute per-bin medians in the 0.2 s convention run far
        # below -100 dB for real content spread over many bins — gate
        # only true sentinels (unmeasurable bands), never real levels
        for i in range(N_BANDS):
            g_db = p["noise_db"][i]
            if g_db < -140:
                continue
            nb = sosfilt(self._band_sos[i], self.rng.standard_normal(n_samp))
            gain = 10 ** ((g_db - self._cal_bed[i]) / 20)
            out += nb * gain * env

        return out

    def synth_chord(self, notes, dur: float = 6.0, **kw) -> np.ndarray:
        out = None
        for midi, vel in notes:
            y = self.synth_note(midi, vel, dur=dur, **kw)
            out = y if out is None else out + y
        return out
