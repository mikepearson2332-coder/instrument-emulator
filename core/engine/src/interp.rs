//! Key/velocity interpolation — port of `Piano.note_params` and helpers.
//! Fully deterministic; verified against the Python reference to float
//! precision by scripts/compare_engines.py.

use crate::params::{Key, Layer, Table};
use serde::Serialize;
use std::collections::BTreeMap;

pub const N_BANDS: usize = 10;

#[derive(Clone, Serialize)]
pub struct PState {
    pub n: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fr: Option<f64>,
    pub a1: f64,
    pub t1: f64,
    pub a2: f64,
    pub t2: f64,
}

#[derive(Clone, Serialize)]
pub struct NoteParams {
    pub f0: f64,
    #[serde(rename = "B")]
    pub b: f64,
    pub partials: Vec<PState>,
    pub thump_db: Vec<f64>,
    pub bed_db: Vec<f64>,
    pub bed_t60: Vec<f64>,
    pub bed_anchor_s: f64,
    pub symp_db: Vec<f64>,
}

#[derive(Clone)]
struct LayerState {
    partials: Vec<PState>,
    thump_db: Vec<f64>,
    bed_db: Vec<f64>,
    bed_t60: Vec<f64>,
    bed_anchor_s: f64,
    symp_db: Vec<f64>,
}

pub fn midi_to_freq(midi: f64) -> f64 {
    440.0 * 2f64.powf((midi - 69.0) / 12.0)
}

fn clean_profile(prof: &Option<Vec<Option<f64>>>, floor: f64) -> Vec<f64> {
    match prof {
        None => vec![floor; N_BANDS],
        Some(v) => v.iter().map(|x| x.unwrap_or(floor)).collect(),
    }
}

fn lerp_profile(a: &[f64], b: &[f64], w: f64) -> Vec<f64> {
    a.iter().zip(b).map(|(x, y)| x + (y - x) * w).collect()
}

fn layer_state(layer: &Layer) -> LayerState {
    LayerState {
        partials: layer
            .partials
            .iter()
            .map(|p| PState {
                n: p.n,
                fr: p.fr,
                a1: p.a1,
                t1: p.t1,
                a2: p.a2,
                t2: p.t2,
            })
            .collect(),
        thump_db: clean_profile(&layer.thump_db, -120.0),
        bed_db: clean_profile(&layer.bed_db, -120.0),
        bed_t60: clean_profile(&layer.bed_t60, 10.0),
        // Python: float(layer.get("bed_anchor_s", 1.5) or 1.5) — None and 0 both -> 1.5
        bed_anchor_s: match layer.bed_anchor_s {
            Some(v) if v != 0.0 => v,
            _ => 1.5,
        },
        symp_db: layer
            .symp_db
            .as_ref()
            .map(|v| v.iter().map(|x| x.unwrap_or(-140.0)).collect())
            .unwrap_or_default(),
    }
}

/// Log-domain interpolation between two partial lists, matched by n.
/// A partial missing on one side fades toward -80 dB of the other.
fn merge_partials(lo: &[PState], hi: &[PState], w: f64) -> Vec<PState> {
    let lo_map: BTreeMap<i64, &PState> = lo.iter().map(|p| (p.n, p)).collect();
    let hi_map: BTreeMap<i64, &PState> = hi.iter().map(|p| (p.n, p)).collect();
    let loglerp = |a: f64, b: f64, floor: f64| -> f64 {
        let la = a.max(floor).ln();
        let lb = b.max(floor).ln();
        (la + (lb - la) * w).exp()
    };
    let mut ns: Vec<i64> = lo_map.keys().chain(hi_map.keys()).copied().collect();
    ns.sort_unstable();
    ns.dedup();
    ns.iter()
        .map(|n| {
            let a = lo_map.get(n);
            let b = hi_map.get(n);
            let (a1a, t1a, a2a, t2a) = match (a, b) {
                (Some(p), _) => (p.a1, p.t1, p.a2, p.t2),
                (None, Some(p)) => (p.a1 * 1e-4, p.t1, p.a2 * 1e-4, p.t2),
                (None, None) => unreachable!(),
            };
            let (a1b, t1b, a2b, t2b) = match (b, a) {
                (Some(p), _) => (p.a1, p.t1, p.a2, p.t2),
                (None, Some(p)) => (p.a1 * 1e-4, p.t1, p.a2 * 1e-4, p.t2),
                (None, None) => unreachable!(),
            };
            // a side missing -> it inherits the other side's fr (mirrors
            // the Python {**b, ...} copy semantics)
            let fr_a = a.and_then(|p| p.fr).or_else(|| b.and_then(|p| p.fr));
            let fr_b = b.and_then(|p| p.fr).or_else(|| a.and_then(|p| p.fr));
            let fr = match (fr_a, fr_b) {
                (Some(x), Some(y)) => Some(loglerp(x, y, 1e-6)),
                _ => None,
            };
            PState {
                n: *n,
                fr,
                a1: loglerp(a1a, a1b, 1e-9),
                t1: loglerp(t1a, t1b, 1e-3),
                a2: loglerp(a2a, a2b, 1e-9),
                t2: loglerp(t2a, t2b, 1e-3),
            }
        })
        .collect()
}

fn pad_to(v: &[f64], n: usize) -> Vec<f64> {
    let mut out = v.to_vec();
    out.resize(n.max(v.len()), -140.0);
    out
}

/// Note state at arbitrary velocity (log-amp interpolation between layers).
fn interp_layers(layers: &[Layer], velocity: f64) -> LayerState {
    let vs: Vec<f64> = layers.iter().map(|l| l.vel).collect();
    if velocity <= vs[0] {
        return layer_state(&layers[0]);
    }
    if velocity >= *vs.last().unwrap() {
        return layer_state(layers.last().unwrap());
    }
    let j = vs.iter().position(|v| *v >= velocity).unwrap();
    if vs[j] == velocity {
        return layer_state(&layers[j]);
    }
    let i = j - 1;
    let w = (velocity - vs[i]) / (vs[j] - vs[i]);
    let lo = layer_state(&layers[i]);
    let hi = layer_state(&layers[j]);
    let n_lines = lo.symp_db.len().max(hi.symp_db.len());
    let (slo, shi) = (pad_to(&lo.symp_db, n_lines), pad_to(&hi.symp_db, n_lines));
    LayerState {
        partials: merge_partials(&lo.partials, &hi.partials, w),
        thump_db: lerp_profile(&lo.thump_db, &hi.thump_db, w),
        bed_db: lerp_profile(&lo.bed_db, &hi.bed_db, w),
        bed_t60: lerp_profile(&lo.bed_t60, &hi.bed_t60, w),
        bed_anchor_s: lo.bed_anchor_s * (1.0 - w) + hi.bed_anchor_s * w,
        symp_db: slo.iter().zip(&shi).map(|(a, b)| a + (b - a) * w).collect(),
    }
}

/// Sampled keys bracketing `midi` and the interpolation weight.
/// Keys must be sorted by midi (Table::from_json guarantees this).
fn neighbor_keys(keys: &[Key], midi: i32) -> (usize, usize, f64) {
    let n = keys.len();
    if midi <= keys[0].midi {
        return (0, 0, 0.0);
    }
    if midi >= keys[n - 1].midi {
        return (n - 1, n - 1, 0.0);
    }
    let hi = keys.iter().position(|k| k.midi >= midi).unwrap();
    if keys[hi].midi == midi {
        return (hi, hi, 0.0);
    }
    let lo = hi - 1;
    let w = (midi - keys[lo].midi) as f64 / (keys[hi].midi - keys[lo].midi) as f64;
    (lo, hi, w)
}

fn from_state(f0: f64, b: f64, s: LayerState) -> NoteParams {
    NoteParams {
        f0,
        b,
        partials: s.partials,
        thump_db: s.thump_db,
        bed_db: s.bed_db,
        bed_t60: s.bed_t60,
        bed_anchor_s: s.bed_anchor_s,
        symp_db: s.symp_db,
    }
}

/// Interpolated synthesis parameters for arbitrary key/velocity.
pub fn note_params(table: &Table, midi: i32, velocity: f64) -> NoteParams {
    let keys = &table.keys;
    let (lo, hi, w) = neighbor_keys(keys, midi);
    let slo = interp_layers(&keys[lo].layers, velocity);
    if lo == hi {
        let f0 = keys[lo].f0 * 2f64.powf((midi - keys[lo].midi) as f64 / 12.0);
        return from_state(f0, keys[lo].b, slo);
    }
    let shi = interp_layers(&keys[hi].layers, velocity);
    let (klo, khi) = (&keys[lo], &keys[hi]);

    // keep each neighbor's stretch deviation, interpolate in cents
    let dev_lo = 1200.0 * (klo.f0 / midi_to_freq(klo.midi as f64)).log2();
    let dev_hi = 1200.0 * (khi.f0 / midi_to_freq(khi.midi as f64)).log2();
    let dev = dev_lo + (dev_hi - dev_lo) * w;
    let f0 = midi_to_freq(midi as f64) * 2f64.powf(dev / 1200.0);
    let log_b = klo.b.ln() + (khi.b.ln() - klo.b.ln()) * w;
    let n_lines = slo.symp_db.len().max(shi.symp_db.len());
    let (plo, phi) = (pad_to(&slo.symp_db, n_lines), pad_to(&shi.symp_db, n_lines));
    NoteParams {
        f0,
        b: log_b.exp(),
        partials: merge_partials(&slo.partials, &shi.partials, w),
        thump_db: lerp_profile(&slo.thump_db, &shi.thump_db, w),
        bed_db: lerp_profile(&slo.bed_db, &shi.bed_db, w),
        bed_t60: lerp_profile(&slo.bed_t60, &shi.bed_t60, w),
        bed_anchor_s: slo.bed_anchor_s * (1.0 - w) + shi.bed_anchor_s * w,
        symp_db: plo.iter().zip(&phi).map(|(a, b)| a + (b - a) * w).collect(),
    }
}

// used by lerp_profile via zip: profiles are always N_BANDS long from clean_profile
impl NoteParams {
    pub fn partial_count(&self) -> usize {
        self.partials.len()
    }
}
