//! Sample-free instrument synthesis engine.
//!
//! Pure DSP: parameter tables in, sample buffers out. No devices, no threads,
//! no OS dependencies — device I/O lives in the (future) `io` crate.
//!
//! Currently one engine family: calibrated modal synthesis (piano). The
//! reference implementation is `instruments/piano/synth.py`; this is a port
//! verified against it by the Python evaluation harness.

pub mod bench;
pub mod filters;
pub mod interp;
pub mod params;
pub mod rng;
pub mod stft;
pub mod stream;
pub mod sustained;
pub mod synth;
pub mod voice;

pub use interp::NoteParams;
pub use params::Table;
pub use stream::StreamSynth;
pub use synth::Piano;
pub use voice::Quality;
