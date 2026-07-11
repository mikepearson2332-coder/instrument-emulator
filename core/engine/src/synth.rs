//! Modal piano synthesizer — offline API over the streaming Voice
//! (see voice.rs). Model reference: `instruments/piano/synth.py`.

use crate::filters::{butter_bandpass4, sosfilt, Sos};
use crate::interp::{note_params, NoteParams, N_BANDS};
use crate::params::Table;
use crate::rng::Rng;
use crate::stft::BandMetric;
use crate::voice::{Quality, ReleaseStyle, Voice, VoiceStyle, THUMP_TAU};

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
    pub quality: Quality,
    pub style: VoiceStyle,
    pub(crate) rng: Rng,
    pub(crate) band_sos: Vec<Sos>,
    pub(crate) cal_bed: Vec<f64>,
    pub(crate) cal_thump: Vec<f64>,
    pub(crate) thump_taus: Vec<f64>,
}

/// Behavior + per-band click taus from the table config; absent config =
/// exact piano semantics (grand.json predates the config block).
fn style_from_table(table: &Table) -> (VoiceStyle, Vec<f64>) {
    match &table.config {
        None => (VoiceStyle::PIANO, vec![THUMP_TAU; N_BANDS]),
        Some(c) => {
            let tau = c.thump_tau_s.unwrap_or(THUMP_TAU);
            let mut taus = c.thump_tau_bands.clone().unwrap_or_default();
            taus.resize(N_BANDS, tau);
            if c.thump_tau_bands.is_none() {
                taus = vec![tau; N_BANDS];
            }
            let release = match c.release_fade_s {
                Some(f) => ReleaseStyle::Fade {
                    fade_s: f,
                    remnant: c.release_remnant.unwrap_or(0.0),
                    undamped_above: c.undamped_above,
                },
                None => ReleaseStyle::NoDampers,
            };
            (
                VoiceStyle {
                    piano_unison: false,
                    attack_s: c.attack_s.unwrap_or(0.0),
                    release,
                },
                taus,
            )
        }
    }
}

impl Piano {
    pub fn from_file(path: &str, sr: usize, seed: u64) -> Result<Self, String> {
        let json = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
        Ok(Self::new(Table::from_json(&json)?, sr, seed))
    }

    pub fn new(table: Table, sr: usize, seed: u64) -> Self {
        let edges = band_edges();
        let srf = sr as f64;
        let (style, thump_taus) = style_from_table(&table);
        // per-band bandpass filters + empirical level calibration so that
        // synthesized noise reproduces measured bed/thump dB exactly under
        // the same measurement code (see stft.rs)
        let metric = BandMetric::new(sr);
        let mut probe_rng = Rng::new(99);
        let probe: Vec<f64> = (0..sr).map(|_| probe_rng.standard_normal()).collect();

        let mut band_sos = Vec::with_capacity(N_BANDS);
        let mut cal_bed = Vec::with_capacity(N_BANDS);
        let mut cal_thump = Vec::with_capacity(N_BANDS);
        for i in 0..N_BANDS {
            let (lo, hi) = (edges[i], edges[i + 1].min(srf / 2.0 * 0.98));
            let sos = butter_bandpass4(lo, hi, srf);
            let mut nb = probe.clone();
            sosfilt(&sos, &mut nb);
            let (steady_db, _) = metric.band_metric(&nb, edges[i], edges[i + 1]);
            let nb_thump: Vec<f64> = nb
                .iter()
                .enumerate()
                .map(|(j, a)| a * (-(j as f64) / (thump_taus[i] * srf)).exp())
                .collect();
            let (_, attack_db) = metric.band_metric(&nb_thump, edges[i], edges[i + 1]);
            band_sos.push(sos);
            cal_bed.push(steady_db);
            cal_thump.push(attack_db);
        }

        Piano {
            table,
            sr,
            quality: Quality::FULL,
            style,
            rng: Rng::new(seed),
            band_sos,
            cal_bed,
            cal_thump,
            thump_taus,
        }
    }

    pub fn note_params(&self, midi: i32, velocity: f64) -> NoteParams {
        note_params(&self.table, midi, velocity)
    }

    pub(crate) fn make_voice(&mut self, midi: i32, velocity: f64) -> Voice {
        let p = self.note_params(midi, velocity);
        let lines = self.table.symp_lines.as_deref().unwrap_or(&[]);
        Voice::new(
            &p,
            midi,
            self.sr as f64,
            self.quality,
            lines,
            self.table.symp_anchor_s,
            &self.band_sos,
            &self.cal_bed,
            &self.cal_thump,
            &self.thump_taus,
            &self.style,
            &mut self.rng,
        )
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
        let n_samp = (dur * srf) as usize;
        let mut voice = self.make_voice(midi, velocity);
        let mut out = vec![0.0f64; n_samp];
        let r0 = match release_at {
            Some(rel) if rel < dur && !sustain_pedal => (rel * srf) as usize,
            _ => n_samp,
        };
        let r0 = r0.min(n_samp);
        let (head, tail) = out.split_at_mut(r0);
        voice.render_add(head, &mut self.rng);
        if !tail.is_empty() {
            voice.trigger_release(); // no-op for undamped keys (midi >= 89)
            voice.render_add(tail, &mut self.rng);
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
