//! Parameter-table schema (`instruments/<name>/params/*.json`).
//! Mirrors what `pianomodel` calibration writes; unknown fields are ignored.

use serde::Deserialize;

#[derive(Deserialize, Clone)]
pub struct Table {
    #[serde(default)]
    pub symp_lines: Option<Vec<SympLine>>,
    #[serde(default = "default_symp_anchor")]
    pub symp_anchor_s: f64,
    pub keys: Vec<Key>,
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
