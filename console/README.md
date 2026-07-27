# Strix Console Development

This directory contains the independent React/Tauri application and its loopback-only Python
control service. Phase 1 provides the application shell, language and theme foundations, typed
health contract, and in-memory session authentication. It does not run Strix scans.

## Prerequisites

- Node.js 22.12 or newer
- Rust with the Windows MSVC toolchain
- Python 3.12 or newer and `uv`
- Tauri's Windows prerequisites

## Browser Development

Use a development-only token in two PowerShell terminals:

```powershell
cd console/control-service
$env:STRIX_CONSOLE_ACCESS_TOKEN = "local-development-token"
uv sync
uv run strix-console-service
```

```powershell
cd console
$env:VITE_CONTROL_TOKEN = "local-development-token"
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Tokens remain in process memory; never add them to `.env` files.

## Desktop Development

Install dependencies once with `npm install`, then run:

```powershell
npm run tauri dev
```

The Phase 1 desktop shell starts independently. Automatic sidecar launch and secure token handoff
are release work and must be completed before scan controls are enabled.

## Checks

```powershell
npm run check
uv run --project control-service ruff check control-service
uv run --project control-service mypy
uv run --project control-service pytest
cargo check --manifest-path src-tauri/Cargo.toml
```
