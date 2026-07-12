//! Engine family 2: sustained stochastic harmonic bank.
//!
//! Continuous-excitation instruments (bowed string sections first): a
//! bank of harmonic oscillators with slow stochastic FM (ensemble
//! detune) and AM, a shared vibrato LFO, per-band steady bow noise, and
//! a sustain envelope (smoothstep rise -> undulating sustain -> two-
//! stage release on note-off). Executable reference: `lab/sustained.py`
//! — deterministic paths (note params, calibration) match it to float
//! precision; stochastic renders are compared statistically (different
//! PRNG), like every other engine port.
//!
//! Modulators update every `MOD_HOP` samples and are linearly
//! interpolated between nodes, exactly like the Python reference's
//! `_lp_noise`; one-pole noise is scaled by the analytic stationary
//! gain sqrt((1-a)/(1+a)) (never the realized std — a streaming engine
//! cannot know it).

use crate::filters::Sos;
use crate::params::{Layer, Table};
use crate::rng::Rng;
use crate::voice::{a_weight, Quality};

pub const N_BANDS_SUS: usize = 12;
pub const NOISE_WIN_S: f64 = 0.2;
pub const NOISE_HOP_S: f64 = 0.05;
pub const MOD_HOP: usize = 64;

const LN2_1200: f64 = core::f64::consts::LN_2 / 1200.0;
const NOISE_FLOOR: f64 = -150.0;

pub fn sus_band_edges() -> [f64; N_BANDS_SUS + 1] {
    // np.geomspace(40, 16000, 13)
    let mut e = [0.0; N_BANDS_SUS + 1];
    for (i, v) in e.iter_mut().enumerate() {
        *v = 40.0 * 400f64.powf(i as f64 / 12.0);
    }
    e
}

#[derive(Clone, Copy)]
pub struct SusConfig {
    pub drift_cents: f64,
    pub drift_hz: f64,
    pub vib_cents: f64,
    pub harm_am_db: f64,
}

impl SusConfig {
    pub fn from_table(t: &Table) -> Self {
        let c = t.config.as_ref();
        SusConfig {
            drift_cents: c.and_then(|c| c.drift_cents).unwrap_or(6.0),
            drift_hz: c.and_then(|c| c.drift_hz).unwrap_or(1.0),
            vib_cents: c.and_then(|c| c.vib_cents).unwrap_or(7.0),
            harm_am_db: c.and_then(|c| c.harm_am_db).unwrap_or(1.0),
        }
    }
}

#[derive(Clone)]
pub struct SusParams {
    pub f0: f64,
    pub harm: Vec<(i64, f64)>,
    pub noise_db: Vec<f64>,
    pub rise_s: f64,
    pub und_db: f64,
    pub und_hz: f64,
    pub vib_hz: f64,
    pub vib_am_db: f64,
    pub rel_s: f64,
    pub rel_remnant: f64,
    pub rel_tail_s: f64,
}

// ------------------------------------------------------- interpolation
// Mirrors lab/sustained.py note_params to float precision.

struct LState {
    harm: Vec<(i64, f64)>,
    noise_db: Vec<f64>,
    scalars: [f64; 8], // rise, und_db, und_hz, vib_hz, vib_am_db, rel_s, rel_rem, rel_tail
}

fn layer_state(l: &Layer) -> LState {
    let harm = l
        .harm
        .as_ref()
        .map(|hs| hs.iter().map(|h| (h.n, h.a)).collect())
        .unwrap_or_default();
    let noise_db = l
        .noise_db
        .as_ref()
        .map(|v| v.iter().map(|x| x.unwrap_or(NOISE_FLOOR)).collect())
        .unwrap_or_else(|| vec![NOISE_FLOOR; N_BANDS_SUS]);
    LState {
        harm,
        noise_db,
        scalars: [
            l.rise_s.unwrap_or(0.3),
            l.und_db.unwrap_or(1.0),
            l.und_hz.unwrap_or(0.5),
            l.vib_hz.unwrap_or(5.0),
            l.vib_am_db.unwrap_or(0.5),
            l.rel_s.unwrap_or(0.3),
            l.rel_remnant.unwrap_or(0.0),
            l.rel_tail_s.unwrap_or(1.0),
        ],
    }
}

fn merge_harm(lo: &[(i64, f64)], hi: &[(i64, f64)], w: f64) -> Vec<(i64, f64)> {
    use std::collections::BTreeMap;
    let lo_m: BTreeMap<i64, f64> = lo.iter().copied().collect();
    let hi_m: BTreeMap<i64, f64> = hi.iter().copied().collect();
    let mut ns: Vec<i64> = lo_m.keys().chain(hi_m.keys()).copied().collect();
    ns.sort_unstable();
    ns.dedup();
    ns.iter()
        .map(|n| {
            let a = *lo_m
                .get(n)
                .unwrap_or(&(hi_m.get(n).copied().unwrap_or(0.0) * 1e-4));
            let b = *hi_m
                .get(n)
                .unwrap_or(&(lo_m.get(n).copied().unwrap_or(0.0) * 1e-4));
            let la = a.max(1e-12).ln();
            let lb = b.max(1e-12).ln();
            (*n, (la + (lb - la) * w).exp())
        })
        .collect()
}

fn merge_states(lo: &LState, hi: &LState, w: f64) -> LState {
    let mut scalars = [0.0; 8];
    for i in 0..8 {
        scalars[i] = lo.scalars[i] + (hi.scalars[i] - lo.scalars[i]) * w;
    }
    LState {
        harm: merge_harm(&lo.harm, &hi.harm, w),
        noise_db: lo
            .noise_db
            .iter()
            .zip(&hi.noise_db)
            .map(|(a, b)| a + (b - a) * w)
            .collect(),
        scalars,
    }
}

fn interp_layers(layers: &[Layer], velocity: f64) -> LState {
    let vs: Vec<f64> = layers.iter().map(|l| l.vel).collect();
    if velocity <= vs[0] {
        return layer_state(&layers[0]);
    }
    if velocity >= vs[vs.len() - 1] {
        return layer_state(&layers[layers.len() - 1]);
    }
    let j = vs.iter().position(|v| *v >= velocity).unwrap();
    if vs[j] == velocity {
        return layer_state(&layers[j]);
    }
    let i = j - 1;
    let w = (velocity - vs[i]) / (vs[j] - vs[i]);
    merge_states(&layer_state(&layers[i]), &layer_state(&layers[j]), w)
}

fn midi_to_freq(m: f64) -> f64 {
    440.0 * 2f64.powf((m - 69.0) / 12.0)
}

fn params_from(f0: f64, s: LState) -> SusParams {
    SusParams {
        f0,
        harm: s.harm,
        noise_db: s.noise_db,
        rise_s: s.scalars[0],
        und_db: s.scalars[1],
        und_hz: s.scalars[2],
        vib_hz: s.scalars[3],
        vib_am_db: s.scalars[4],
        rel_s: s.scalars[5],
        rel_remnant: s.scalars[6],
        rel_tail_s: s.scalars[7],
    }
}

pub fn sus_note_params(table: &Table, midi: i32, velocity: f64) -> SusParams {
    let keys = &table.keys;
    let ms: Vec<i32> = keys.iter().map(|k| k.midi).collect();
    let (lo, hi, w) = if midi <= ms[0] {
        (0, 0, 0.0)
    } else if midi >= ms[ms.len() - 1] {
        (keys.len() - 1, keys.len() - 1, 0.0)
    } else {
        let hi = ms.iter().position(|m| *m >= midi).unwrap();
        if ms[hi] == midi {
            (hi, hi, 0.0)
        } else {
            let lo = hi - 1;
            let w = (midi - ms[lo]) as f64 / (ms[hi] - ms[lo]) as f64;
            (lo, hi, w)
        }
    };
    let slo = interp_layers(&keys[lo].layers, velocity);
    if lo == hi {
        let f0 = keys[lo].f0 * 2f64.powf((midi - keys[lo].midi) as f64 / 12.0);
        return params_from(f0, slo);
    }
    let shi = interp_layers(&keys[hi].layers, velocity);
    let dev_lo = 1200.0 * (keys[lo].f0 / midi_to_freq(keys[lo].midi as f64)).log2();
    let dev_hi = 1200.0 * (keys[hi].f0 / midi_to_freq(keys[hi].midi as f64)).log2();
    let dev = dev_lo + (dev_hi - dev_lo) * w;
    let f0 = midi_to_freq(midi as f64) * 2f64.powf(dev / 1200.0);
    params_from(f0, merge_states(&slo, &shi, w))
}

// ------------------------------------------------------------- voice

/// One-pole lowpassed noise node generator (block rate = MOD_HOP), scaled
/// by the analytic stationary gain. `next()` returns the next node.
struct LpNoise {
    alpha: f64,
    inv_gain: f64,
    acc: f64,
}

impl LpNoise {
    fn new(f_c: f64, sr: f64) -> Self {
        let alpha = (-2.0 * core::f64::consts::PI * f_c * MOD_HOP as f64 / sr).exp();
        let g = ((1.0 - alpha) / (1.0 + alpha)).sqrt();
        LpNoise {
            alpha,
            inv_gain: 1.0 / (g + 1e-12),
            acc: 0.0,
        }
    }

    fn next(&mut self, rng: &mut Rng) -> f64 {
        self.acc = self.alpha * self.acc + (1.0 - self.alpha) * rng.standard_normal();
        self.acc * self.inv_gain
    }
}

struct SusHarm {
    freq_hz: f64,
    amp: f64,
    phase: f64,
    drift: LpNoise,
    am: LpNoise,
    drift_node: (f64, f64), // (current, next)
    am_node: (f64, f64),
}

struct SusNoiseBand {
    sos: [[f64; 5]; 4],
    state: [[f64; 2]; 4],
    gain: f64,
}

pub struct SustainedVoice {
    pub midi: i32,
    pub key_down: bool,
    sr: f64,
    vib_phase: f64,
    vib_step: f64,
    vib_cents: f64,
    vib_am_db: f64,
    drift_cents: f64,
    am_span: f64, // 10^(harm_am_db/20) - 1
    und_db: f64,
    und: LpNoise,
    und_node: (f64, f64),
    rise_inv: f64, // 1/rise_samples
    t_samp: u64,
    block_pos: usize,
    harms: Vec<SusHarm>,
    noise: Vec<SusNoiseBand>,
    // release
    released: bool,
    rel_env1: f64,
    rel_env2: f64,
    rel_d1: f64,
    rel_d2: f64,
}

impl SustainedVoice {
    pub fn new(
        p: &SusParams,
        cfg: &SusConfig,
        midi: i32,
        sr: f64,
        q: Quality,
        band_sos: &[Sos],
        cal_bed: &[f64],
        rng: &mut Rng,
    ) -> Self {
        let nyq = sr * 0.5 * 0.95;
        // salience order (steady energy, A-weighted), prune to quality
        let mut cand: Vec<(i64, f64, f64)> = p
            .harm
            .iter()
            .filter(|(n, a)| {
                let f = *n as f64 * p.f0;
                f > 0.0 && f < nyq && *a > 0.0
            })
            .map(|(n, a)| {
                let f = *n as f64 * p.f0;
                let w = a_weight(f);
                (*n, *a, a * a * w * w)
            })
            .collect();
        cand.sort_by(|x, y| y.2.total_cmp(&x.2));
        cand.truncate(q.max_partials);

        let mut harms = Vec::with_capacity(cand.len());
        for (n, a, _) in &cand {
            let mut drift = LpNoise::new(cfg.drift_hz, sr);
            let mut am = LpNoise::new(p.und_hz.max(0.3), sr);
            let d0 = drift.next(rng);
            let d1 = drift.next(rng);
            let a0 = am.next(rng);
            let a1 = am.next(rng);
            harms.push(SusHarm {
                freq_hz: *n as f64 * p.f0,
                amp: *a,
                phase: rng.uniform(0.0, 2.0 * core::f64::consts::PI),
                drift,
                am,
                drift_node: (d0, d1),
                am_node: (a0, a1),
            });
        }

        let mut noise = Vec::new();
        if q.noise {
            for i in 0..N_BANDS_SUS {
                let g_db = p.noise_db[i];
                if g_db < -140.0 {
                    continue;
                }
                let mut sos = [[0.0; 5]; 4];
                sos.copy_from_slice(&band_sos[i][..4]);
                noise.push(SusNoiseBand {
                    sos,
                    state: [[0.0; 2]; 4],
                    gain: 10f64.powf((g_db - cal_bed[i]) / 20.0),
                });
            }
        }

        let mut und = LpNoise::new(p.und_hz.max(0.15), sr);
        let u0 = und.next(rng);
        let u1 = und.next(rng);

        SustainedVoice {
            midi,
            key_down: true,
            sr,
            vib_phase: rng.uniform(0.0, 2.0 * core::f64::consts::PI),
            vib_step: 2.0 * core::f64::consts::PI * p.vib_hz / sr,
            vib_cents: cfg.vib_cents,
            vib_am_db: p.vib_am_db,
            drift_cents: cfg.drift_cents,
            am_span: 10f64.powf(cfg.harm_am_db / 20.0) - 1.0,
            und_db: p.und_db,
            und,
            und_node: (u0, u1),
            rise_inv: 1.0 / (p.rise_s.max(0.02) * sr),
            t_samp: 0,
            block_pos: 0,
            harms,
            noise,
            released: false,
            rel_env1: 1.0,
            rel_env2: p.rel_remnant,
            rel_d1: (-1.0 / (p.rel_s.max(0.02) * sr)).exp(),
            rel_d2: (-1.0 / (p.rel_tail_s.max(0.05) * sr)).exp(),
        }
    }

    pub fn trigger_release(&mut self) {
        self.released = true;
    }

    pub fn is_finished(&self) -> bool {
        self.released && self.rel_env1.max(self.rel_env2) < 1e-7
    }

    pub fn render_add(&mut self, out: &mut [f64], rng: &mut Rng) {
        let hopf = MOD_HOP as f64;
        for o in out.iter_mut() {
            if self.block_pos == MOD_HOP {
                self.block_pos = 0;
                self.und_node = (self.und_node.1, self.und.next(rng));
                for h in &mut self.harms {
                    h.drift_node = (h.drift_node.1, h.drift.next(rng));
                    h.am_node = (h.am_node.1, h.am.next(rng));
                }
            }
            let fr = self.block_pos as f64 / hopf;
            self.block_pos += 1;

            // global envelope
            let x = (self.t_samp as f64 * self.rise_inv).min(1.0);
            let rise = x * x * (3.0 - 2.0 * x);
            let vib = self.vib_phase.sin();
            self.vib_phase += self.vib_step;
            if self.vib_phase > 2.0 * core::f64::consts::PI {
                self.vib_phase -= 2.0 * core::f64::consts::PI;
            }
            let und_v = self.und_node.0 + fr * (self.und_node.1 - self.und_node.0);
            let exc = (self.und_db * und_v + self.vib_am_db * vib).clamp(-12.0, 12.0);
            let mut env = rise * 10f64.powf(exc / 20.0);
            if self.released {
                let fade = self.rel_env1.max(self.rel_env2);
                env *= fade;
                self.rel_env1 *= self.rel_d1;
                self.rel_env2 *= self.rel_d2;
            }

            let mut s = 0.0;
            for h in &mut self.harms {
                let drift = h.drift_node.0 + fr * (h.drift_node.1 - h.drift_node.0);
                let cents = self.vib_cents * vib + self.drift_cents * drift;
                let f = h.freq_hz * (1.0 + LN2_1200 * cents);
                h.phase += 2.0 * core::f64::consts::PI * f / self.sr;
                if h.phase > 2.0 * core::f64::consts::PI {
                    h.phase -= 2.0 * core::f64::consts::PI;
                }
                let am_v = h.am_node.0 + fr * (h.am_node.1 - h.am_node.0);
                let am = (1.0 + self.am_span * am_v).max(0.05);
                s += h.amp * am * h.phase.sin();
            }

            for nb in &mut self.noise {
                let mut v = rng.standard_normal();
                for (sec, st) in nb.sos.iter().zip(nb.state.iter_mut()) {
                    let y = sec[0] * v + st[0];
                    st[0] = sec[1] * v - sec[3] * y + st[1];
                    st[1] = sec[2] * v - sec[4] * y;
                    v = y;
                }
                s += v * nb.gain;
            }

            *o += s * env;
            self.t_samp += 1;
        }
    }
}
