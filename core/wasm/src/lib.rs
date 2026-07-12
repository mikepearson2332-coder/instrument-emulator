//! WASM binding over the pure-DSP `engine` crate for browser use.
//!
//! Exposes `Synth`, a thin wrapper over `engine::StreamSynth` (events in,
//! sample buffers out). Designed to be driven from an `AudioWorkletProcessor`:
//! construct once with a parameter-table JSON + the AudioContext sample rate,
//! push note events, and call `render()` each audio block.
//!
//! The same `Synth` serves every modal-family instrument in the bank — the
//! instrument is entirely determined by the params JSON you pass (piano
//! `grand.json`, rhodes `mk1.json`, …). No audio samples ship; the payload is
//! just the params table plus this ~small wasm binary.
//!
//! Note: the engine uses its own seeded PRNG (`engine::rng`), so there is no
//! `getrandom`/JS-entropy dependency — determinism is controlled by `seed`.

use engine::{params::Table, Piano, StreamSynth};
use wasm_bindgen::prelude::*;

#[wasm_bindgen(start)]
pub fn start() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

#[wasm_bindgen]
pub struct Synth {
    inner: StreamSynth,
    /// f64 scratch reused across blocks; the engine renders f64, WebAudio
    /// wants f32, so we narrow at the boundary.
    scratch: Vec<f64>,
}

#[wasm_bindgen]
impl Synth {
    /// Build a synth for one instrument.
    ///
    /// - `params_json`: the contents of an `instruments/<name>/params/*.json`
    ///   table (e.g. piano `grand.json`, rhodes `mk1.json`).
    /// - `sample_rate`: pass the live `AudioContext.sampleRate` so there is no
    ///   resampling and no pitch error (Android WebViews usually run 48000).
    /// - `seed`: PRNG seed for the stochastic parts (noise/phase); any value.
    #[wasm_bindgen(constructor)]
    pub fn new(params_json: &str, sample_rate: usize, seed: u64) -> Result<Synth, JsError> {
        let table = Table::from_json(params_json).map_err(|e| JsError::new(&e))?;
        let piano = Piano::new(table, sample_rate, seed);
        Ok(Synth {
            inner: StreamSynth::new(piano),
            scratch: Vec::new(),
        })
    }

    /// Start a note. `velocity` is MIDI-style 1..=127.
    pub fn note_on(&mut self, midi: i32, velocity: f64) {
        self.inner.note_on(midi, velocity);
    }

    /// Release a note (respects the sustain pedal, like the native engine).
    pub fn note_off(&mut self, midi: i32) {
        self.inner.note_off(midi);
    }

    /// Sustain pedal down/up.
    pub fn set_pedal(&mut self, down: bool) {
        self.inner.set_pedal(down);
    }

    /// Release everything (panic button / instrument switch).
    pub fn all_notes_off(&mut self) {
        self.inner.all_notes_off();
    }

    /// Render `out.len()` mono frames, overwriting `out`. Call once per audio
    /// block with the worklet's output Float32Array. Dead voices are culled.
    pub fn render(&mut self, out: &mut [f32]) {
        if self.scratch.len() != out.len() {
            self.scratch.resize(out.len(), 0.0);
        }
        self.inner.render(&mut self.scratch);
        for (o, &s) in out.iter_mut().zip(self.scratch.iter()) {
            *o = s as f32;
        }
    }

    /// Number of currently sounding voices (for a CPU/voice meter).
    #[wasm_bindgen(getter)]
    pub fn active_voices(&self) -> usize {
        self.inner.active_voices()
    }
}
