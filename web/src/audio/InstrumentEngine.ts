// Main-thread controller for the WASM instrument engine.
//
// Bundler-agnostic: it references the worklet, wasm, and params by absolute web
// paths (served from public/), so there is no ESM-in-worklet transform to trip
// over in Vite/Webpack/Capacitor. The worklet is self-contained; the main
// thread only compiles the wasm module and hands it to the worklet.
//
// Usage (must init/resume from a user gesture on mobile — see INTEGRATION.md):
//   const eng = new InstrumentEngine();
//   await eng.init();
//   await eng.resume();
//   await eng.setInstrument('piano');
//   eng.noteOn(60, 96); // middle C, velocity 96

export type InstrumentName = 'piano' | 'rhodes';

export interface InstrumentEngineOptions {
  /** URL of the self-contained worklet. Default '/instrument-worklet.js'. */
  workletUrl?: string;
  /** URL of the engine wasm binary. Default '/instrument_wasm_bg.wasm'. */
  wasmUrl?: string;
  /** Map instrument name -> params-table URL. Default `/params/<name>.json`. */
  paramsUrl?: (name: InstrumentName) => string;
}

export class InstrumentEngine {
  private ctx!: AudioContext;
  private master!: GainNode;
  private module!: WebAssembly.Module;
  private node?: AudioWorkletNode;

  private readonly workletUrl: string;
  private readonly wasmUrl: string;
  private readonly paramsUrl: (name: InstrumentName) => string;

  constructor(opts: InstrumentEngineOptions = {}) {
    this.workletUrl = opts.workletUrl ?? '/instrument-worklet.js';
    this.wasmUrl = opts.wasmUrl ?? '/instrument_wasm_bg.wasm';
    this.paramsUrl = opts.paramsUrl ?? ((n) => `/params/${n}.json`);
  }

  /** Compile wasm + register the worklet. Safe to call once. */
  async init(): Promise<void> {
    this.ctx = new AudioContext();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.7; // headroom; the engine render is un-clipped
    this.master.connect(this.ctx.destination);

    const bytes = await fetch(this.wasmUrl).then((r) => r.arrayBuffer());
    this.module = await WebAssembly.compile(bytes);
    await this.ctx.audioWorklet.addModule(this.workletUrl);
  }

  /** Resume the AudioContext. Call inside a click/touch handler on mobile. */
  async resume(): Promise<void> {
    if (this.ctx.state !== 'running') await this.ctx.resume();
  }

  get sampleRate(): number {
    return this.ctx.sampleRate;
  }

  /**
   * Swap the sounding instrument. Builds a fresh worklet node (the Synth is
   * constructed from the params table in its constructor), then disconnects
   * the previous one. The compiled wasm module is reused.
   */
  async setInstrument(name: InstrumentName): Promise<void> {
    const paramsJson = await fetch(this.paramsUrl(name)).then((r) => r.text());
    const node = new AudioWorkletNode(this.ctx, 'instrument-processor', {
      numberOfInputs: 0,
      numberOfOutputs: 1,
      outputChannelCount: [2],
      processorOptions: { module: this.module, paramsJson, seed: 0 },
    });
    node.connect(this.master);
    this.node?.port.postMessage({ type: 'allOff' });
    this.node?.disconnect();
    this.node = node;
  }

  noteOn(midi: number, velocity = 96): void {
    this.node?.port.postMessage({ type: 'noteOn', midi, velocity });
  }
  noteOff(midi: number): void {
    this.node?.port.postMessage({ type: 'noteOff', midi });
  }
  pedal(down: boolean): void {
    this.node?.port.postMessage({ type: 'pedal', down });
  }
  allOff(): void {
    this.node?.port.postMessage({ type: 'allOff' });
  }

  /** Master volume, 0..1. */
  setVolume(v: number): void {
    this.master.gain.value = v;
  }
}
