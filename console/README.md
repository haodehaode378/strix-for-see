# Strix Console Development

This directory contains the independent React/Tauri application and its loopback-only Python
control service. Phase 4 adds persistent versioned events, resumable live observation, bounded
steering, tray continuation, and local notifications on top of the Phase 3 scan controls. Docker
Desktop remains a user-installed prerequisite; the console detects it but never installs or
silently starts it.

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

## Local Configuration

The default writable record root is `%LOCALAPPDATA%\StrixConsole\runs`. Additional roots are
read-only and separated with Windows' `;` path separator:

```powershell
$env:STRIX_CONSOLE_RUN_ROOTS = "D:\strix_runs;E:\archive\strix_runs"
$env:STRIX_CONSOLE_STRIX_PATH = "C:\Program Files\Strix Console\strix.exe"
$env:STRIX_CONSOLE_SANDBOX_IMAGE = "ghcr.io/haodehaode378/strix-for-see-sandbox:latest"
```

`GET /api/system` and `POST /api/system/recheck` run bounded, non-mutating probes. Diagnostics from
`GET /api/system/diagnostics` redact common credential patterns and the user profile path.
`GET /api/local-runs` rescans configured roots on every request. Artifact downloads accept only
known Strix output filenames and cannot escape the indexed run directory.

## Scan Control

Configure and test a model provider in `/scans/new` before launching. API keys are written to
Windows Credential Manager under `StrixConsole/llm/<provider>`; they are not stored in
`provider.json`, queue state, run records, browser storage, or API responses.

`POST /api/scans` requires `X-Idempotency-Key` and explicit authorization. Full mode requires a
second confirmation. The queue is stored at
`%LOCALAPPDATA%\StrixConsole\state\scan-queue.json`, starts at most one process, and passes these
hard controls to the bundled runtime:

- one primary `--target`;
- native `--max-budget-usd` and scan profile;
- a validated internal `--run-name`;
- `STRIX_RUNS_DIR` for the console-owned run root;
- `STRIX_TELEMETRY=false`;
- safe-mode, scope, exclusion, and request-rate constraints ahead of operator instructions.

The control service enforces total duration and sends an interrupt for safe stop. Emergency
termination is a separately confirmed operation and targets only the tracked child handle.
Previously active queue entries are reconciled after a service restart and never reported as
success.

## Live Observability

Normalized events are appended under `%LOCALAPPDATA%\StrixConsole\state\events\<scan-id>.jsonl`
before delivery. `GET /api/scans/{id}/events` is an authenticated SSE stream; clients reconnect
with `Last-Event-ID` or `?after=` and receive only later events. Source keys make repeated reads of
`agents.json`, `agents.db`, `vulnerabilities.json`, and `run.json` idempotent.

Event payloads are bounded and redact authorization headers, cookies, credentials, tokens, and the
current user profile before reaching the browser. The live workspace retains at most 2,000 recent
events in memory and exposes Overview, Agents, Activity, Tools, and Runtime views.

`POST /api/scans/{id}/steering` accepts messages only while the scan is running. Messages containing
secret patterns or new targets are rejected, then accepted guidance is written to that run's local
`.state/console-steering.jsonl` inbox. Strix acknowledges each message after delivering it once to
the root Agent.

In desktop mode, closing the main window hides it to the system tray. The tray can reopen the
window, request a safe stop, or exit. Completion, failure, and critical-finding notifications are
shown only after the user grants notification permission.

## Desktop Development

Install dependencies once with `npm install`, then run:

```powershell
npm run tauri dev
```

The desktop shell starts independently. Automatic production sidecar launch and secure token
handoff remain release-packaging work; browser development can exercise scan control by starting
the loopback service explicitly.

## Checks

```powershell
npm run check
uv run --project control-service ruff check control-service
uv run --project control-service mypy
uv run --project control-service pytest
cargo check --manifest-path src-tauri/Cargo.toml
```
