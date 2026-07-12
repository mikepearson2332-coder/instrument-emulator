// AudioWorkletProcessor body. build_wasm.ps1 concatenates this AFTER the
// wasm-bindgen `--target no-modules` glue to produce a single self-contained
// `instrument-worklet.js` (no imports), served untransformed from public/.
// The glue above defined a module-scope `wasm_bindgen`; pull the API off it.
//
// This file is not used directly — edit it here, then run build_wasm.ps1.

const { initSync, Synth } = wasm_bindgen;

class InstrumentProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const { module, paramsJson, seed } = options.processorOptions;
    // no-modules initSync also takes the { module } object form.
    initSync({ module });
    // seed is a Rust u64 -> JS BigInt at the boundary.
    // `sampleRate` is a global in AudioWorkletGlobalScope.
    this.synth = new Synth(paramsJson, sampleRate, BigInt(seed ?? 0));
    this.port.onmessage = (e) => this.handle(e.data);
  }

  handle(msg) {
    switch (msg.type) {
      case 'noteOn':  this.synth.note_on(msg.midi, msg.velocity); break;
      case 'noteOff': this.synth.note_off(msg.midi); break;
      case 'pedal':   this.synth.set_pedal(msg.down); break;
      case 'allOff':  this.synth.all_notes_off(); break;
    }
  }

  process(_inputs, outputs) {
    const out = outputs[0];
    if (out.length === 0) return true;
    // Engine is mono: render into channel 0, then mirror to the rest.
    this.synth.render(out[0]);
    for (let c = 1; c < out.length; c++) out[c].set(out[0]);
    return true; // keep the processor alive
  }
}

registerProcessor('instrument-processor', InstrumentProcessor);
