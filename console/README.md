# Strix Console Development

This directory contains the independent React/Tauri application and its loopback-only Python
control service. Phase 2 adds read-only device readiness checks, a disposable local-run index,
record details, and allowlisted artifact downloads. It does not run Strix scans or start Docker.

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

## Phase 2 Configuration

The default writable record root is `%LOCALAPPDATA%\StrixConsole\runs`. Additional roots are
read-only and separated with Windows' `;` path separator:

```powershell
$env:STRIX_CONSOLE_RUN_ROOTS = "D:\strix_runs;E:\archive\strix_runs"
$env:STRIX_CONSOLE_STRIX_PATH = "C:\Program Files\Strix Console\strix"
$env:STRIX_CONSOLE_SANDBOX_IMAGE = "ghcr.io/haodehaode378/strix-for-see-sandbox:latest"
```

`GET /api/system` and `POST /api/system/recheck` run bounded, non-mutating probes. Diagnostics from
`GET /api/system/diagnostics` redact common credential patterns and the user profile path.
`GET /api/local-runs` rescans configured roots on every request. Artifact downloads accept only
known Strix output filenames and cannot escape the indexed run directory.

## Desktop Development

Install dependencies once with `npm install`, then run:

```powershell
npm run tauri dev
```

The desktop shell starts independently. Automatic sidecar launch and secure token handoff
are release work and must be completed before scan controls are enabled.

## Checks

```powershell
npm run check
uv run --project control-service ruff check control-service
uv run --project control-service mypy
uv run --project control-service pytest
cargo check --manifest-path src-tauri/Cargo.toml
```
