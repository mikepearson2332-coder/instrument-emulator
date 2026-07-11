"""Modal (additive) piano synthesizer driven by the calibrated parameter table.

Sound model per note:
  - N inharmonic partials f_n = n f0 sqrt(1 + B n^2)
  - each partial's envelope: a1 e^{-t/t1} + a2 e^{-t/t2} (two-stage decay)
  - slight per-partial unison detune -> gentle beating (three-string keys)
  - velocity: interpolates between calibrated layers in log-amplitude,
    which reproduces the measured brightness growth with velocity
  - attack: short filtered-noise hammer/key thump scaled with velocity
  - release: damper-controlled fade with frequency-dependent rate

No audio samples: the only data used is the fitted parameter table.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np
from scipy.signal import butter, sosfilt, stft

from .notes import name_to_midi, midi_to_freq

DEFAULT_TABLE = os.path.join(os.path.dirname(__file__), "params", "grand.json")

BAND_EDGES = np.geomspace(40.0, 8000.0, 11)
THUMP_TAU = 0.02  # s, attack-noise decay


class Piano:
    def __init__(self, table_path: str = DEFAULT_TABLE, sr: int = 48000, seed: int = 1234):
        with open(table_path) as f:
            self.table = json.load(f)
        self.sr = sr
        self.rng = np.random.default_rng(seed)
        self.keys = sorted(self.table["keys"], key=lambda k: k["midi"])
        self.key_midis = [k["midi"] for k in self.keys]
        self._init_band_noise()

    # ---------------------------------------------- band-noise calibration

    def _band_metric(self, x: np.ndarray, band: int) -> tuple[float, float]:
        """(steady dB, attack-max dB) of median STFT magnitude in a band —
        the same metric the analysis uses to measure bed/thump levels."""
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
        """Per-band bandpass filters + empirical level calibration so that
        synthesized noise reproduces measured bed/thump dB exactly under the
        same measurement code."""
        sr = self.sr
        self._band_sos = []
        self._cal_bed = []
        self._cal_thump = []
        rng = np.random.default_rng(99)
        probe = rng.standard_normal(sr)  # 1 s unit white noise
        tt = np.arange(sr) / sr
        thump_env = np.exp(-tt / THUMP_TAU)
        for i in range(len(BAND_EDGES) - 1):
            lo, hi = BAND_EDGES[i], BAND_EDGES[i + 1]
            sos = butter(4, [lo, min(hi, sr / 2 * 0.98)], btype="bandpass",
                         fs=sr, output="sos")
            self._band_sos.append(sos)
            nb = sosfilt(sos, probe)
            steady_db, _ = self._band_metric(nb, i)
            _, attack_db = self._band_metric(nb * thump_env, i)
            self._cal_bed.append(steady_db)
            self._cal_thump.append(attack_db)

    # ------------------------------------------------------- interpolation

    def _neighbor_keys(self, midi: int):
        """Sampled keys bracketing `midi` and the interpolation weight."""
        ms = self.key_midis
        if midi <= ms[0]:
            return self.keys[0], self.keys[0], 0.0
        if midi >= ms[-1]:
            return self.keys[-1], self.keys[-1], 0.0
        hi = next(i for i, m in enumerate(ms) if m >= midi)
        lo = hi - 1 if ms[hi] != midi else hi
        if ms[hi] == midi:
            return self.keys[hi], self.keys[hi], 0.0
        w = (midi - ms[lo]) / (ms[hi] - ms[lo])
        return self.keys[lo], self.keys[hi], w

    @staticmethod
    def _merge_partials(lo_partials, hi_partials, w):
        """Log-domain interpolation between two partial lists, matching by n.
        A partial missing on one side fades toward -80 dB of the other."""
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
            partials.append({
                "n": n,
                "a1": loglerp(a["a1"], b["a1"]),
                "t1": loglerp(a["t1"], b["t1"], 1e-3),
                "a2": loglerp(a["a2"], b["a2"]),
                "t2": loglerp(a["t2"], b["t2"], 1e-3),
            })
        return partials

    N_BANDS = len(BAND_EDGES) - 1

    @classmethod
    def _clean_profile(cls, prof, floor):
        if prof is None:
            return [floor] * cls.N_BANDS
        return [floor if v is None else float(v) for v in prof]

    @classmethod
    def _lerp_profile(cls, a, b, w, floor):
        a = cls._clean_profile(a, floor)
        b = cls._clean_profile(b, floor)
        return [x + (y - x) * w for x, y in zip(a, b)]

    @classmethod
    def _layer_state(cls, layer: dict) -> dict:
        return {
            "partials": [dict(p) for p in layer["partials"]],
            "thump_db": cls._clean_profile(layer.get("thump_db"), -120.0),
            "bed_db": cls._clean_profile(layer.get("bed_db"), -120.0),
            "bed_t60": cls._clean_profile(layer.get("bed_t60"), 10.0),
            "bed_anchor_s": float(layer.get("bed_anchor_s", 1.5) or 1.5),
            "symp_db": [(-140.0 if v is None else float(v))
                        for v in (layer.get("symp_db") or [])],
        }

    def _interp_layers(self, layers: list, velocity: float) -> dict:
        """Note state at arbitrary velocity (log-amp interpolation)."""
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
        n_lines = max(len(lo["symp_db"]), len(hi["symp_db"]))

        def pad(v):
            return v + [-140.0] * (n_lines - len(v))

        return {
            "partials": self._merge_partials(lo["partials"], hi["partials"], w),
            "thump_db": self._lerp_profile(lo["thump_db"], hi["thump_db"], w, -120.0),
            "bed_db": self._lerp_profile(lo["bed_db"], hi["bed_db"], w, -120.0),
            "bed_t60": self._lerp_profile(lo["bed_t60"], hi["bed_t60"], w, 10.0),
            "bed_anchor_s": lo["bed_anchor_s"] * (1 - w) + hi["bed_anchor_s"] * w,
            "symp_db": [a + (b - a) * w
                        for a, b in zip(pad(lo["symp_db"]), pad(hi["symp_db"]))],
        }

    def note_params(self, midi: int, velocity: float) -> dict:
        """Interpolated synthesis parameters for arbitrary key/velocity."""
        klo, khi, w = self._neighbor_keys(midi)
        slo = self._interp_layers(klo["layers"], velocity)
        if klo is khi:
            f0 = klo["f0"] * midi_to_ratio(midi - klo["midi"])
            return {"f0": f0, "B": klo["B"], **slo}
        shi = self._interp_layers(khi["layers"], velocity)

        # keep each neighbor's stretch deviation, interpolate in cents
        dev_lo = 1200 * math.log2(klo["f0"] / midi_to_freq(klo["midi"]))
        dev_hi = 1200 * math.log2(khi["f0"] / midi_to_freq(khi["midi"]))
        dev = dev_lo + (dev_hi - dev_lo) * w
        f0 = midi_to_freq(midi) * 2 ** (dev / 1200)
        logB = math.log(klo["B"]) + (math.log(khi["B"]) - math.log(klo["B"])) * w
        n_lines = max(len(slo["symp_db"]), len(shi["symp_db"]))

        def pad(v):
            return v + [-140.0] * (n_lines - len(v))

        return {
            "f0": f0,
            "B": math.exp(logB),
            "partials": self._merge_partials(slo["partials"], shi["partials"], w),
            "thump_db": self._lerp_profile(slo["thump_db"], shi["thump_db"], w, -120.0),
            "bed_db": self._lerp_profile(slo["bed_db"], shi["bed_db"], w, -120.0),
            "bed_t60": self._lerp_profile(slo["bed_t60"], shi["bed_t60"], w, 10.0),
            "bed_anchor_s": slo["bed_anchor_s"] * (1 - w) + shi["bed_anchor_s"] * w,
            "symp_db": [a + (b - a) * w
                        for a, b in zip(pad(slo["symp_db"]), pad(shi["symp_db"]))],
        }

    # ------------------------------------------------------------ synthesis

    def synth_note(
        self,
        midi: int,
        velocity: float,
        dur: float = 4.0,
        release_at: float | None = None,
        sustain_pedal: bool = False,
    ) -> np.ndarray:
        """Render one note. `dur` = total render length in seconds;
        `release_at` = key release time (None = hold to the end)."""
        sr = self.sr
        p = self.note_params(midi, velocity)
        f0, B = p["f0"], p["B"]
        n_samp = int(dur * sr)
        t = np.arange(n_samp) / sr
        out = np.zeros(n_samp)

        # number of unison strings (approx: 1 below ~B1, 2 to ~E2, else 3)
        if midi < 33:
            n_strings = 1
        elif midi < 41:
            n_strings = 2
        else:
            n_strings = 3

        # unison detunings in cents per string (measured pianos: ~0.5-2 c in
        # the midrange, growing to 10-30 c total spread in the top octave)
        det_sets = {1: [0.0], 2: [-0.55, 0.55], 3: [-0.9, 0.12, 1.0]}
        det_scale = 1.0 + max(0, midi - 76) * 0.7
        dets = [d * det_scale for d in det_sets[n_strings]]

        nyq = sr * 0.5 * 0.95
        for prt in p["partials"]:
            n = prt["n"]
            fn = n * f0 * math.sqrt(1 + B * n * n)
            if fn >= nyq:
                continue
            a1, t1, a2, t2 = prt["a1"], prt["t1"], prt["a2"], prt["t2"]
            if a1 + a2 <= 0:
                continue
            env = a1 * np.exp(-t / max(t1, 1e-3)) + a2 * np.exp(-t / max(t2, 1e-3))
            if midi < 76 and n_strings > 1:
                # The measured envelope already contains the unison strings'
                # decoherence — splitting it across detuned copies would
                # double-count the level drop. Use level-preserving
                # multiplicative beating instead (mean gain = 1).
                span_c = (dets[-1] - dets[0]) * (1 + 0.02 * n)
                dfreq = fn * span_c * math.log(2) / 1200.0
                m = 0.35 if n_strings == 3 else 0.3
                beat = 1.0 + m * np.cos(
                    2 * np.pi * dfreq * t + self.rng.uniform(0, 2 * np.pi))
                if n_strings == 3:
                    beat += 0.18 * np.cos(
                        2 * np.pi * dfreq * 0.55 * t + self.rng.uniform(0, 2 * np.pi))
                phase = self.rng.uniform(-0.25, 0.25)
                out += env * beat * np.sin(2 * np.pi * fn * t + phase)
            else:
                # top octave: splits are tens of cents — genuinely resolved
                # spectral lines, so render the detuned strings explicitly
                wts = 1.0 + self.rng.uniform(-0.35, 0.35, size=len(dets))
                wts /= wts.sum()
                for d, wt in zip(dets, wts):
                    jit = self.rng.uniform(0.7, 1.3)
                    f = fn * 2.0 ** (d * jit * (1 + 0.02 * n) / 1200.0)
                    phase = self.rng.uniform(-0.25, 0.25)
                    out += (env * wt) * np.sin(2 * np.pi * f * t + phase)

        # --- broadband components: attack thump + sympathetic resonance bed
        thump_db = p.get("thump_db", [-120.0] * self.N_BANDS)
        bed_db = p.get("bed_db", [-120.0] * self.N_BANDS)
        bed_t60 = p.get("bed_t60", [10.0] * self.N_BANDS)
        for i in range(self.N_BANDS):
            g_thump = thump_db[i]
            g_bed = bed_db[i]
            if g_thump < -100 and g_bed < -100:
                continue
            nb = sosfilt(self._band_sos[i], self.rng.standard_normal(n_samp))
            comp = np.zeros(n_samp)
            if g_bed > -100:
                t60 = max(bed_t60[i], 0.3)
                # measured level is anchored mid-way through the analysis
                # window, not at t=0: add back 60 dB/t60 * anchor (cap 20 dB)
                comp_db = min(20.0, 60.0 * p.get("bed_anchor_s", 1.5) / t60)
                gain = 10 ** ((g_bed - self._cal_bed[i] + comp_db) / 20)
                comp += gain * 10 ** (-3.0 * t / t60)
            if g_thump > -100:
                gain = 10 ** ((g_thump - self._cal_thump[i]) / 20)
                comp += gain * np.exp(-t / THUMP_TAU)
            out += nb * comp

        # --- release / damper (keys above ~F#6 have no dampers)
        if (release_at is not None and release_at < dur
                and not sustain_pedal and midi < 89):
            r0 = int(release_at * sr)
            fade_t = 0.12 if midi < 60 else 0.06
            ntail = n_samp - r0
            fade = np.exp(-np.arange(ntail) / (fade_t * sr))
            # dampers kill string modes but a soft body/bed remnant rings on
            remnant = 0.02 * np.exp(-np.arange(ntail) / (1.0 * sr))
            out[r0:] *= np.maximum(fade, remnant)

        # --- sympathetic / body resonance lines (not damped by this key)
        lines = self.table.get("symp_lines") or []
        symp_db = p.get("symp_db") or []
        anchor = float(self.table.get("symp_anchor_s", 1.2))
        ramp = np.minimum(t / 0.03, 1.0)
        for j, ln in enumerate(lines[: len(symp_db)]):
            db = symp_db[j]
            if db <= -130:
                continue
            t60 = max(float(ln["t60"]), 0.5)
            # measured at `anchor` seconds; extrapolate to t=0 (cap +15 dB)
            a0 = 10 ** ((db + min(15.0, 60.0 * anchor / t60)) / 20)
            env = a0 * 10 ** (-3.0 * t / t60)
            phase = self.rng.uniform(0, 2 * np.pi)
            out += ramp * env * np.sin(2 * np.pi * ln["freq"] * t + phase)

        return out

    def synth_chord(
        self, notes: list[tuple[int, float]], dur: float = 4.0, **kw
    ) -> np.ndarray:
        out = None
        for midi, vel in notes:
            y = self.synth_note(midi, vel, dur=dur, **kw)
            out = y if out is None else out + y
        return out


def midi_to_ratio(semitones: float) -> float:
    return 2.0 ** (semitones / 12.0)
