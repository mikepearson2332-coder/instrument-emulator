//! Python binding for the engine — used by the lab (calibration/evaluation)
//! and by `instruments/piano/synth_rs.py`. Audio is returned as raw f64
//! little-endian bytes; the Python wrapper wraps them with numpy.frombuffer.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

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
        let bytes =
            unsafe { std::slice::from_raw_parts(y.as_ptr() as *const u8, y.len() * 8) };
        PyBytes::new(py, bytes)
    }

    /// Interpolated synthesis parameters as JSON (for parity tests vs Python).
    fn note_params_json(&self, midi: i32, velocity: f64) -> String {
        serde_json::to_string(&self.inner.note_params(midi, velocity)).unwrap()
    }
}

#[pymodule]
fn instrument_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Piano>()?;
    Ok(())
}
