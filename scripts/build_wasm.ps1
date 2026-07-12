# Build the WASM instrument binding and stage a self-contained AudioWorklet
# (+ wasm + params tables) for the web app.
#
# Design: the worklet is built with wasm-bindgen `--target no-modules` and
# concatenated with web/worklet/processor-body.js into ONE plain script
# (web/public/instrument-worklet.js). It has no imports, so it's served
# untransformed from public/ and works in any bundler (Vite/Webpack/Capacitor)
# and inside AudioWorkletGlobalScope. The main thread never loads the glue — it
# only compiles the wasm and hands the Module to the worklet.
#
# Prereqs (one-time):
#   rustup target add wasm32-unknown-unknown
#   wasm-bindgen.exe on PATH, version-matched to core/wasm/Cargo.toml. On
#   Windows ARM64 wasm-pack/wasm-bindgen-cli won't build from source (a TLS dep
#   needs clang); use the official prebuilt from the rustwasm GitHub release.
#
# Output (all under web/public/, i.e. served at the web root):
#   instrument-worklet.js     self-contained worklet (glue + processor)
#   instrument_wasm_bg.wasm    the engine binary
#   params/{piano,rhodes}.json param tables the app fetches
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if (-not (Get-Command wasm-bindgen -ErrorAction SilentlyContinue)) {
    throw "wasm-bindgen not found on PATH. Install the prebuilt matching core/wasm/Cargo.toml's wasm-bindgen version from https://github.com/rustwasm/wasm-bindgen/releases"
}

# 1. Compile the crate to wasm.
cargo build -p instrument-wasm --release --target wasm32-unknown-unknown --manifest-path "$root\core\Cargo.toml"
if ($LASTEXITCODE -ne 0) { throw "cargo wasm build failed" }

# 2. Generate no-modules glue (defines a module-scope `wasm_bindgen`) + wasm.
$glueDir = "$root\core\target\wasmglue"
wasm-bindgen "$root\core\target\wasm32-unknown-unknown\release\instrument_wasm.wasm" `
    --out-dir $glueDir --out-name instrument_wasm --target no-modules
if ($LASTEXITCODE -ne 0) { throw "wasm-bindgen failed" }

# 3. Concatenate polyfills + glue + processor body into one self-contained
#    worklet. The polyfills (TextEncoder/TextDecoder) MUST come first — the
#    glue instantiates them at load, and AudioWorkletGlobalScope lacks them.
$publicDir = "$root\web\public"
New-Item -ItemType Directory -Force $publicDir | Out-Null
$poly = Get-Content "$root\web\worklet\polyfills.js" -Raw
$glue = Get-Content "$glueDir\instrument_wasm.js" -Raw
$body = Get-Content "$root\web\worklet\processor-body.js" -Raw
Set-Content -Path "$publicDir\instrument-worklet.js" -Value ($poly + "`n" + $glue + "`n" + $body) -Encoding utf8

# 4. Stage the wasm binary (main thread fetches + compiles it).
Copy-Item "$glueDir\instrument_wasm_bg.wasm" "$publicDir\instrument_wasm_bg.wasm" -Force

# 5. Stage the parameter tables. Add more instruments here as the bank grows;
#    each is just a JSON table fed to the same Synth.
$paramsOut = "$publicDir\params"
New-Item -ItemType Directory -Force $paramsOut | Out-Null
Copy-Item "$root\instruments\piano\params\grand.json"  "$paramsOut\piano.json"  -Force
Copy-Item "$root\instruments\rhodes\params\mk1.json"   "$paramsOut\rhodes.json" -Force

Write-Host "built web/public/{instrument-worklet.js, instrument_wasm_bg.wasm, params/{piano,rhodes}.json}"
