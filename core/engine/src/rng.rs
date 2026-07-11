//! Deterministic PRNG for synthesis (xoshiro256++ + Box-Muller normals).
//!
//! Not numpy-compatible: the Python reference uses PCG64/ziggurat, so renders
//! differ in noise realization but match in distribution. Verification against
//! the Python engine is therefore statistical (eval-score parity), plus exact
//! comparison of the deterministic parameter-interpolation path.

pub struct Rng {
    s: [u64; 4],
    spare_normal: Option<f64>,
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E3779B97F4A7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
    z ^ (z >> 31)
}

impl Rng {
    pub fn new(seed: u64) -> Self {
        let mut sm = seed;
        let s = [
            splitmix64(&mut sm),
            splitmix64(&mut sm),
            splitmix64(&mut sm),
            splitmix64(&mut sm),
        ];
        Rng {
            s,
            spare_normal: None,
        }
    }

    #[inline]
    pub fn next_u64(&mut self) -> u64 {
        let s = &mut self.s;
        let result = s[0].wrapping_add(s[3]).rotate_left(23).wrapping_add(s[0]);
        let t = s[1] << 17;
        s[2] ^= s[0];
        s[3] ^= s[1];
        s[1] ^= s[2];
        s[0] ^= s[3];
        s[2] ^= t;
        s[3] = s[3].rotate_left(45);
        result
    }

    /// Uniform in [0, 1) with 53-bit resolution.
    #[inline]
    pub fn next_f64(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 * (1.0 / (1u64 << 53) as f64)
    }

    #[inline]
    pub fn uniform(&mut self, lo: f64, hi: f64) -> f64 {
        lo + (hi - lo) * self.next_f64()
    }

    /// Standard normal via the Marsaglia polar method (pair-cached, no trig).
    pub fn standard_normal(&mut self) -> f64 {
        if let Some(v) = self.spare_normal.take() {
            return v;
        }
        loop {
            let x = 2.0 * self.next_f64() - 1.0;
            let y = 2.0 * self.next_f64() - 1.0;
            let s = x * x + y * y;
            if s > 0.0 && s < 1.0 {
                let f = (-2.0 * s.ln() / s).sqrt();
                self.spare_normal = Some(y * f);
                return x * f;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uniform_range_and_determinism() {
        let mut a = Rng::new(1234);
        let mut b = Rng::new(1234);
        for _ in 0..1000 {
            let x = a.uniform(-0.25, 0.25);
            assert!((-0.25..0.25).contains(&x));
            assert_eq!(x, b.uniform(-0.25, 0.25));
        }
    }

    #[test]
    fn normal_moments() {
        let mut r = Rng::new(7);
        let n = 200_000;
        let (mut sum, mut sq) = (0.0, 0.0);
        for _ in 0..n {
            let v = r.standard_normal();
            sum += v;
            sq += v * v;
        }
        let mean = sum / n as f64;
        let var = sq / n as f64 - mean * mean;
        assert!(mean.abs() < 0.01, "mean {mean}");
        assert!((var - 1.0).abs() < 0.02, "var {var}");
    }
}
