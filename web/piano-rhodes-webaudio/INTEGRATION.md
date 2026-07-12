# Piano + Rhodes real-time audio — integration bundle

**For the AI assistant reading this in the target repo:** this folder is a
self-contained drop-in that adds a sample-free, real-time **piano** and
**Rhodes** synthesizer to a React app (built for a Capacitor Android WebView,
works in any modern browser). It was generated from a separate Rust
"instrument-model" project; you do **not** need that project to integrate this.
Everything required is in this folder.

**Status: verified working.** The exact files in this bundle were loaded in a
Vite + React app and both instruments produced audio through the real
AudioWorklet path (piano peak ≈ 0.37, Rhodes ≈ 0.12 at velocity 100, 48 kHz).

## What this is (and isn't)

- A WebAssembly build of a modal-synthesis engine + two small parameter tables.
  It **synthesizes** audio in real time from note events — there are **no audio
  sample files**. Payload ≈ 0.5 MB wasm + ~0.65 MB JSON params + a 15 KB worklet.
- Audio runs in an **AudioWorklet** (dedicated realtime thread). The main thread
  only compiles the wasm and sends note-on/off messages.
- It is **mono**, un-effected, and un-clipped at the source. A master `GainNode`
  (0.7) provides headroom. Add reverb/EQ/limiting downstream if you want.

## Architecture (why the files are shaped this way)

- `instrument-worklet.js` is **one self-contained script**: a tiny
  TextEncoder/TextDecoder polyfill + the wasm-bindgen glue (built
  `--target no-modules`) + the AudioWorkletProcessor. It has **no imports**, so
  it is served untransformed from `public/` and sidesteps every bundler's
  ESM-in-worklet pitfalls. (The polyfill matters: `AudioWorkletGlobalScope`
  lacks `TextEncoder`/`TextDecoder`, which wasm-bindgen needs to pass the params
  string into wasm — without it the worklet silently fails to register.)
- The main thread (`InstrumentEngine.ts`) never loads the glue. It just
  `fetch`es the `.wasm`, `WebAssembly.compile`s it, and hands the `Module` to
  the worklet via `processorOptions`. So there is nothing bundler-specific on
  the main thread either — all references are absolute web paths.

## Requirements

- **React**. Any bundler (Vite, Webpack, CRA) — nothing here is Vite-specific.
- A Chromium-based runtime. Capacitor's Android WebView qualifies.
- No special headers. No threads/SharedArrayBuffer, so **no** COOP/COEP.

## Install — copy two folders

| Bundle folder | Copy its **contents** into | Result |
|---|---|---|
| `copy-to-src/` | your app's `src/` | `src/audio/InstrumentEngine.ts`, `src/PianoDemo.tsx` |
| `copy-to-public/` | your app's `public/` | `public/instrument-worklet.js`, `public/instrument_wasm_bg.wasm`, `public/params/*.json` |

Final layout in the target app:

```
src/
  audio/InstrumentEngine.ts    # main-thread controller (public API)
  PianoDemo.tsx                # optional example; delete after wiring your own UI
public/
  instrument-worklet.js        # self-contained worklet (polyfill + glue + processor)
  instrument_wasm_bg.wasm       # engine binary
  params/
    piano.json
    rhodes.json
```

Everything in `public/` is served at the **web root** (`/instrument-worklet.js`,
`/instrument_wasm_bg.wasm`, `/params/piano.json`). `InstrumentEngine` fetches
those absolute paths by default. If your app serves static assets from a
sub-path, pass overrides to the constructor (see below) — do **not** move files
into `src/`, or the bundler will transform the worklet and break it.

## Wire it up

Fastest check — render the bundled example:

```tsx
import PianoDemo from './PianoDemo';
// ...
<PianoDemo />
```

Tap **Start audio**, then the keys. Switch Piano/Rhodes with the buttons.

For real use, drive `InstrumentEngine`:

```ts
import { InstrumentEngine } from './audio/InstrumentEngine';

const eng = new InstrumentEngine();
await eng.init();                 // compile wasm + register worklet (once)
await eng.resume();               // MUST be inside a user-gesture handler on mobile
await eng.setInstrument('piano'); // or 'rhodes'

eng.noteOn(60, 96);   // MIDI note 60 (middle C), velocity 1..127
eng.noteOff(60);
eng.pedal(true);      // sustain pedal down / up
eng.setVolume(0.8);   // master 0..1
eng.allOff();         // panic / release everything
```

If assets aren't at the web root, override paths:

```ts
new InstrumentEngine({
  workletUrl: '/assets/instrument-worklet.js',
  wasmUrl: '/assets/instrument_wasm_bg.wasm',
  paramsUrl: (name) => `/assets/params/${name}.json`,
});
```

### API (`InstrumentEngine`)

| Method | Notes |
|---|---|
| `init()` | Compiles the wasm module and registers the worklet. Call once. |
| `resume()` | Resumes the `AudioContext`. **Call from a click/touch handler** — mobile WebViews start audio suspended. |
| `setInstrument('piano' \| 'rhodes')` | Builds a fresh voice node for that params table. Cheap; safe to call to switch. |
| `noteOn(midi, velocity=96)` | `midi` 21..108 covers a piano; `velocity` 1..127. |
| `noteOff(midi)` | Respects the sustain pedal. |
| `pedal(down: boolean)` | Sustain. |
| `allOff()` | Release all voices. |
| `setVolume(0..1)` | Master gain. |
| `get sampleRate` | The live context rate the engine was built at. |

MIDI note numbers: 60 = C4 (middle C). Note `n` → `440 * 2**((n-69)/12)` Hz.

## Capacitor / Android specifics (already handled — just don't undo them)

- **User-gesture unlock.** Do not create the `AudioContext` or call `resume()`
  at module load. `PianoDemo` does both behind the "Start audio" button. On
  Android the first sound must originate from a tap.
- **Sample rate.** The engine is constructed with the live
  `AudioContext.sampleRate` (usually 48000 on Android), so there is no
  resampling and no pitch error. Do not hardcode 44100.
- **Asset serving.** Capacitor serves the bundle from `https://localhost`, so
  the `.wasm`, worklet, and `/params/*.json` are same-origin — plain `fetch`
  works, no CORS/headers needed.
- **Latency** is the WebView's output buffer (fine for a keyboard). The engine
  renders per 128-frame block.

## Level / clipping

`render` output is raw. Under heavy polyphony the mix can exceed ±1. If you hear
hard clipping, insert a soft-clipper before the destination — a
`WaveShaperNode` with a `tanh` curve — or lower `setVolume`.

## Provenance & updating

Generated from the "instrument-model" Rust project (modal synthesis; piano is
the same family as Pianoteq, Rhodes is a tine-EP model; params are fitted
tables, not recordings). Built with **wasm-bindgen 0.2.126** (`--target
no-modules`). To update the sound or add instruments, rebuild there
(`scripts/build_wasm.ps1`) and re-copy `instrument-worklet.js` +
`instrument_wasm_bg.wasm` + the new `params/*.json`. Any modal-family table
(woodblock, vibraphone, koto, jamblock, strings) loads through the same engine —
add the name to the `InstrumentName` union in `InstrumentEngine.ts` and stage
its JSON in `public/params/`. If you regenerate the wasm, the wasm-bindgen CLI
version must match the crate version, and keep the polyfill prepended.

## Troubleshooting

- **`AudioWorkletNode cannot be created: … 'instrument-processor' is not
  defined`** → the worklet script threw before registering. Almost always a
  missing global in `AudioWorkletGlobalScope`. This bundle's worklet already
  prepends a TextEncoder/TextDecoder polyfill; if you regenerated it, ensure the
  polyfill is still first in the file. Do **not** relocate the worklet into
  `src/` (bundler transforms will re-break it).
- **No sound, no errors** → `resume()` wasn't called from a user gesture, or the
  context is still suspended. Ensure the first call chain runs inside `onClick`.
- **404 on `/params/piano.json` or the worklet/wasm** → files weren't copied
  into `public/`, or the app's public root differs — pass path overrides to the
  `InstrumentEngine` constructor.
- **Wrong pitch / speed** → don't force a fixed `AudioContext` sample rate the
  hardware then overrides; let the engine use `AudioContext.sampleRate`.
