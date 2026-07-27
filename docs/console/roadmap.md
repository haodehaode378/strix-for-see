# Strix Console Delivery Roadmap

## Delivery Rules

Implement one phase at a time on `main`. Use focused commits, include tests and documentation, and
pass applicable build/lint/type checks before pushing. Create a branch or pull request only when
explicitly requested or when isolated collaborative work requires it. Do not combine unrelated
phases in one commit.

## Phase 1: Contracts and Skeleton

Scope:

- Create the independent React/TypeScript, Tauri v2, and Python service structure.
- Package a development sidecar and add desktop/browser platform adapters.
- Define scan states, API schemas, event envelope, IDs, and error model.
- Add bilingual message catalogs, theme tokens, formatter, lint, type-check, test, and CI commands.

Acceptance:

- Desktop and local-browser frontends connect to the loopback service.
- A per-start token protects HTTP and SSE and is never persisted in browser storage.
- CI runs deterministic checks.
- API/event contracts are versioned and documented.
- No production capability or placeholder scan behavior is implied.

## Phase 2: Setup and Local Records

Scope:

- Build `/setup` and `/system/environment` with required and optional readiness checks.
- Implement the default writable run root plus read-only `strix_runs/` sources.
- Build `/local-runs` and `/local-runs/:id`.
- Parse completed, active, interrupted, partial, and malformed records.
- Download allowlisted existing artifacts.

Acceptance:

- Fixture directories cover every record state.
- A malformed run remains visible with a useful diagnostic.
- Refresh detects new or updated runs without restarting the service.
- No route can escape the configured runs root.
- Docker failure does not prevent record browsing.
- Copied or exported diagnostics are demonstrably redacted.

## Phase 3: Scan Control

Scope:

- Add the bilingual create-scan wizard for Web, local directory, public Git, and IP/domain targets.
- Configure providers through Windows Credential Manager and test model connectivity.
- Validate safe/full mode, authorization scope, credentials, rate, timeout, budget, and runtime.
- Add a persistent queue with one active scan.
- Start Strix through a subprocess adapter.
- Implement lifecycle reconciliation, safe stop, and confirmed emergency termination.

Acceptance:

- Each task has exactly one primary target and cannot expand beyond its authorized scope.
- A valid configuration launches exactly one scan; later tasks remain queued.
- Duplicate launch retries are idempotent.
- Stop targets only the selected run and produces a terminal state.
- Full mode and emergency termination require distinct confirmations.
- Failed startup preserves diagnostics without creating a false running scan.

## Phase 4: Live Observability

Scope:

- Normalize and persist versioned events.
- Add resumable SSE and replay.
- Build Overview, Agents, Activity, Tools, Runtime, and steering interactions.
- Display usage, cost, errors, findings, and reconnecting state.
- Add system-tray continuation and Windows completion/failure/critical-finding notifications.

Acceptance:

- Refresh/reconnect does not duplicate or lose acknowledged events.
- Agent parent/child relationships remain stable.
- Large event streams remain responsive.
- Sensitive inputs and outputs are redacted before reaching the browser.

## Phase 5: Findings and Reports

Scope:

- Build live and historical finding details.
- Add local workflow states, notes, history, cross-run filtering, and severity summaries.
- Present evidence, PoC, affected locations, and remediation safely.
- Export HTML, PDF, Markdown, and JSON in Chinese or English with redaction options.

Acceptance:

- Finding identity and deduplication behavior are documented.
- Workflow transitions and note history persist locally.
- Missing optional fields render as partial data, not errors.
- Exports use correct content types and omit selected sensitive fields.
- Untrusted report content cannot execute in the console.

## Phase 6: Hardening and Release

Scope:

- Test process crashes, service restarts, Docker loss, rate limits, budget exhaustion, and corrupt
  local data.
- Add accessibility, responsive layouts, reduced motion, destructive confirmations, and audit
  diagnostics.
- Package the Windows installer and document Docker Desktop, SmartScreen, configuration, upgrade,
  uninstall, and release steps.
- Add confirmed stable updates from GitHub Releases and separate compatible Sandbox updates from
  GHCR.

Acceptance:

- Critical flows have automated integration coverage.
- No secrets appear in logs, events, screenshots, or client storage.
- Local-only defaults are secure.
- A clean environment can install, launch, exercise, and remove the console using documented steps.
- Application updates preserve a working version on failure and never run during a scan.
- Sandbox pulls show version, size, progress, and never remove old images without confirmation.

## Deferred Scope

Multi-user tenancy, login, cloud deployment or sync, remote/LAN access, telemetry, private Git
credentials, scheduling, multiple concurrent scans, portable distribution, scan archive
import/export, organization collaboration, and true pause/resume require separate proposals. Do
not introduce scaffolding for them before requirements are approved.
