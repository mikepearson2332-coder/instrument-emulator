# Build the Rust core and stage the Python extension module.
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
cargo build --release --manifest-path "$root\core\Cargo.toml"
if ($LASTEXITCODE -ne 0) { throw "cargo build failed" }
New-Item -ItemType Directory -Force "$root\core\dist" | Out-Null
Copy-Item "$root\core\target\release\instrument_core.dll" "$root\core\dist\instrument_core.pyd" -Force
Write-Host "built core/dist/instrument_core.pyd"
