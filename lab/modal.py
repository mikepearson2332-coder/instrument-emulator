"""Generic modal-instrument synthesizer driven by a calibrated table.

Config-driven sibling of the piano synth (`instruments/piano/synth.py`) for
instruments in the modal engine family that are NOT pianos: struck/plucked
resonators without unison-string beating (woodblock, mallets/bells, plucked
strings). The piano keeps its own synth; this module is the executable
reference implementation for every table whose partials may carry explicit
frequency ratios (`fr`) instead of the inharmonic-string series.

Table schema (superset of the piano's; `config` drives the differences):

  {
    "version": 1,
    "instrument": "woodblock",
    "config": {
      "sr": 44100,                 # native rate of the reference
      "thump_tau_s": 0.010,        # attack-noise decay (piano: 0.02)
      "attack_s": 0.0015,          # partial onset ramp (0 = instant)
      "release_fade_s": null,      # null: note-off ignored (no dampers)
                                   # number: exponential fade on release
      "release_remnant": 0.0,      # residual level that rings after damping
      "undamped_above": null,      # midi above which release is a no-op
      "pol_beat_m": [0.3, 0.8],    # dual-polarization beat depth range
      "pol_beat_cents": [0.5, 2.0] # ... and detune range (plucked strings)
    },
    "keys": [ {note, midi, f0, B, layers: [ {vel, peak, thump_db, bed_db,
        bed_t60, bed_anchor_s, partials: [{n, fr, a1, t1, a2, t2}]} ]} ]
  }

Partial frequency: fr * f0 when "fr" present, else n*f0*sqrt(1+B n^2).
Within one table all partials must agree on which convention they use.
"""

from __future__ import annotations

import json
import math

import numpy as np
from scipy.signal import butter, sosfilt, stft

from .notes import midi_to_freq

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)  # shared with the Rust engine
N_BANDS = len(BAND_EDGES) - 1


def _clean_profile(prof, floor, n=N_BANDS):
    if prof is None:
        return [floor] * n
    return [floor if v is None else float(v) for v in prof]


def _lerp(a, b, w):
    return [x + (y - x) * w for x, y in zip(a, b)]


class ModalSynth:
    """Offline reference renderer for generic modal tables."""

    def __init__(self, table_path: str, sr: int | None = None, seed: int = 1234):
        with open(table_path) as f:
            self.table = json.load(f)
        cfg = self.table.get("config", {})
        self.sr = int(sr or cfg.get("sr", 48000))
        self.thump_tau = float(cfg.get("thump_tau_s", 0.02))
        tb = cfg.get("thump_tau_bands")
        self.thump_taus = ([float(v) for v in tb] if tb
                           else [self.thump_tau] * N_BANDS)
        self.attack_s = float(cfg.get("attack_s", 0.0) or 0.0)
        self.pol_beat_m = cfg.get("pol_beat_m")        # [lo, hi] or None
        self.pol_beat_cents = cfg.get("pol_beat_cents")
        self.release_fade_s = cfg.get("release_fade_s")  # None -> undamped
        self.release_remnant = float(cfg.get("release_remnant", 0.0) or 0.0)
        self.undamped_above = cfg.get("undamped_above")
        self.rng = np.random.default_rng(seed)
        self.keys = sorted(self.table["keys"], key=lambda k: k["midi"])
        self.key_midis = [k["midi"] for k in self.keys]
        self._init_band_noise()

    # ---------------------------------------------- band-noise calibration
    # Identical conventions to the piano synth (and core/engine): the same
    # scipy STFT median-band metric the analysis uses. Never convert
    # analytically — see the piano DEVLOG.

    def _band_metric(self, x: np.ndarray, band: int) -> tuple[float, float]:
        sr = self.sr
        nper = int(0.046 * sr)
        nover = nper - int(0.010 * sr)
        f, t, Z = stft(x, sr, nperseg=nper, noverlap=nover, padded=False)
        A = np.abs(Z)
        sel = (f >= BAND_EDGES[band]) & (f < BAND_EDGES[band + 1])
        med = np.median(A[sel], axis=0)
        steady = float(np.median(med))
        attack = float(med[t < 0.12].max()) if (t < 0.12).any() else steady
        return (20 * math.log10(steady + 1e-12),
                20 * math.log10(attack + 1e-12))

    def _init_band_noise(self):
        sr = self.sr
        self._band_sos = []
        self._cal_bed = []
        self._cal_thump = []
        rng = np.random.default_rng(99)
        probe = rng.standard_normal(sr)
        tt = np.arange(sr) / sr
        for i in range(N_BANDS):
            lo, hi = BAND_EDGES[i], BAND_EDGES[i + 1]
            sos = butter(4, [lo, min(hi, sr / 2 * 0.98)], btype="bandpass",
                         fs=sr, output="sos")
            self._band_sos.append(sos)
            nb = sosfilt(sos, probe)
            steady_db, _ = self._band_metric(nb, i)
            thump_env = np.exp(-tt / self.thump_taus[i])
            _, attack_db = self._band_metric(nb * thump_env, i)
            self._cal_bed.append(steady_db)
            self._cal_thump.append(attack_db)

    # ------------------------------------------------------- interpolation

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
    def _merge_partials(lo_partials, hi_partials, w):
        """Log-domain interpolation matched by mode index n; fr included."""
        lo_p = {p["n"]: p for p in lo_partials}
        hi_p = {p["n"]: p for p in hi_partials}

        def loglerp(a, b, floor=1e-9):
            la, lb = math.log(max(a, floor)), math.log(max(b, floor))
            return math.exp(la + (lb - la) * w)

        partials = []
        for n in sorted(set(lo_p) | set(hi_p)):
            a = lo_p.get(n)
            b = hi_p.get(n)
            if a is None:
                a = {**b, "a1": b["a1"] * 1e-4, "a2": b["a2"] * 1e-4}
            if b is None:
                b = {**a, "a1": a["a1"] * 1e-4, "a2": a["a2"] * 1e-4}
            out = {
                "n": n,
                "a1": loglerp(a["a1"], b["a1"]),
                "t1": loglerp(a["t1"], b["t1"], 1e-4),
                "a2": loglerp(a["a2"], b["a2"]),
                "t2": loglerp(a["t2"], b["t2"], 1e-4),
            }
            if "fr" in a or "fr" in b:
                fra = a.get("fr", b.get("fr"))
                frb = b.get("fr", a.get("fr"))
                out["fr"] = loglerp(fra, frb, 1e-6)
            partials.append(out)
        return partials

    @classmethod
    def _layer_state(cls, layer: dict) -> dict:
        return {
            "partials": [dict(p) for p in layer["partials"]],
            "thump_db": _clean_profile(layer.get("thump_db"), -120.0),
            "bed_db": _clean_profile(layer.get("bed_db"), -120.0),
            "bed_t60": _clean_profile(layer.get("bed_t60"), 10.0),
            "bed_anchor_s": float(layer.get("bed_anchor_s", 1.5) or 1.5),
        }

    def _interp_layers(self, layers: list, velocity: float) -> dict:
        vs = [L["vel"] for L in layers]
        if velocity <= vs[0]:
            return self._layer_state(layers[0])
        if velocity >= vs[-1]:
            return self._layer_state(layers[-1])
        j = next(i for i, v in enumerate(vs) if v >= velocity)
        if vs[j] == velocity:
            return self._layer_state(layers[j])
        i = j - 1
        w = (velocity - vs[i]) / (vs[j] - vs[i])
        lo, hi = self._layer_state(layers[i]), self._layer_state(layers[j])
        return {
            "partials": self._merge_partials(lo["partials"], hi["partials"], w),
            "thump_db": _lerp(lo["thump_db"], hi["thump_db"], w),
            "bed_db": _lerp(lo["bed_db"], hi["bed_db"], w),
            "bed_t60": _lerp(lo["bed_t60"], hi["bed_t60"], w),
            "bed_anchor_s": lo["bed_anchor_s"] * (1 - w) + hi["bed_anchor_s"] * w,
        }

    def note_params(self, midi: int, velocity: float) -> dict:
        klo, khi, w = self._neighbor_keys(midi)
        slo = self._interp_layers(klo["layers"], velocity)
        if klo is khi:
            f0 = klo["f0"] * 2.0 ** ((midi - klo["midi"]) / 12.0)
            return {"f0": f0, "B": klo.get("B", 0.0), **slo}
        shi = self._interp_layers(khi["layers"], velocity)
        dev_lo = 1200 * math.log2(klo["f0"] / midi_to_freq(klo["midi"]))
        dev_hi = 1200 * math.log2(khi["f0"] / midi_to_freq(khi["midi"]))
        dev = dev_lo + (dev_hi - dev_lo) * w
        f0 = midi_to_freq(midi) * 2 ** (dev / 1200)
        blo = max(klo.get("B", 0.0), 1e-12)
        bhi = max(khi.get("B", 0.0), 1e-12)
        logB = math.log(blo) + (math.log(bhi) - math.log(blo)) * w
        B = math.exp(logB)
        return {
            "f0": f0,
            "B": 0.0 if B <= 1e-11 else B,
            "partials": self._merge_partials(slo["partials"], shi["partials"], w),
            "thump_db": _lerp(slo["thump_db"], shi["thump_db"], w),
            "bed_db": _lerp(slo["bed_db"], shi["bed_db"], w),
            "bed_t60": _lerp(slo["bed_t60"], shi["bed_t60"], w),
            "bed_anchor_s": slo["bed_anchor_s"] * (1 - w) + shi["bed_anchor_s"] * w,
        }

    # ------------------------------------------------------------ synthesis

    def _partial_freq(self, prt: dict, f0: float, B: float) -> float:
        if "fr" in prt and prt["fr"] is not None:
            return prt["fr"] * f0
        n = prt["n"]
        return n * f0 * math.sqrt(1 + B * n * n)

    def synth_note(
        self,
        midi: int,
        velocity: float,
        dur: float = 2.0,
        release_at: float | None = None,
        sustain_pedal: bool = False,
    ) -> np.ndarray:
        sr = self.sr
        p = self.note_params(midi, velocity)
        f0, B = p["f0"], p["B"]
        n_samp = int(dur * sr)
        t = np.arange(n_samp) / sr
        out = np.zeros(n_samp)

        nyq = sr * 0.5 * 0.95
        # contact-time onset ramp: kills the broadband splatter of a
        # discontinuous sine start (real modes rise over ~1-3 ms)
        ramp = np.minimum(t / self.attack_s, 1.0) if self.attack_s > 0 else None
        for prt in p["partials"]:
            fn = self._partial_freq(prt, f0, B)
            if fn >= nyq or fn <= 0:
                continue
            a1, t1, a2, t2 = prt["a1"], prt["t1"], prt["a2"], prt["t2"]
            if a1 + a2 <= 0:
                continue
            env = a1 * np.exp(-t / max(t1, 1e-4)) + a2 * np.exp(-t / max(t2, 1e-4))
            if ramp is not None:
                env = env * ramp
            if self.pol_beat_m is not None:
                # dual-polarization beating: each partial's two orthogonal
                # string polarizations are detuned by a fraction of a cent
                # to a couple of cents, producing the dip-and-recover
                # envelopes real plucked strings show (Weinreich). The
                # polarizations start IN PHASE at the pluck (dip comes at
                # half the beat period); normalize so t=0 keeps the
                # measured amplitude.
                m = self.rng.uniform(*self.pol_beat_m)
                span = self.rng.uniform(*self.pol_beat_cents)
                dfreq = fn * span * math.log(2) / 1200.0
                ph = self.rng.uniform(-0.4, 0.4)
                env = env * ((1.0 + m * np.cos(2 * np.pi * dfreq * t + ph))
                             / (1.0 + m * math.cos(ph)))
            phase = self.rng.uniform(-0.25, 0.25)
            out += env * np.sin(2 * np.pi * fn * t + phase)

        # broadband: attack thump + resonance/room bed (same model as piano)
        thump_db = p["thump_db"]
        bed_db = p["bed_db"]
        bed_t60 = p["bed_t60"]
        for i in range(N_BANDS):
            g_thump = thump_db[i]
            g_bed = bed_db[i]
            if g_thump < -100 and g_bed < -100:
                continue
            nb = sosfilt(self._band_sos[i], self.rng.standard_normal(n_samp))
            comp = np.zeros(n_samp)
            if g_bed > -100:
                t60 = max(bed_t60[i], 0.1)
                comp_db = min(20.0, 60.0 * p.get("bed_anchor_s", 1.5) / t60)
                gain = 10 ** ((g_bed - self._cal_bed[i] + comp_db) / 20)
                comp += gain * 10 ** (-3.0 * t / t60)
            if g_thump > -100:
                gain = 10 ** ((g_thump - self._cal_thump[i]) / 20)
                comp += gain * np.exp(-t / self.thump_taus[i])
            out += nb * comp

        # release / damping
        damped = (self.release_fade_s is not None
                  and release_at is not None and release_at < dur
                  and not sustain_pedal
                  and (self.undamped_above is None or midi <= self.undamped_above))
        if damped:
            r0 = int(release_at * sr)
            ntail = n_samp - r0
            fade = np.exp(-np.arange(ntail) / (self.release_fade_s * sr))
            if self.release_remnant > 0:
                rem = self.release_remnant * np.exp(-np.arange(ntail) / (1.0 * sr))
                fade = np.maximum(fade, rem)
            out[r0:] *= fade

        return out

    def synth_chord(self, notes, dur: float = 2.0, **kw) -> np.ndarray:
        out = None
        for midi, vel in notes:
            y = self.synth_note(midi, vel, dur=dur, **kw)
            out = y if out is None else out + y
        return out
