# Web / Capacitor integration (piano + rhodes, real-time)

Reference integration for running the instrument bank's Rust engine in a
browser / Capacitor WebView via WASM + an AudioWorklet. No audio samples ship —
only the `.wasm` binary and small params tables. The same code plays **piano**
and **rhodes** (and any future modal-family instrument); the instrument is
chosen entirely by which params JSON you load.

**Verified working** in a Vite + React app: both instruments produce audio
through the real AudioWorklet path. A ready-to-hand-off copy of the files below,
plus a self-contained integration guide, lives in
[`piano-rhodes-webaudio/`](piano-rhodes-webaudio) — drop that folder into any
target repo.

## Architecture

- **`worklet/`** (build inputs) — `polyfills.js` (TextEncoder/TextDecoder for
  `AudioWorkletGlobalScope`, which lacks them) + `processor-body.js` (the
  `AudioWorkletProcessor`). `build_wasm.ps1` concatenates these with the
  wasm-bindgen `--target no-modules` glue into one self-contained
  `public/instrument-worklet.js` with **no imports** — so it's served
  untransformed and works in any bundler and inside the worklet scope.
- **`src/audio/InstrumentEngine.ts`** — main-thread controller. Compiles the
  wasm (`WebAssembly.compile`) and hands the `Module` to the worklet; never
  loads the glue. References everything by absolute web path, so it's
  bundler-agnostic.
- **`public/`** (build outputs, gitignored) — `instrument-worklet.js`,
  `instrument_wasm_bg.wasm`, `params/{piano,rhodes}.json`.

## Build

```powershell
# one-time
rustup target add wasm32-unknown-unknown
# wasm-bindgen CLI on PATH, version-matched to core/wasm/Cargo.toml. On Windows
# ARM64, wasm-pack/wasm-bindgen-cli won't compile from source (a TLS dep needs
# clang); use the official prebuilt from the rustwasm GitHub release
# (x86_64-pc-windows-msvc runs under ARM64 emulation), verify its .sha256sum,
# and put wasm-bindgen.exe in ~/.cargo/bin.

# each time the engine or params change
scripts\build_wasm.ps1
```

Writes `web/public/{instrument-worklet.js, instrument_wasm_bg.wasm,
params/{piano,rhodes}.json}`.

## Wire into a React app (any bundler)

1. Copy `src/audio/InstrumentEngine.ts` (and `src/PianoDemo.tsx` for a demo)
   into your app's `src/`.
2. Copy `public/`'s contents into your app's `public/` (served at the web root).
3. Render `<PianoDemo />`, or use `InstrumentEngine` directly (see the API in
   [`piano-rhodes-webaudio/INTEGRATION.md`](piano-rhodes-webaudio/INTEGRATION.md)).

Nothing in the audio path uses the DOM, so it works identically in the browser
and inside a Capacitor Android WebView (Chromium).

## Capacitor gotchas (handled in the code, but know them)

- **User-gesture unlock.** Android WebViews start the `AudioContext` suspended.
  Create/resume it inside a tap handler — `PianoDemo` does this behind the
  "Start audio" button. Don't `new AudioContext()` at module load.
- **Sample rate.** The engine renders at whatever rate you construct it with; we
  pass the live `AudioContext.sampleRate` (usually 48000 on Android), so there's
  no resampling and no pitch shift. Don't hardcode 44100.
- **Serving assets.** `public/` files are fetched at runtime. In a Capacitor
  build they're served from the app bundle over `https://localhost` —
  same-origin, so plain `fetch` works. No CORS or COOP/COEP needed.
- **Latency.** Default WebAudio block is 128 frames (~2.7 ms @ 48 k). Fine for a
  keyboard. Under high polyphony, expose the engine's quality presets next.

## Level / clipping

`render` returns the engine's raw, un-clipped output. `InstrumentEngine` puts a
master `GainNode` at 0.7 for headroom. Under heavy polyphony add a soft-clipper
(`WaveShaperNode`, `tanh` curve) before the destination — the native `core/io`
layer does exactly this.

## Adding more instruments

Every modal-family table works with the same engine. To add e.g. vibraphone:

1. Stage its table in `build_wasm.ps1`
   (`instruments/vibraphone/params/vibes.json` → `web/public/params/vibes.json`).
2. Add the name to `InstrumentName` in `InstrumentEngine.ts`.

The **strings** instruments (`vln/vla/vc/cb`) use engine family 2
(`config.engine = "sustained"`), constructed through the same path — so they
load through this binding too, though they're voiced differently.
