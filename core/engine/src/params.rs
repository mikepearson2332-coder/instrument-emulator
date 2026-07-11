//! Parameter-table schema (`instruments/<name>/params/*.json`).
//! Mirrors what `pianomodel` calibration writes; unknown fields are ignored.

use serde::Deserialize;

#[derive(Deserialize, Clone)]
pub struct Table {
    #[serde(default)]
    pub symp_lines: Option<Vec<SympLine>>,
    #[serde(default = "default_symp_anchor")]
    pub symp_anchor_s: f64,
    /// Present on generic modal tables (woodblock, mallets, plucked
    /// strings); absent on the piano table -> exact piano behavior.
    #[serde(default)]
    pub config: Option<Config>,
    pub keys: Vec<Key>,
}

/// Behavior switches for the generic modal family. All fields optional so
/// tables only state what differs from the defaults.
#[derive(Deserialize, Clone, Default)]
pub struct Config {
    /// Native sample rate of the reference set (informational; the engine
    /// renders at whatever rate it is constructed with).
    #[serde(default)]
    pub sr: Option<usize>,
    /// Attack-noise decay when `thump_tau_bands` is absent.
    #[serde(default)]
    pub thump_tau_s: Option<f64>,
    /// Per-band attack-noise decay (10 log bands 40 Hz - 8 kHz).
    #[serde(default)]
    pub thump_tau_bands: Option<Vec<f64>>,
    /// Partial onset ramp seconds (contact time); 0/absent = instant.
    #[serde(default)]
    pub attack_s: Option<f64>,
    /// Damper fade on note-off; absent/null = no dampers (note-off ignored).
    #[serde(default)]
    pub release_fade_s: Option<f64>,
    /// Residual level ringing on after damping (piano uses 0.02).
    #[serde(default)]
    pub release_remnant: Option<f64>,
    /// Keys above this midi have no dampers.
    #[serde(default)]
    pub undamped_above: Option<i32>,
}

fn default_symp_anchor() -> f64 {
    1.2
}

#[derive(Deserialize, Clone)]
pub struct SympLine {
    pub freq: f64,
    pub t60: f64,
}

#[derive(Deserialize, Clone)]
pub struct Key {
    pub note: String,
    pub midi: i32,
    pub f0: f64,
    #[serde(rename = "B")]
    pub b: f64,
    pub layers: Vec<Layer>,
}

#[derive(Deserialize, Clone)]
pub struct Layer {
    pub vel: f64,
    /// Per-band dB profiles; missing list or null entries mean "floor".
    #[serde(default)]
    pub thump_db: Option<Vec<Option<f64>>>,
    #[serde(default)]
    pub bed_db: Option<Vec<Option<f64>>>,
    #[serde(default)]
    pub bed_t60: Option<Vec<Option<f64>>>,
    #[serde(default)]
    pub bed_anchor_s: Option<f64>,
    #[serde(default)]
    pub symp_db: Option<Vec<Option<f64>>>,
    pub partials: Vec<Partial>,
}

#[derive(Deserialize, Clone, Copy)]
pub struct Partial {
    pub n: i64,
    /// Explicit frequency ratio (freq = fr * f0) for non-string mode
    /// series; absent -> inharmonic string series n*f0*sqrt(1+B*n^2).
    #[serde(default)]
    pub fr: Option<f64>,
    pub a1: f64,
    pub t1: f64,
    pub a2: f64,
    pub t2: f64,
}

impl Table {
    pub fn from_json(json: &str) -> Result<Self, String> {
        let mut t: Table = serde_json::from_str(json).map_err(|e| e.to_string())?;
        t.keys.sort_by_key(|k| k.midi);
        Ok(t)
    }
}
