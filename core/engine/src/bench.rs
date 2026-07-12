//! Host calibration: measure this machine's synthesis throughput and solve
//! for the best quality level at a target polyphony and CPU budget.

use crate::synth::Piano;
use crate::voice::Quality;
use serde::Serialize;
use std::time::Instant;

#[derive(Serialize, Clone, Copy, Debug)]
pub struct BenchResult {
    /// Marginal cost of one partial for one output sample (seconds).
    pub sec_per_partial_sample: f64,
    /// Fixed per-voice cost for one output sample (noise, symp, mixing).
    pub sec_per_voice_sample: f64,
    /// Convenience: partial-samples per second.
    pub partials_per_sec: f64,
}

fn time_render(piano: &mut Piano, midi: i32, dur: f64, reps: usize) -> f64 {
    // warmup
    piano.synth_note(midi, 88.0, 0.1, None, false);
    let t0 = Instant::now();
    for _ in 0..reps {
        piano.synth_note(midi, 88.0, dur, None, false);
    }
    t0.elapsed().as_secs_f64() / reps as f64
}

/// Two-point fit: time a rich voice at two partial budgets; the slope is the
/// per-partial cost, the intercept the fixed per-voice overhead.
pub fn run(piano: &mut Piano) -> BenchResult {
    let saved = piano.quality;
    let dur = 1.0;
    let n_samp = piano.sr as f64 * dur;
    let midi = 48; // low-mid key: many partials available

    // sustained tables have no modal partials — floor the budget spread
    // so the two-point fit stays well-posed (harm counts are similar)
    let full = piano.note_params(midi, 88.0).partials.len().max(24);
    let k_hi = full.min(60);
    let k_lo = 8usize;

    piano.quality = Quality {
        max_partials: k_hi,
        ..Quality::FULL
    };
    let t_hi = time_render(piano, midi, dur, 3);
    piano.quality = Quality {
        max_partials: k_lo,
        ..Quality::FULL
    };
    let t_lo = time_render(piano, midi, dur, 3);
    piano.quality = saved;

    let per_partial = ((t_hi - t_lo) / (k_hi - k_lo) as f64 / n_samp).max(1e-12);
    let overhead = (t_lo / n_samp - k_lo as f64 * per_partial).max(0.0);
    BenchResult {
        sec_per_partial_sample: per_partial,
        sec_per_voice_sample: overhead,
        partials_per_sec: 1.0 / per_partial,
    }
}

/// Largest per-voice partial budget that fits `polyphony` voices in
/// `cpu_fraction` of one core at this Piano's sample rate.
pub fn pick_max_partials(b: &BenchResult, sr: usize, polyphony: usize, cpu_fraction: f64) -> usize {
    let budget_per_voice_sample = cpu_fraction / (sr as f64 * polyphony as f64);
    let k = (budget_per_voice_sample - b.sec_per_voice_sample) / b.sec_per_partial_sample;
    k.max(0.0) as usize
}
