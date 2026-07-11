//! Python binding for the engine — used by the lab (calibration/evaluation)
//! and by `instruments/piano/synth_rs.py`. Audio is returned as raw f64
//! little-endian bytes; the Python wrapper wraps them with numpy.frombuffer.

use engine::voice::Quality;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

fn quality_from_args(max_partials: Option<usize>, noise: bool, max_symp_lines: Option<usize>) -> Quality {
    Quality {
        max_partials: max_partials.unwrap_or(usize::MAX),
        noise,
        max_symp_lines: max_symp_lines.unwrap_or(usize::MAX),
    }
}

fn to_bytes<'py>(py: Python<'py>, y: &[f64]) -> Bound<'py, PyBytes> {
    let bytes = unsafe { std::slice::from_raw_parts(y.as_ptr() as *const u8, y.len() * 8) };
    PyBytes::new(py, bytes)
}

#[pyclass(unsendable)]
struct Piano {
    inner: engine::Piano,
}

#[pymethods]
impl Piano {
    #[new]
    #[pyo3(signature = (table_path, sr=48000, seed=1234))]
    fn new(table_path: &str, sr: usize, seed: u64) -> PyResult<Self> {
        engine::Piano::from_file(table_path, sr, seed)
            .map(|inner| Piano { inner })
            .map_err(PyValueError::new_err)
    }

    #[getter]
    fn sr(&self) -> usize {
        self.inner.sr
    }

    /// Limit rendering quality (None = unlimited/full).
    #[pyo3(signature = (max_partials=None, noise=true, max_symp_lines=None))]
    fn set_quality(&mut self, max_partials: Option<usize>, noise: bool, max_symp_lines: Option<usize>) {
        self.inner.quality = quality_from_args(max_partials, noise, max_symp_lines);
    }

    /// Render one note; returns raw little-endian f64 samples.
    #[pyo3(signature = (midi, velocity, dur=4.0, release_at=None, sustain_pedal=false))]
    fn synth_note<'py>(
        &mut self,
        py: Python<'py>,
        midi: i32,
        velocity: f64,
        dur: f64,
        release_at: Option<f64>,
        sustain_pedal: bool,
    ) -> Bound<'py, PyBytes> {
        let y = self
            .inner
            .synth_note(midi, velocity, dur, release_at, sustain_pedal);
        to_bytes(py, &y)
    }

    /// Interpolated synthesis parameters as JSON (for parity tests vs Python).
    fn note_params_json(&self, midi: i32, velocity: f64) -> String {
        serde_json::to_string(&self.inner.note_params(midi, velocity)).unwrap()
    }

    /// Measure this machine's throughput; returns JSON
    /// {sec_per_partial_sample, sec_per_voice_sample, partials_per_sec}.
    fn benchmark_json(&mut self) -> String {
        serde_json::to_string(&engine::bench::run(&mut self.inner)).unwrap()
    }

    /// Largest per-voice partial budget for `polyphony` voices within
    /// `cpu_fraction` of one core (runs the benchmark internally).
    fn pick_max_partials(&mut self, polyphony: usize, cpu_fraction: f64) -> usize {
        let b = engine::bench::run(&mut self.inner);
        engine::bench::pick_max_partials(&b, self.inner.sr, polyphony, cpu_fraction)
    }
}

/// Real-time streaming synth: note events in, buffers out.
#[pyclass(unsendable)]
struct StreamSynth {
    inner: engine::StreamSynth,
}

#[pymethods]
impl StreamSynth {
    #[new]
    #[pyo3(signature = (table_path, sr=48000, seed=1234))]
    fn new(table_path: &str, sr: usize, seed: u64) -> PyResult<Self> {
        engine::Piano::from_file(table_path, sr, seed)
            .map(|p| StreamSynth {
                inner: engine::StreamSynth::new(p),
            })
            .map_err(PyValueError::new_err)
    }

    #[getter]
    fn sr(&self) -> usize {
        self.inner.piano.sr
    }

    #[pyo3(signature = (max_partials=None, noise=true, max_symp_lines=None))]
    fn set_quality(&mut self, max_partials: Option<usize>, noise: bool, max_symp_lines: Option<usize>) {
        self.inner.piano.quality = quality_from_args(max_partials, noise, max_symp_lines);
    }

    fn note_on(&mut self, midi: i32, velocity: f64) {
        self.inner.note_on(midi, velocity);
    }

    fn note_off(&mut self, midi: i32) {
        self.inner.note_off(midi);
    }

    fn set_pedal(&mut self, down: bool) {
        self.inner.set_pedal(down);
    }

    fn all_notes_off(&mut self) {
        self.inner.all_notes_off();
    }

    fn active_voices(&self) -> usize {
        self.inner.active_voices()
    }

    /// Render `n_frames` samples; returns raw little-endian f64.
    fn render<'py>(&mut self, py: Python<'py>, n_frames: usize) -> Bound<'py, PyBytes> {
        let mut buf = vec![0.0f64; n_frames];
        self.inner.render(&mut buf);
        to_bytes(py, &buf)
    }
}

#[pymodule]
fn instrument_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Piano>()?;
    m.add_class::<StreamSynth>()?;
    Ok(())
}
