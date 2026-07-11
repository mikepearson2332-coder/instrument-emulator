//! Modal piano synthesizer — port of `instruments/piano/synth.py::Piano`.
//!
//! Sound model per note: N inharmonic partials with two-stage exponential
//! decay, unison beating/detune, velocity interpolation between calibrated
//! layers, filtered-noise attack thump + resonance bed, damper release, and
//! global sympathetic lines. The only data used is the parameter table.

use crate::filters::{butter_bandpass4, sosfilt, Sos};
use crate::interp::{note_params, NoteParams, N_BANDS};
use crate::params::Table;
use crate::rng::Rng;
use crate::stft::BandMetric;
use std::f64::consts::{LN_2, PI};

const THUMP_TAU: f64 = 0.02; // s, attack-noise decay

pub fn band_edges() -> [f64; N_BANDS + 1] {
    // np.geomspace(40, 8000, 11)
    let mut e = [0.0; N_BANDS + 1];
    for (i, v) in e.iter_mut().enumerate() {
        *v = 40.0 * 200f64.powf(i as f64 / 10.0);
    }
    e
}

pub struct Piano {
    pub table: Table,
    pub sr: usize,
    rng: Rng,
    band_sos: Vec<Sos>,
    cal_bed: Vec<f64>,
    cal_thump: Vec<f64>,
}

impl Piano {
    pub fn from_file(path: &str, sr: usize, seed: u64) -> Result<Self, String> {
        let json = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        Ok(Self::new(Table::from_json(&json)?, sr, seed))
    }

    pub fn new(table: Table, sr: usize, seed: u64) -> Self {
        let edges = band_edges();
        let srf = sr as f64;
        // per-band bandpass filters + empirical level calibration so that
        // synthesized noise reproduces measured bed/thump dB exactly under
        // the same measurement code (see stft.rs)
        let metric = BandMetric::new(sr);
        let mut probe_rng = Rng::new(99);
        let probe: Vec<f64> = (0..sr).map(|_| probe_rng.standard_normal()).collect();
        let thump_env: Vec<f64> = (0..sr)
            .map(|i| (-(i as f64) / (THUMP_TAU * srf)).exp())
            .collect();

        let mut band_sos = Vec::with_capacity(N_BANDS);
        let mut cal_bed = Vec::with_capacity(N_BANDS);
        let mut cal_thump = Vec::with_capacity(N_BANDS);
        for i in 0..N_BANDS {
            let (lo, hi) = (edges[i], edges[i + 1].min(srf / 2.0 * 0.98));
            let sos = butter_bandpass4(lo, hi, srf);
            let mut nb = probe.clone();
            sosfilt(&sos, &mut nb);
            let (steady_db, _) = metric.band_metric(&nb, edges[i], edges[i + 1]);
            let nb_thump: Vec<f64> = nb.iter().zip(&thump_env).map(|(a, b)| a * b).collect();
            let (_, attack_db) = metric.band_metric(&nb_thump, edges[i], edges[i + 1]);
            band_sos.push(sos);
            cal_bed.push(steady_db);
            cal_thump.push(attack_db);
        }

        Piano {
            table,
            sr,
            rng: Rng::new(seed),
            band_sos,
            cal_bed,
            cal_thump,
        }
    }

    pub fn note_params(&self, midi: i32, velocity: f64) -> NoteParams {
        note_params(&self.table, midi, velocity)
    }

    /// Render one note. `dur` = total render length in seconds;
    /// `release_at` = key release time (None = hold to the end).
    pub fn synth_note(
        &mut self,
        midi: i32,
        velocity: f64,
        dur: f64,
        release_at: Option<f64>,
        sustain_pedal: bool,
    ) -> Vec<f64> {
        let srf = self.sr as f64;
        let p = self.note_params(midi, velocity);
        let n_samp = (dur * srf) as usize;
        let mut out = vec![0.0f64; n_samp];

        // number of unison strings (approx: 1 below ~B1, 2 to ~E2, else 3)
        let n_strings: usize = if midi < 33 {
            1
        } else if midi < 41 {
            2
        } else {
            3
        };
        // unison detunings in cents per string (measured pianos: ~0.5-2 c in
        // the midrange, growing to 10-30 c total spread in the top octave)
        let det_base: &[f64] = match n_strings {
            1 => &[0.0],
            2 => &[-0.55, 0.55],
            _ => &[-0.9, 0.12, 1.0],
        };
        let det_scale = 1.0 + (midi - 76).max(0) as f64 * 0.7;
        let dets: Vec<f64> = det_base.iter().map(|d| d * det_scale).collect();

        let nyq = srf * 0.5 * 0.95;
        let mut env = vec![0.0f64; n_samp];
        for prt in &p.partials {
            let n = prt.n as f64;
            let fnn = n * p.f0 * (1.0 + p.b * n * n).sqrt();
            if fnn >= nyq {
                continue;
            }
            let (a1, a2) = (prt.a1, prt.a2);
            if a1 + a2 <= 0.0 {
                continue;
            }
            let t1 = prt.t1.max(1e-3);
            let t2 = prt.t2.max(1e-3);
            for (i, e) in env.iter_mut().enumerate() {
                let t = i as f64 / srf;
                *e = a1 * (-t / t1).exp() + a2 * (-t / t2).exp();
            }

            if midi < 76 && n_strings > 1 {
                // The measured envelope already contains the unison strings'
                // decoherence — level-preserving multiplicative beating
                // (mean gain = 1) instead of splitting the envelope.
                let span_c = (dets[dets.len() - 1] - dets[0]) * (1.0 + 0.02 * n);
                let dfreq = fnn * span_c * LN_2 / 1200.0;
                let m = if n_strings == 3 { 0.35 } else { 0.3 };
                let ph1 = self.rng.uniform(0.0, 2.0 * PI);
                let ph2 = if n_strings == 3 {
                    Some(self.rng.uniform(0.0, 2.0 * PI))
                } else {
                    None
                };
                let phase = self.rng.uniform(-0.25, 0.25);
                for i in 0..n_samp {
                    let t = i as f64 / srf;
                    let mut beat = 1.0 + m * (2.0 * PI * dfreq * t + ph1).cos();
                    if let Some(p2) = ph2 {
                        beat += 0.18 * (2.0 * PI * dfreq * 0.55 * t + p2).cos();
                    }
                    out[i] += env[i] * beat * (2.0 * PI * fnn * t + phase).sin();
                }
            } else {
                // top octave: splits are tens of cents — genuinely resolved
                // spectral lines, so render the detuned strings explicitly
                let mut wts: Vec<f64> = dets
                    .iter()
                    .map(|_| 1.0 + self.rng.uniform(-0.35, 0.35))
                    .collect();
                let wsum: f64 = wts.iter().sum();
                for w in wts.iter_mut() {
                    *w /= wsum;
                }
                for (d, wt) in dets.iter().zip(&wts) {
                    let jit = self.rng.uniform(0.7, 1.3);
                    let f = fnn * 2f64.powf(d * jit * (1.0 + 0.02 * n) / 1200.0);
                    let phase = self.rng.uniform(-0.25, 0.25);
                    for i in 0..n_samp {
                        let t = i as f64 / srf;
                        out[i] += env[i] * wt * (2.0 * PI * f * t + phase).sin();
                    }
                }
            }
        }

        // --- broadband components: attack thump + sympathetic resonance bed
        for i in 0..N_BANDS {
            let g_thump = p.thump_db[i];
            let g_bed = p.bed_db[i];
            if g_thump < -100.0 && g_bed < -100.0 {
                continue;
            }
            let mut nb: Vec<f64> = (0..n_samp).map(|_| self.rng.standard_normal()).collect();
            sosfilt(&self.band_sos[i], &mut nb);
            let (bed_gain, t60) = if g_bed > -100.0 {
                let t60 = p.bed_t60[i].max(0.3);
                // measured level is anchored mid-way through the analysis
                // window, not at t=0: add back 60 dB/t60 * anchor (cap 20 dB)
                let comp_db = (60.0 * p.bed_anchor_s / t60).min(20.0);
                (
                    10f64.powf((g_bed - self.cal_bed[i] + comp_db) / 20.0),
                    t60,
                )
            } else {
                (0.0, 1.0)
            };
            let thump_gain = if g_thump > -100.0 {
                10f64.powf((g_thump - self.cal_thump[i]) / 20.0)
            } else {
                0.0
            };
            for s in 0..n_samp {
                let t = s as f64 / srf;
                let mut comp = 0.0;
                if bed_gain > 0.0 {
                    comp += bed_gain * 10f64.powf(-3.0 * t / t60);
                }
                if thump_gain > 0.0 {
                    comp += thump_gain * (-t / THUMP_TAU).exp();
                }
                out[s] += nb[s] * comp;
            }
        }

        // --- release / damper (keys above ~F#6 have no dampers)
        if let Some(rel) = release_at {
            if rel < dur && !sustain_pedal && midi < 89 {
                let r0 = (rel * srf) as usize;
                let fade_t = if midi < 60 { 0.12 } else { 0.06 };
                for (k, v) in out[r0.min(n_samp)..].iter_mut().enumerate() {
                    let fade = (-(k as f64) / (fade_t * srf)).exp();
                    // dampers kill string modes but a soft body/bed remnant rings on
                    let remnant = 0.02 * (-(k as f64) / srf).exp();
                    *v *= fade.max(remnant);
                }
            }
        }

        // --- sympathetic / body resonance lines (not damped by this key)
        let anchor = self.table.symp_anchor_s;
        if let Some(lines) = self.table.symp_lines.clone() {
            let n_lines = lines.len().min(p.symp_db.len());
            for (j, ln) in lines[..n_lines].iter().enumerate() {
                let db = p.symp_db[j];
                if db <= -130.0 {
                    continue;
                }
                let t60 = ln.t60.max(0.5);
                // measured at `anchor` seconds; extrapolate to t=0 (cap +15 dB)
                let a0 = 10f64.powf((db + (60.0 * anchor / t60).min(15.0)) / 20.0);
                let phase = self.rng.uniform(0.0, 2.0 * PI);
                for (i, v) in out.iter_mut().enumerate() {
                    let t = i as f64 / srf;
                    let ramp = (t / 0.03).min(1.0);
                    let e = a0 * 10f64.powf(-3.0 * t / t60);
                    *v += ramp * e * (2.0 * PI * ln.freq * t + phase).sin();
                }
            }
        }

        out
    }

    pub fn synth_chord(
        &mut self,
        notes: &[(i32, f64)],
        dur: f64,
        release_at: Option<f64>,
        sustain_pedal: bool,
    ) -> Vec<f64> {
        let mut out: Option<Vec<f64>> = None;
        for (midi, vel) in notes {
            let y = self.synth_note(*midi, *vel, dur, release_at, sustain_pedal);
            match &mut out {
                None => out = Some(y),
                Some(acc) => {
                    for (a, b) in acc.iter_mut().zip(&y) {
                        *a += b;
                    }
                }
            }
        }
        out.unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn band_edges_match_geomspace() {
        let e = band_edges();
        assert!((e[0] - 40.0).abs() < 1e-9);
        assert!((e[10] - 8000.0).abs() < 1e-9);
        assert!((e[5] - 40.0 * 200f64.powf(0.5)).abs() < 1e-6);
    }
}
