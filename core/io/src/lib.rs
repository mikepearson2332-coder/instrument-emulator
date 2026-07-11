//! Device I/O layer: real-time audio output (cpal/WASAPI) and MIDI input
//! (midir/WinMM) around the pure-DSP engine. The engine crate stays free of
//! devices/threads; this crate owns the audio thread and the event queue.
//!
//! Architecture: control threads (GUI via Python, MIDI callback) push events
//! into an mpsc channel; the audio callback drains it, drives StreamSynth,
//! and publishes meters through atomics. The callback never touches Python
//! or takes locks.

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use engine::{Piano, StreamSynth};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{mpsc, Arc};
use std::time::Instant;

#[derive(Debug, Clone, Copy)]
pub enum Event {
    NoteOn(u8, f64),
    NoteOff(u8),
    Pedal(bool),
    AllNotesOff,
    /// max_partials, noise, max_symp_lines (usize::MAX = unlimited)
    Quality(usize, bool, usize),
    Gain(f64),
}

#[derive(Default)]
pub struct Meters {
    pub voices: AtomicUsize,
    /// audio-callback CPU load in permille of the buffer deadline
    pub load_permille: AtomicUsize,
    /// output peak in milli (1000 = 0 dBFS), decaying max
    pub peak_milli: AtomicUsize,
}

pub struct Live {
    _stream: cpal::Stream,
    tx: mpsc::Sender<Event>,
    pub meters: Arc<Meters>,
    pub sr: u32,
    pub device_name: String,
    midi_conn: Option<midir::MidiInputConnection<()>>,
}

fn apply(ev: Event, synth: &mut StreamSynth, gain: &mut f64) {
    match ev {
        Event::NoteOn(m, v) => synth.note_on(m as i32, v),
        Event::NoteOff(m) => synth.note_off(m as i32),
        Event::Pedal(d) => synth.set_pedal(d),
        Event::AllNotesOff => synth.all_notes_off(),
        Event::Quality(mp, noise, msl) => {
            synth.piano.quality = engine::Quality {
                max_partials: mp,
                noise,
                max_symp_lines: msl,
            };
        }
        Event::Gain(g) => *gain = g,
    }
}

impl Live {
    pub fn new(table_path: &str, seed: u64) -> Result<Self, String> {
        let host = cpal::default_host();
        let device = host
            .default_output_device()
            .ok_or("no default audio output device")?;
        let device_name = device.name().unwrap_or_else(|_| "unknown".into());
        let config = device.default_output_config().map_err(|e| e.to_string())?;
        let sr = config.sample_rate().0;
        let channels = config.channels() as usize;

        let piano = Piano::from_file(table_path, sr as usize, seed)?;
        let mut synth = StreamSynth::new(piano);
        let (tx, rx) = mpsc::channel::<Event>();
        let meters = Arc::new(Meters::default());
        let m = meters.clone();
        let mut gain = 0.25f64;
        let mut buf: Vec<f64> = Vec::new();

        let stream = device
            .build_output_stream(
                &config.into(),
                move |out: &mut [f32], _| {
                    let t0 = Instant::now();
                    while let Ok(ev) = rx.try_recv() {
                        apply(ev, &mut synth, &mut gain);
                    }
                    let frames = out.len() / channels;
                    buf.resize(frames, 0.0);
                    synth.render(&mut buf);
                    let mut peak = 0.0f64;
                    for (frame, v) in out.chunks_mut(channels).zip(&buf) {
                        // soft clip so ff chords stay musical
                        let s = (v * gain).tanh() as f32;
                        peak = peak.max(s.abs() as f64);
                        for c in frame.iter_mut() {
                            *c = s;
                        }
                    }
                    m.voices.store(synth.active_voices(), Ordering::Relaxed);
                    let avail = frames as f64 / sr as f64;
                    let load = t0.elapsed().as_secs_f64() / avail * 1000.0;
                    m.load_permille.store(load as usize, Ordering::Relaxed);
                    let pk = (peak * 1000.0) as usize;
                    m.peak_milli.fetch_max(pk, Ordering::Relaxed);
                },
                |e| eprintln!("audio stream error: {e}"),
                None,
            )
            .map_err(|e| e.to_string())?;
        stream.play().map_err(|e| e.to_string())?;

        Ok(Live {
            _stream: stream,
            tx,
            meters,
            sr,
            device_name,
            midi_conn: None,
        })
    }

    pub fn send(&self, ev: Event) {
        let _ = self.tx.send(ev);
    }

    /// Reset the decaying peak meter and return the previous value.
    pub fn take_peak_milli(&self) -> usize {
        self.meters.peak_milli.swap(0, Ordering::Relaxed)
    }

    // ------------------------------------------------------------- MIDI in

    pub fn midi_ports() -> Vec<String> {
        match midir::MidiInput::new("instrument-testbed") {
            Ok(input) => input
                .ports()
                .iter()
                .map(|p| input.port_name(p).unwrap_or_else(|_| "unknown".into()))
                .collect(),
            Err(_) => Vec::new(),
        }
    }

    pub fn midi_connect(&mut self, port_index: usize) -> Result<String, String> {
        let input = midir::MidiInput::new("instrument-testbed").map_err(|e| e.to_string())?;
        let ports = input.ports();
        let port = ports.get(port_index).ok_or("no such MIDI port")?;
        let name = input.port_name(port).unwrap_or_else(|_| "unknown".into());
        let tx = self.tx.clone();
        let conn = input
            .connect(
                port,
                "testbed-in",
                move |_ts, msg, _| {
                    if msg.len() < 3 {
                        return;
                    }
                    match msg[0] & 0xF0 {
                        0x90 if msg[2] > 0 => {
                            let _ = tx.send(Event::NoteOn(msg[1], msg[2] as f64));
                        }
                        0x90 | 0x80 => {
                            let _ = tx.send(Event::NoteOff(msg[1]));
                        }
                        0xB0 if msg[1] == 64 => {
                            let _ = tx.send(Event::Pedal(msg[2] >= 64));
                        }
                        _ => {}
                    }
                },
                (),
            )
            .map_err(|e| e.to_string())?;
        self.midi_conn = Some(conn);
        Ok(name)
    }

    pub fn midi_disconnect(&mut self) {
        self.midi_conn = None;
    }
}
