//! Real-time streaming synth: note events in, sample buffers out.
//! This is the API real-time consumers (testbed, io crate, WASM) drive;
//! the offline `Piano::synth_note` is a thin wrapper over the same Voice.

use crate::synth::Piano;
use crate::voice::Voice;

pub struct StreamSynth {
    pub piano: Piano,
    voices: Vec<Voice>,
    pedal: bool,
}

impl StreamSynth {
    pub fn new(piano: Piano) -> Self {
        StreamSynth {
            piano,
            voices: Vec::new(),
            pedal: false,
        }
    }

    pub fn note_on(&mut self, midi: i32, velocity: f64) {
        let v = self.piano.make_voice(midi, velocity);
        self.voices.push(v);
    }

    pub fn note_off(&mut self, midi: i32) {
        for v in &mut self.voices {
            if v.midi == midi && v.key_down {
                v.key_down = false;
                if !self.pedal {
                    v.trigger_release();
                }
            }
        }
    }

    pub fn set_pedal(&mut self, down: bool) {
        self.pedal = down;
        if !down {
            for v in &mut self.voices {
                if !v.key_down {
                    v.trigger_release();
                }
            }
        }
    }

    pub fn all_notes_off(&mut self) {
        for v in &mut self.voices {
            v.key_down = false;
            v.trigger_release();
        }
    }

    /// Fill `out` (overwrites), mixing all active voices; culls dead ones.
    pub fn render(&mut self, out: &mut [f64]) {
        out.fill(0.0);
        let rng = &mut self.piano.rng;
        for v in &mut self.voices {
            v.render_add(out, rng);
        }
        self.voices.retain(|v| !v.is_finished());
    }

    pub fn active_voices(&self) -> usize {
        self.voices.len()
    }
}
