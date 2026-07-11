//! Butterworth bandpass design + cascaded-biquad filtering.
//!
//! Matches `scipy.signal.butter(4, [lo, hi], btype="bandpass", fs, output="sos")`
//! followed by `sosfilt`: the section grouping differs from scipy's zpk2sos
//! pairing, but the overall transfer function is identical (verified against
//! scipy impulse-response values in the tests below).

use num_complex::Complex64;
use std::f64::consts::PI;

/// One biquad section: [b0, b1, b2, a1, a2] with a0 = 1.
pub type Sos = Vec<[f64; 5]>;

/// 4th-order (per side) Butterworth bandpass as 4 biquad sections.
pub fn butter_bandpass4(lo: f64, hi: f64, fs: f64) -> Sos {
    const N: usize = 4;
    let two_fs = 2.0 * fs;
    // bilinear pre-warp
    let w1 = two_fs * (PI * lo / fs).tan();
    let w2 = two_fs * (PI * hi / fs).tan();
    let bw = w2 - w1;
    let w0 = (w1 * w2).sqrt();

    // analog lowpass prototype poles -> bandpass poles -> bilinear z-poles
    let mut zpoles: Vec<Complex64> = Vec::with_capacity(2 * N);
    for k in 0..N {
        let theta = PI * (2.0 * (k as f64 + 1.0) + N as f64 - 1.0) / (2.0 * N as f64);
        let p = Complex64::new(theta.cos(), theta.sin());
        let pb = p * (bw / 2.0);
        let disc = (pb * pb - Complex64::new(w0 * w0, 0.0)).sqrt();
        for s in [pb + disc, pb - disc] {
            let z = (Complex64::new(two_fs, 0.0) + s) / (Complex64::new(two_fs, 0.0) - s);
            zpoles.push(z);
        }
    }

    // conjugate-pair the poles: keep im >= 0 representatives
    let mut upper: Vec<Complex64> = zpoles.iter().copied().filter(|z| z.im >= 0.0).collect();
    // numerical safety: if reflection symmetry was lost, greedily rebuild
    if upper.len() != N {
        upper.clear();
        let mut pool = zpoles.clone();
        while !pool.is_empty() {
            let z = pool.swap_remove(0);
            let (mut best, mut bd) = (0usize, f64::MAX);
            for (i, c) in pool.iter().enumerate() {
                let d = (c - z.conj()).norm();
                if d < bd {
                    bd = d;
                    best = i;
                }
            }
            pool.swap_remove(best);
            upper.push(if z.im >= 0.0 { z } else { z.conj() });
        }
    }
    assert_eq!(upper.len(), N, "pole pairing failed");

    // each section: zeros at z=+1 and z=-1 -> numerator (1, 0, -1)
    let mut sos: Sos = upper
        .iter()
        .map(|z| [1.0, 0.0, -1.0, -2.0 * z.re, z.norm_sqr()])
        .collect();

    // normalize |H| = 1 at the (digital) center frequency, like scipy
    let wc = 2.0 * (w0 / two_fs).atan();
    let e1 = Complex64::new(0.0, -wc).exp();
    let e2 = Complex64::new(0.0, -2.0 * wc).exp();
    let mut h = Complex64::new(1.0, 0.0);
    for s in &sos {
        h *= (s[0] + s[1] * e1 + s[2] * e2) / (Complex64::new(1.0, 0.0) + s[3] * e1 + s[4] * e2);
    }
    let g = 1.0 / h.norm();
    for s in &mut sos {
        s[0] *= g.powf(1.0 / N as f64);
        s[1] *= g.powf(1.0 / N as f64);
        s[2] *= g.powf(1.0 / N as f64);
    }
    sos
}

/// In-place cascaded biquad filtering (direct form II transposed),
/// zero initial state — same as scipy.signal.sosfilt defaults.
pub fn sosfilt(sos: &[[f64; 5]], x: &mut [f64]) {
    for s in sos {
        let (b0, b1, b2, a1, a2) = (s[0], s[1], s[2], s[3], s[4]);
        let (mut z1, mut z2) = (0.0f64, 0.0f64);
        for v in x.iter_mut() {
            let xi = *v;
            let y = b0 * xi + z1;
            z1 = b1 * xi - a1 * y + z2;
            z2 = b2 * xi - a2 * y;
            *v = y;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// scipy reference: butter(4, [40, 40*200^0.1], bandpass, fs=48000) impulse head
    /// (from scripts/probe_stft_conventions.py).
    #[test]
    fn impulse_response_matches_scipy_band0() {
        let lo = 40.0;
        let hi = 40.0 * 200f64.powf(0.1);
        let sos = butter_bandpass4(lo, hi, 48000.0);
        assert_eq!(sos.len(), 4);
        let mut x = vec![0.0; 16];
        x[0] = 1.0;
        sosfilt(&sos, &mut x);
        let expect = [
            1.113859917219249e-11,
            8.900024617991454e-11,
            3.554567105523644e-10,
            9.757309339358396e-10,
            2.124530265973400e-09,
            3.974776648417334e-09,
        ];
        for (got, want) in x.iter().zip(expect.iter()) {
            let rel = (got - want).abs() / want.abs();
            assert!(rel < 1e-6, "got {got:e} want {want:e} rel {rel:e}");
        }
    }

    /// Frequency response sanity for the top band (matches scipy design band 9).
    #[test]
    fn unity_gain_at_center_band9() {
        let lo = 40.0 * 200f64.powf(0.9);
        let hi = 8000.0;
        let fs = 48000.0;
        let sos = butter_bandpass4(lo, hi, fs);
        // evaluate |H| at geometric center of the warped band
        let two_fs = 2.0 * fs;
        let w1 = two_fs * (std::f64::consts::PI * lo / fs).tan();
        let w2 = two_fs * (std::f64::consts::PI * hi / fs).tan();
        let wc = 2.0 * ((w1 * w2).sqrt() / two_fs).atan();
        let e1 = Complex64::new(0.0, -wc).exp();
        let e2 = Complex64::new(0.0, -2.0 * wc).exp();
        let mut h = Complex64::new(1.0, 0.0);
        for s in &sos {
            h *= (s[0] + s[1] * e1 + s[2] * e2)
                / (Complex64::new(1.0, 0.0) + s[3] * e1 + s[4] * e2);
        }
        assert!((h.norm() - 1.0).abs() < 1e-12, "|H(wc)| = {}", h.norm());
    }
}
