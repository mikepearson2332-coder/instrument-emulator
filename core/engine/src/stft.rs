//! Band-level measurement metric — a port of `Piano._band_metric`, which is a
//! specific use of `scipy.signal.stft` (periodic hann, nperseg=int(0.046*sr),
//! noverlap=nperseg-int(0.010*sr), boundary zero-extension by nperseg/2,
//! magnitude scaled by 1/sum(window), onesided without doubling).
//!
//! The synth calibrates its noise gains *through this metric*, so it must
//! reproduce scipy's numbers: the analysis stage measured the reference
//! recordings with scipy, and a constant dB offset here would directly bias
//! synthesized noise levels. Verified against scipy values in the tests.

use num_complex::Complex64;
use rustfft::FftPlanner;

pub struct BandMetric {
    sr: usize,
    nper: usize,
    hop: usize,
    window: Vec<f64>,
    wsum: f64,
    fft: std::sync::Arc<dyn rustfft::Fft<f64>>,
}

impl BandMetric {
    pub fn new(sr: usize) -> Self {
        Self::with_windows(sr, 0.046, 0.010)
    }

    /// Same scipy conventions with a different window/hop — the sustained
    /// family measures its noise bed with 0.2 s windows (46 ms cannot
    /// resolve non-harmonic bins between low-string harmonics).
    pub fn with_windows(sr: usize, win_s: f64, hop_s: f64) -> Self {
        let nper = (win_s * sr as f64) as usize;
        let hop = (hop_s * sr as f64) as usize;
        // periodic hann (scipy get_window default, fftbins=True)
        let window: Vec<f64> = (0..nper)
            .map(|i| 0.5 - 0.5 * (2.0 * std::f64::consts::PI * i as f64 / nper as f64).cos())
            .collect();
        let wsum: f64 = window.iter().sum();
        let fft = FftPlanner::new().plan_fft_forward(nper);
        BandMetric {
            sr,
            nper,
            hop,
            window,
            wsum,
            fft,
        }
    }

    /// Median-magnitude track over frames for bins with lo <= f < hi,
    /// plus each frame's time in seconds (t=0 at the first frame,
    /// centered on the first input sample via zero boundary extension).
    fn median_track(&self, x: &[f64], lo: f64, hi: f64) -> Vec<(f64, f64)> {
        let pad = self.nper / 2;
        let ext_len = x.len() + 2 * pad;
        let n_frames = if ext_len >= self.nper {
            (ext_len - self.nper) / self.hop + 1
        } else {
            0
        };
        let bin_hz = self.sr as f64 / self.nper as f64;
        let k_lo = (lo / bin_hz).ceil() as usize;
        let mut k_hi = (hi / bin_hz).ceil() as usize; // first bin >= hi (excluded)
        k_hi = k_hi.min(self.nper / 2 + 1);
        // guard exact-boundary float cases like scipy's f >= lo comparison
        let k_lo = if (k_lo as f64) * bin_hz < lo { k_lo + 1 } else { k_lo };

        let mut buf = vec![Complex64::new(0.0, 0.0); self.nper];
        let mut mags: Vec<f64> = Vec::with_capacity(k_hi.saturating_sub(k_lo));
        let mut track = Vec::with_capacity(n_frames);
        for fr in 0..n_frames {
            let start = fr as isize * self.hop as isize - pad as isize;
            for (i, b) in buf.iter_mut().enumerate() {
                let idx = start + i as isize;
                let v = if idx >= 0 && (idx as usize) < x.len() {
                    x[idx as usize]
                } else {
                    0.0
                };
                *b = Complex64::new(v * self.window[i], 0.0);
            }
            self.fft.process(&mut buf);
            mags.clear();
            for k in k_lo..k_hi {
                mags.push(buf[k].norm() / self.wsum);
            }
            track.push((median(&mut mags), fr as f64 * self.hop as f64 / self.sr as f64));
        }
        track
    }

    /// (steady dB, attack-max dB) of the median band magnitude —
    /// the same metric the Python analysis/synth calibration uses.
    pub fn band_metric(&self, x: &[f64], lo: f64, hi: f64) -> (f64, f64) {
        let track = self.median_track(x, lo, hi);
        let mut meds: Vec<f64> = track.iter().map(|(m, _)| *m).collect();
        let steady = median(&mut meds);
        let attack = track
            .iter()
            .filter(|(_, t)| *t < 0.12)
            .map(|(m, _)| *m)
            .fold(f64::NAN, f64::max);
        let attack = if attack.is_nan() { steady } else { attack };
        (
            20.0 * (steady + 1e-12).log10(),
            20.0 * (attack + 1e-12).log10(),
        )
    }
}

/// numpy-convention median (mean of the two middle values for even length).
fn median(v: &mut [f64]) -> f64 {
    if v.is_empty() {
        return f64::NAN;
    }
    v.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = v.len();
    if n % 2 == 1 {
        v[n / 2]
    } else {
        0.5 * (v[n / 2 - 1] + v[n / 2])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Reference values from scripts/probe_stft_conventions.py (scipy 48 kHz):
    /// x = sin(2π·997·i/sr)·exp(-i/(0.3·sr)), i in 0..sr.
    #[test]
    fn matches_scipy_band_medians() {
        let sr = 48000usize;
        let x: Vec<f64> = (0..sr)
            .map(|i| {
                (2.0 * std::f64::consts::PI * 997.0 * i as f64 / sr as f64).sin()
                    * (-(i as f64) / (0.3 * sr as f64)).exp()
            })
            .collect();
        let bm = BandMetric::new(sr);
        assert_eq!(bm.nper, 2208);
        assert_eq!(bm.hop, 480);

        let edges: Vec<f64> = (0..11)
            .map(|i| 40.0 * 200f64.powf(i as f64 / 10.0))
            .collect();

        // band 4: steady 8.922193280679e-07, attack 8.772898236504e-03
        let track = bm.median_track(&x, edges[4], edges[5]);
        assert_eq!(track.len(), 101);
        let mut meds: Vec<f64> = track.iter().map(|(m, _)| *m).collect();
        let steady = median(&mut meds);
        let attack = track
            .iter()
            .filter(|(_, t)| *t < 0.12)
            .map(|(m, _)| *m)
            .fold(f64::MIN, f64::max);
        assert!(
            (steady - 8.922193280679e-07).abs() / 8.922193280679e-07 < 1e-6,
            "steady {steady:e}"
        );
        assert!(
            (attack - 8.772898236504e-03).abs() / 8.772898236504e-03 < 1e-6,
            "attack {attack:e}"
        );

        // band 9: steady 9.821940454076e-10, attack 1.857536541877e-04
        let track = bm.median_track(&x, edges[9], edges[10]);
        let mut meds: Vec<f64> = track.iter().map(|(m, _)| *m).collect();
        let steady = median(&mut meds);
        let attack = track
            .iter()
            .filter(|(_, t)| *t < 0.12)
            .map(|(m, _)| *m)
            .fold(f64::MIN, f64::max);
        assert!(
            (steady - 9.821940454076e-10).abs() / 9.821940454076e-10 < 1e-6,
            "steady {steady:e}"
        );
        assert!(
            (attack - 1.857536541877e-04).abs() / 1.857536541877e-04 < 1e-6,
            "attack {attack:e}"
        );
    }
}
