# Strix Console Technical Architecture

## System Boundary

```text
React Console
  |-- HTTP commands and queries
  |-- resumable SSE events
  v
Control Service
  |-- Scan Controller
  |-- Strix Process Adapter
  |-- Run Indexer
  |-- Event Normalizer
  |-- Report Reader
  v
Strix CLI / Docker Sandbox / strix_runs/
```

The browser never starts processes, reads arbitrary local paths, talks directly to Docker, or
receives API keys. The control service owns those capabilities and exposes a narrow typed API.

## Control-Service Responsibilities

- Validate targets, scope, model/runtime settings, budget, and authorization acknowledgement.
- Check Strix, Docker, sandbox image, disk, and provider readiness.
- Start Strix in an isolated subprocess and record its identity.
- Stop only the resolved process and reconcile interrupted processes after service restart.
- Read run records and reports without treating partial writes as corruption.
- Normalize engine output into stable versioned events.
- Redact credentials, authorization headers, cookies, and sensitive tool output.

## Lifecycle Model

The console owns this presentation state machine:

```text
draft -> validating -> preparing -> running -> reporting -> completed
                     \-> failed
running -> stopping -> stopped
```

Engine events and persisted artifacts drive transitions. Terminal states are immutable except for
metadata repair. A service restart must reconcile in-memory state with process existence and local
run files. Pause/resume is excluded until Strix can persist and restore Agent and sandbox state.

## API Shape

Initial endpoints:

```text
GET    /api/health
GET    /api/system
POST   /api/scans
GET    /api/scans
GET    /api/scans/{scan_id}
POST   /api/scans/{scan_id}/stop
POST   /api/scans/{scan_id}/steering
GET    /api/scans/{scan_id}/events
GET    /api/scans/{scan_id}/findings
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

The indexer scans only the configured `strix_runs/` root, resolves every candidate beneath that
root, and tolerates files being replaced while read. Local artifacts remain authoritative. SQLite
may cache searchable metadata, but the cache must be disposable and rebuildable.

Readers expose explicit `active`, `completed`, `interrupted`, `partial`, and `malformed` states.
They never hide a record solely because an optional artifact is absent. Downloads use an allowlist
of supported artifact names and content types.

## Frontend State

Server state is fetched and cached by scan/run ID. The SSE reducer applies events idempotently by
event ID. URL parameters own shareable filters and selected tabs; transient panel state remains
local. Long logs and tool outputs are virtualized and collapsed by default.

Every page implements loading, empty, stale, reconnecting, partial-data, and error states. Dynamic
status changes use accessible live regions and respect reduced-motion preferences.

## Security and Failure Rules

- Bind locally by default; remote binding requires authentication and explicit configuration.
- Never log secrets or return raw environment variables.
- Validate authorized target scope server-side; user instructions cannot expand it.
- Stop and delete actions require exact resource resolution and confirmation.
- Treat subprocess exit, Docker loss, provider rate limits, budget exhaustion, malformed records,
  and SSE disconnection as distinct observable errors.
- Preserve partial results after failure and make recovery actions explicit.
