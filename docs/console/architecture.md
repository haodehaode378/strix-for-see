# Strix Console Technical Architecture

## System Boundary

```text
Tauri v2 desktop shell / local browser
  v
React + TypeScript console
  |-- HTTP commands and queries
  |-- resumable SSE events
  v
Bundled Python control-service sidecar
  |-- Scan Controller
  |-- Single-Scan Queue
  |-- Strix Process Adapter
  |-- Run Indexer
  |-- Event Normalizer
  |-- Report Reader
  v
Bundled Strix / external Docker Desktop / local run roots
```

The same frontend runs in desktop and browser modes. Business components call a platform adapter
instead of Tauri APIs directly: `DesktopAdapter` opens native dialogs and folders, while
`BrowserAdapter` requests equivalent operations from the local service where safe. The browser
never starts arbitrary processes, reads arbitrary paths, talks to Docker, or receives secrets.

The service binds only to `127.0.0.1`, generates a random access token on every start, and requires
it for HTTP and SSE. The desktop shell passes it to the current webview session. Local-browser
access uses an explicit one-time bootstrap and keeps the token in memory, never `localStorage`.
LAN binding and remote control are not supported.

## Packaging and Compatibility

Tauri bundles `control-service.exe` and a fixed Strix runtime as sidecars. Normal mode never
resolves Strix or Python from `PATH`; an explicit developer mode may point to a working tree. One
application version declares its compatible service, Strix, event schema, and sandbox-image range.
Docker Desktop and WebView2 remain platform prerequisites.

## Control-Service Responsibilities

- Validate targets, scope, model/runtime settings, budget, and authorization acknowledgement.
- Check Docker, WSL 2, virtualization, Git, sandbox image, disk, paths, and provider readiness.
- Queue tasks and enforce at most one active Strix process.
- Start Strix in an isolated subprocess and record its identity.
- Safe-stop or emergency-terminate only the resolved process and reconcile after service restart.
- Read run records and reports without treating partial writes as corruption.
- Normalize engine output into stable versioned events.
- Store secrets through Windows Credential Manager and redact credentials, authorization headers,
  cookies, certificates, usernames, and sensitive paths from browser responses and diagnostics.

## Lifecycle Model

The console owns this presentation state machine:

```text
draft -> validating -> queued -> preparing -> running -> reporting -> completed
             \-------------------------------> failed
running -> stopping -> stopped
running -> terminating -> terminated
```

Engine events and persisted artifacts drive transitions. Terminal states are immutable except for
metadata repair. A service restart must reconcile in-memory state with process existence and local
run files. Pause/resume is excluded until Strix can persist and restore Agent and sandbox state.

## API Shape

Initial endpoints:

```text
GET    /api/health
GET    /api/system
POST   /api/system/recheck
POST   /api/scans
GET    /api/scans
GET    /api/scans/{scan_id}
POST   /api/scans/{scan_id}/stop
POST   /api/scans/{scan_id}/terminate
POST   /api/scans/{scan_id}/steering
GET    /api/scans/{scan_id}/events
GET    /api/scans/{scan_id}/findings
PATCH  /api/findings/{finding_id}
GET    /api/local-runs
GET    /api/local-runs/{run_id}
GET    /api/local-runs/{run_id}/artifacts/{artifact}
```

Mutating requests use idempotency keys where retries could duplicate work. IDs are opaque and must
not be converted into filesystem paths by the browser.

## Event Contract

SSE events use monotonically increasing IDs within a scan:

```json
{
  "schemaVersion": 1,
  "eventId": "opaque-id",
  "scanId": "opaque-scan-id",
  "occurredAt": "ISO-8601 timestamp",
  "type": "tool.completed",
  "actor": {"kind": "agent", "id": "agent-id"},
  "payload": {}
}
```

Event types cover scan lifecycle, Agent lifecycle/messages, tool lifecycle, findings, usage,
steering, runtime health, and errors. Reconnection sends `Last-Event-ID`; the service replays later
events before resuming live delivery. Unknown event types are ignored safely and retained for
diagnostics.

## Local-Run Indexing

The indexer scans only configured run roots, resolves every candidate beneath its owning root, and
tolerates files being replaced while read. The default writable root is
`%LOCALAPPDATA%\StrixConsole\runs\`; added `strix_runs/` roots are read-only sources. Local
artifacts remain authoritative. SQLite may cache searchable metadata, but the cache is disposable
and rebuildable.

Readers expose explicit `queued`, `active`, `completed`, `interrupted`, `partial`, and `malformed`
states. They never hide a record solely because an optional artifact is absent. Downloads use an
allowlist of supported artifact names and content types. Deletion uses a Windows Recycle Bin
adapter after exact-path resolution and confirmation; removing a source never deletes its files.

## Frontend State

Server state is fetched and cached by scan/run ID. The SSE reducer applies events idempotently by
event ID. URL parameters own shareable filters and selected tabs; transient panel state remains
local. Long logs and tool outputs are virtualized and collapsed by default.

Every page implements loading, empty, stale, reconnecting, partial-data, and error states. Dynamic
status changes use accessible live regions and respect reduced-motion preferences.

User-facing strings use message keys and locale-aware date/number formatting. The initial locale
comes from Windows, while UI and report locale remain independent settings. Theme tokens support
dark, light, and Windows-derived modes.

## Updates and Runtime Images

The stable update manifest comes from GitHub Releases. Tauri, the sidecar, and Strix are one atomic
application version. Update checks are read-only; download and install require confirmation and are
blocked while a scan is active. Installation failure must leave the previous version runnable.

Sandbox images use separately versioned GHCR tags and a compatibility manifest. Pulls expose
download progress and disk estimates. Existing containers keep their resolved image, and cleanup of
old tags requires explicit confirmation.

## Security and Failure Rules

- Bind only to loopback and reject requests without the per-start token.
- Never log secrets or return raw environment variables.
- Validate authorized target scope server-side; user instructions cannot expand it.
- Full scan mode, terminate, data clearing, and delete actions require explicit confirmation.
- Render untrusted reports and tool output as inert content; never execute embedded scripts.
- Treat subprocess exit, Docker loss, provider rate limits, budget exhaustion, malformed records,
  and SSE disconnection as distinct observable errors.
- Preserve partial results after failure and make recovery actions explicit.
- Keep all application, scan, credential, log, diagnostic, and report data on the device.
