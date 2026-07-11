//! Streaming voice with recursive resonators.
//!
//! Same sound model as synth.py, but every per-sample transcendental is
//! replaced by a recurrence:
//!   sin/cos(ωt+φ)      -> complex rotator (4 mul/2 add per sample)
//!   a·e^{-t/τ}         -> state × per-sample decay factor
//!   10^{-3t/t60}       -> same (decay factor e^{-3·ln10/(sr·t60)})
//!   ramp min(t/r, 1)   -> incremental add + clamp
//! Rotator magnitude drift is ~n·ε ≈ 4e-11 over 8 s at 48 kHz — inaudible,
//! and voices die by envelope decay long before drift matters.
//!
//! Quality: partials are sorted by A-weighted energy salience at note-on and
//! truncated to `Quality::max_partials`. The parameter table is unchanged —
//! pruning is a runtime decision, so calibration never needs to re-run.

use crate::filters::Sos;
use crate::interp::{NoteParams, N_BANDS};
use crate::params::SympLine;
use crate::rng::Rng;
use std::f64::consts::{LN_10, LN_2, PI};

pub const THUMP_TAU: f64 = 0.02; // s, attack-noise decay

#[derive(Clone, Copy, Debug)]
pub struct Quality {
    /// Partials kept per voice (most salient first). usize::MAX = all.
    pub max_partials: usize,
    /// Render the broadband components (attack thump + resonance bed).
    pub noise: bool,
    /// Sympathetic/body resonance lines kept. usize::MAX = all.
    pub max_symp_lines: usize,
}

impl Quality {
    pub const FULL: Quality = Quality {
        max_partials: usize::MAX,
        noise: true,
        max_symp_lines: usize::MAX,
    };
}

impl Default for Quality {
    fn default() -> Self {
        Quality::FULL
    }
}

/// A-weighting amplitude gain (linear, not dB) — salience proxy weight.
fn a_weight(f: f64) -> f64 {
    let f2 = f * f;
    let r = (12194.0f64.powi(2) * f2 * f2)
        / ((f2 + 20.6f64.powi(2))
            * ((f2 + 107.7f64.powi(2)) * (f2 + 737.9f64.powi(2))).sqrt()
            * (f2 + 12194.0f64.powi(2)));
    r / 0.7943 // normalized so 1 kHz ~ 1 (matches the 2.0 dB A-weight offset)
}

// ---------------------------------------------------------------- recurrences

struct Rotator {
    re: f64,
    im: f64,
    cr: f64,
    ci: f64,
}

impl Rotator {
    /// amp·e^{i(ωn+φ)}: value at n=0 is amp·(cos φ, sin φ).
    fn new(omega: f64, phase: f64, amp: f64) -> Self {
        Rotator {
            re: amp * phase.cos(),
            im: amp * phase.sin(),
            cr: omega.cos(),
            ci: omega.sin(),
        }
    }

    /// Current imaginary part (amp·sin), then advance one sample.
    #[inline(always)]
    fn step_sin(&mut self) -> f64 {
        let s = self.im;
        let re = self.re * self.cr - self.im * self.ci;
        self.im = self.re * self.ci + self.im * self.cr;
        self.re = re;
        s
    }

    /// Current real part (amp·cos), then advance one sample.
    #[inline(always)]
    fn step_cos(&mut self) -> f64 {
        let c = self.re;
        let re = self.re * self.cr - self.im * self.ci;
        self.im = self.re * self.ci + self.im * self.cr;
        self.re = re;
        c
    }
}

/// a1·e^{-t/t1} + a2·e^{-t/t2} as two decaying states.
struct Decay2 {
    e1: f64,
    d1: f64,
    e2: f64,
    d2: f64,
}

impl Decay2 {
    fn new(a1: f64, t1: f64, a2: f64, t2: f64, sr: f64) -> Self {
        Decay2 {
            e1: a1,
            d1: (-1.0 / (sr * t1)).exp(),
            e2: a2,
            d2: (-1.0 / (sr * t2)).exp(),
        }
    }

    #[inline(always)]
    fn step(&mut self) -> f64 {
        let v = self.e1 + self.e2;
        self.e1 *= self.d1;
        self.e2 *= self.d2;
        v
    }

    fn level(&self) -> f64 {
        self.e1 + self.e2
    }
}

// ------------------------------------------------------------------ partials

enum PartialKind {
    /// midi < 76 with >1 string: level-preserving multiplicative beating.
    Beat {
        osc: Rotator,
        beat_a: Rotator,          // amp = m
        beat_b: Option<Rotator>,  // amp = 0.18 (3-string keys)
    },
    /// Explicitly rendered detuned strings (top octave / single string);
    /// per-string weight folded into the rotator amplitude.
    Strings { oscs: Vec<Rotator> },
}

struct PartialState {
    env: Decay2,
    kind: PartialKind,
}

struct NoiseBand {
    sos: [[f64; 5]; 4],
    state: [[f64; 2]; 4],
    bed_gain: f64,
    bed_env: f64,
    bed_decay: f64,
    thump_gain: f64,
    thump_env: f64,
    thump_decay: f64,
}

struct SympOsc {
    osc: Rotator, // amp 1
    env: f64,     // starts at a0
    decay: f64,
    ramp: f64,
    ramp_inc: f64,
}

/// Damper fade: gain = max(fade, remnant), both exponential states.
struct Release {
    fade: f64,
    fade_d: f64,
    rem: f64,
    rem_d: f64,
}

pub struct Voice {
    pub midi: i32,
    pub key_down: bool,
    releasable: bool, // keys above MIDI 88 have no dampers
    partials: Vec<PartialState>,
    noise: Vec<NoiseBand>,
    symp: Vec<SympOsc>,
    release: Option<Release>,
    scratch: Vec<f64>,
    last_level: f64,
    sr: f64,
}

impl Voice {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        p: &NoteParams,
        midi: i32,
        sr: f64,
        q: Quality,
        symp_lines: &[SympLine],
        symp_anchor: f64,
        band_sos: &[Sos],
        cal_bed: &[f64],
        cal_thump: &[f64],
        rng: &mut Rng,
    ) -> Voice {
        // number of unison strings (approx: 1 below ~B1, 2 to ~E2, else 3)
        let n_strings: usize = if midi < 33 {
            1
        } else if midi < 41 {
            2
        } else {
            3
        };
        let det_base: &[f64] = match n_strings {
            1 => &[0.0],
            2 => &[-0.55, 0.55],
            _ => &[-0.9, 0.12, 1.0],
        };
        let det_scale = 1.0 + (midi - 76).max(0) as f64 * 0.7;
        let dets: Vec<f64> = det_base.iter().map(|d| d * det_scale).collect();
        let nyq = sr * 0.5 * 0.95;

        // candidate partials with A-weighted energy salience
        let mut cand: Vec<(usize, f64, f64)> = Vec::with_capacity(p.partials.len()); // (idx, fn, salience)
        for (i, prt) in p.partials.iter().enumerate() {
            let n = prt.n as f64;
            let fnn = n * p.f0 * (1.0 + p.b * n * n).sqrt();
            if fnn >= nyq || prt.a1 + prt.a2 <= 0.0 {
                continue;
            }
            let t1 = prt.t1.max(1e-3);
            let t2 = prt.t2.max(1e-3);
            // ∫env² ≈ a1²t1/2 + a2²t2/2 + 2a1a2/(1/t1+1/t2), A-weighted
            let cross = 2.0 * prt.a1 * prt.a2 / (1.0 / t1 + 1.0 / t2);
            let energy = 0.5 * (prt.a1 * prt.a1 * t1 + prt.a2 * prt.a2 * t2) + cross;
            let w = a_weight(fnn);
            cand.push((i, fnn, energy * w * w));
        }
        cand.sort_by(|a, b| b.2.partial_cmp(&a.2).unwrap());
        cand.truncate(q.max_partials);

        let mut partials = Vec::with_capacity(cand.len());
        for (i, fnn, _) in &cand {
            let prt = &p.partials[*i];
            let n = prt.n as f64;
            let env = Decay2::new(prt.a1, prt.t1.max(1e-3), prt.a2, prt.t2.max(1e-3), sr);
            let kind = if midi < 76 && n_strings > 1 {
                let span_c = (dets[dets.len() - 1] - dets[0]) * (1.0 + 0.02 * n);
                let dfreq = fnn * span_c * LN_2 / 1200.0;
                let m = if n_strings == 3 { 0.35 } else { 0.3 };
                let beat_a = Rotator::new(2.0 * PI * dfreq / sr, rng.uniform(0.0, 2.0 * PI), m);
                let beat_b = if n_strings == 3 {
                    Some(Rotator::new(
                        2.0 * PI * dfreq * 0.55 / sr,
                        rng.uniform(0.0, 2.0 * PI),
                        0.18,
                    ))
                } else {
                    None
                };
                let phase = rng.uniform(-0.25, 0.25);
                PartialKind::Beat {
                    osc: Rotator::new(2.0 * PI * fnn / sr, phase, 1.0),
                    beat_a,
                    beat_b,
                }
            } else {
                let mut wts: Vec<f64> = dets
                    .iter()
                    .map(|_| 1.0 + rng.uniform(-0.35, 0.35))
                    .collect();
                let wsum: f64 = wts.iter().sum();
                for w in wts.iter_mut() {
                    *w /= wsum;
                }
                let oscs = dets
                    .iter()
                    .zip(&wts)
                    .map(|(d, wt)| {
                        let jit = rng.uniform(0.7, 1.3);
                        let f = fnn * 2f64.powf(d * jit * (1.0 + 0.02 * n) / 1200.0);
                        let phase = rng.uniform(-0.25, 0.25);
                        Rotator::new(2.0 * PI * f / sr, phase, *wt)
                    })
                    .collect();
                PartialKind::Strings { oscs }
            };
            partials.push(PartialState { env, kind });
        }

        // broadband components: attack thump + sympathetic resonance bed
        let mut noise = Vec::new();
        if q.noise {
            for i in 0..N_BANDS {
                let g_thump = p.thump_db[i];
                let g_bed = p.bed_db[i];
                if g_thump < -100.0 && g_bed < -100.0 {
                    continue;
                }
                let (bed_gain, bed_decay) = if g_bed > -100.0 {
                    let t60 = p.bed_t60[i].max(0.3);
                    let comp_db = (60.0 * p.bed_anchor_s / t60).min(20.0);
                    (
                        10f64.powf((g_bed - cal_bed[i] + comp_db) / 20.0),
                        (-3.0 * LN_10 / (sr * t60)).exp(),
                    )
                } else {
                    (0.0, 1.0)
                };
                let thump_gain = if g_thump > -100.0 {
                    10f64.powf((g_thump - cal_thump[i]) / 20.0)
                } else {
                    0.0
                };
                let mut sos = [[0.0; 5]; 4];
                sos.copy_from_slice(&band_sos[i][..4]);
                noise.push(NoiseBand {
                    sos,
                    state: [[0.0; 2]; 4],
                    bed_gain,
                    bed_env: 1.0,
                    bed_decay,
                    thump_gain,
                    thump_env: 1.0,
                    thump_decay: (-1.0 / (sr * THUMP_TAU)).exp(),
                });
            }
        }

        // sympathetic / body resonance lines (not damped by this key);
        // loudest lines first so max_symp_lines truncates gracefully
        let n_lines = symp_lines.len().min(p.symp_db.len());
        let mut symp_cand: Vec<(f64, f64, f64)> = Vec::with_capacity(n_lines); // (a0, t60, freq)
        for (j, ln) in symp_lines[..n_lines].iter().enumerate() {
            let db = p.symp_db[j];
            if db <= -130.0 {
                continue;
            }
            let t60 = ln.t60.max(0.5);
            let a0 = 10f64.powf((db + (60.0 * symp_anchor / t60).min(15.0)) / 20.0);
            symp_cand.push((a0, t60, ln.freq));
        }
        symp_cand.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap());
        symp_cand.truncate(q.max_symp_lines);
        let symp = symp_cand
            .iter()
            .map(|(a0, t60, freq)| SympOsc {
                osc: Rotator::new(2.0 * PI * freq / sr, rng.uniform(0.0, 2.0 * PI), 1.0),
                env: *a0,
                decay: (-3.0 * LN_10 / (sr * t60)).exp(),
                ramp: 0.0,
                ramp_inc: 1.0 / (0.03 * sr),
            })
            .collect();

        Voice {
            midi,
            key_down: true,
            releasable: midi < 89,
            partials,
            noise,
            symp,
            release: None,
            scratch: Vec::new(),
            last_level: f64::MAX,
            sr,
        }
    }

    /// Start the damper fade (no-op for undamped keys).
    pub fn trigger_release(&mut self) {
        if !self.releasable || self.release.is_some() {
            return;
        }
        let fade_t = if self.midi < 60 { 0.12 } else { 0.06 };
        self.release = Some(Release {
            fade: 1.0,
            fade_d: (-1.0 / (fade_t * self.sr)).exp(),
            rem: 0.02,
            rem_d: (-1.0 / self.sr).exp(),
        });
    }

    pub fn is_finished(&self) -> bool {
        self.last_level < 1e-7
    }

    /// Render `out.len()` samples, ADDING into `out` (mix bus).
    pub fn render_add(&mut self, out: &mut [f64], rng: &mut Rng) {
        let n = out.len();
        if n == 0 {
            return;
        }
        // cull components that have decayed below audibility (~-140 dBFS);
        // envelopes only decay, so they never come back. CPU cost of a
        // ringing voice shrinks as it fades.
        const FLOOR: f64 = 1e-7;
        self.partials.retain(|p| p.env.level() > FLOOR);
        self.noise
            .retain(|nb| nb.bed_gain * nb.bed_env + nb.thump_gain * nb.thump_env > FLOOR);
        self.symp.retain(|so| so.env > FLOOR);

        self.scratch.clear();
        self.scratch.resize(n, 0.0);
        let scratch = &mut self.scratch;

        // partials
        for ps in &mut self.partials {
            match &mut ps.kind {
                PartialKind::Beat {
                    osc,
                    beat_a,
                    beat_b,
                } => {
                    if let Some(bb) = beat_b {
                        for s in scratch.iter_mut() {
                            let beat = 1.0 + beat_a.step_cos() + bb.step_cos();
                            *s += ps.env.step() * beat * osc.step_sin();
                        }
                    } else {
                        for s in scratch.iter_mut() {
                            let beat = 1.0 + beat_a.step_cos();
                            *s += ps.env.step() * beat * osc.step_sin();
                        }
                    }
                }
                PartialKind::Strings { oscs } => {
                    for s in scratch.iter_mut() {
                        let mut acc = 0.0;
                        for o in oscs.iter_mut() {
                            acc += o.step_sin();
                        }
                        *s += ps.env.step() * acc;
                    }
                }
            }
        }

        // broadband noise
        for nb in &mut self.noise {
            for s in scratch.iter_mut() {
                let mut x = rng.standard_normal();
                for (sec, st) in nb.sos.iter().zip(nb.state.iter_mut()) {
                    let y = sec[0] * x + st[0];
                    st[0] = sec[1] * x - sec[3] * y + st[1];
                    st[1] = sec[2] * x - sec[4] * y;
                    x = y;
                }
                let comp = nb.bed_gain * nb.bed_env + nb.thump_gain * nb.thump_env;
                nb.bed_env *= nb.bed_decay;
                nb.thump_env *= nb.thump_decay;
                *s += x * comp;
            }
        }

        // damper fade applies to strings + noise, not to sympathetic lines
        if let Some(r) = &mut self.release {
            for s in scratch.iter_mut() {
                *s *= r.fade.max(r.rem);
                r.fade *= r.fade_d;
                r.rem *= r.rem_d;
            }
        }

        // sympathetic lines
        for so in &mut self.symp {
            for s in scratch.iter_mut() {
                let ramp = so.ramp.min(1.0);
                so.ramp += so.ramp_inc;
                *s += ramp * so.env * so.osc.step_sin();
                so.env *= so.decay;
            }
        }

        for (o, s) in out.iter_mut().zip(scratch.iter()) {
            *o += s;
        }

        // level estimate for voice culling
        let gain = self
            .release
            .as_ref()
            .map(|r| r.fade.max(r.rem))
            .unwrap_or(1.0);
        let mut level = 0.0;
        for ps in &self.partials {
            level += ps.env.level();
        }
        for nb in &self.noise {
            level += nb.bed_gain * nb.bed_env + nb.thump_gain * nb.thump_env;
        }
        let mut symp_level = 0.0;
        for so in &self.symp {
            symp_level += so.env;
        }
        self.last_level = level * gain + symp_level;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::interp::PState;

    fn one_partial_params(f0: f64, a1: f64, t1: f64) -> NoteParams {
        NoteParams {
            f0,
            b: 0.0,
            partials: vec![PState {
                n: 1,
                a1,
                t1,
                a2: 0.0,
                t2: 1.0,
            }],
            thump_db: vec![-120.0; N_BANDS],
            bed_db: vec![-120.0; N_BANDS],
            bed_t60: vec![10.0; N_BANDS],
            bed_anchor_s: 1.5,
            symp_db: vec![],
        }
    }

    /// Recursive render must match the closed-form model (beat branch, m60):
    /// env(t)·(1 + m·cos(2πdf t+φ1) + 0.18·cos(2π·0.55df t+φ2))·sin(2πf t+φ3)
    #[test]
    fn recurrence_matches_closed_form() {
        let sr = 48000.0;
        let p = one_partial_params(261.5, 0.8, 0.9);
        let mut rng = Rng::new(42);
        let mut v = Voice::new(
            &p,
            60,
            sr,
            Quality::FULL,
            &[],
            1.2,
            &vec![vec![[0.0; 5]; 4]; N_BANDS],
            &[0.0; N_BANDS],
            &[0.0; N_BANDS],
            &mut rng,
        );
        let mut out = vec![0.0f64; 48000];
        let mut noise_rng = Rng::new(1);
        v.render_add(&mut out, &mut noise_rng);

        // replicate the phase draws (same seed, same order)
        let mut r2 = Rng::new(42);
        let ph1 = r2.uniform(0.0, 2.0 * PI);
        let ph2 = r2.uniform(0.0, 2.0 * PI);
        let ph3 = r2.uniform(-0.25, 0.25);
        let (f, dfl) = {
            let fnn = 261.5;
            let span_c = (1.0 - (-0.9)) * (1.0 + 0.02);
            (fnn, fnn * span_c * LN_2 / 1200.0)
        };
        let mut max_err = 0.0f64;
        for i in (0..48000).step_by(997) {
            let t = i as f64 / sr;
            let env = 0.8 * (-t / 0.9).exp();
            let beat = 1.0
                + 0.35 * (2.0 * PI * dfl * t + ph1).cos()
                + 0.18 * (2.0 * PI * dfl * 0.55 * t + ph2).cos();
            let want = env * beat * (2.0 * PI * f * t + ph3).sin();
            max_err = max_err.max((out[i] - want).abs());
        }
        assert!(max_err < 1e-9, "max err {max_err:e}");
    }

    /// Buffered streaming must equal one-shot rendering exactly
    /// (noise disabled so RNG draw order is identical).
    #[test]
    fn streaming_equals_oneshot() {
        let sr = 48000.0;
        let mut p = one_partial_params(440.0, 0.5, 0.5);
        p.partials.push(PState {
            n: 2,
            a1: 0.2,
            t1: 0.4,
            a2: 0.01,
            t2: 1.5,
        });
        let q = Quality {
            noise: false,
            ..Quality::FULL
        };
        let sos = vec![vec![[0.0; 5]; 4]; N_BANDS];
        let mk = |rng: &mut Rng| {
            Voice::new(&p, 69, sr, q, &[], 1.2, &sos, &[0.0; N_BANDS], &[0.0; N_BANDS], rng)
        };
        let mut rng1 = Rng::new(7);
        let mut v1 = mk(&mut rng1);
        let mut one = vec![0.0f64; 4800];
        let mut nr1 = Rng::new(1);
        v1.render_add(&mut one, &mut nr1);

        let mut rng2 = Rng::new(7);
        let mut v2 = mk(&mut rng2);
        let mut buffered = vec![0.0f64; 4800];
        let mut nr2 = Rng::new(1);
        for chunk in buffered.chunks_mut(256) {
            v2.render_add(chunk, &mut nr2);
        }
        for (a, b) in one.iter().zip(&buffered) {
            assert_eq!(a, b);
        }
    }

    #[test]
    fn quality_truncates_partials() {
        let sr = 48000.0;
        let mut p = one_partial_params(220.0, 0.5, 0.5);
        for n in 2..=20 {
            p.partials.push(PState {
                n,
                a1: 0.5 / n as f64,
                t1: 0.5,
                a2: 0.0,
                t2: 1.0,
            });
        }
        let sos = vec![vec![[0.0; 5]; 4]; N_BANDS];
        let q = Quality {
            max_partials: 5,
            noise: false,
            max_symp_lines: 0,
        };
        let mut rng = Rng::new(3);
        let v = Voice::new(&p, 57, sr, q, &[], 1.2, &sos, &[0.0; N_BANDS], &[0.0; N_BANDS], &mut rng);
        assert_eq!(v.partials.len(), 5);
    }
}
