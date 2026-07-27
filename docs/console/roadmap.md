# Strix Console Delivery Roadmap

## Delivery Rules

Implement one phase at a time from `develop`. Each phase uses a focused branch, contains tests and
documentation, passes applicable build/lint/type checks, and is merged before dependent work starts.
Do not combine phases in one commit or PR.

## Phase 1: Contracts and Skeleton

Scope:

- Create the independent console repository structure.
- Select and pin the frontend and control-service stack.
- Define scan states, API schemas, event envelope, IDs, and error model.
- Add formatter, lint, type-check, test, and CI commands.

Acceptance:

- Frontend and control service start locally.
- CI runs deterministic checks.
- API/event contracts are versioned and documented.
- No production capability or placeholder scan behavior is implied.

## Phase 2: Local Records

Scope:

- Implement a read-only `strix_runs/` indexer.
- Build `/local-runs` and `/local-runs/:id`.
- Parse completed, active, interrupted, partial, and malformed records.
- Download allowlisted existing artifacts.

Acceptance:

- Fixture directories cover every record state.
- A malformed run remains visible with a useful diagnostic.
- Refresh detects new or updated runs without restarting the service.
- No route can escape the configured runs root.

## Phase 3: Scan Control

Scope:

- Add environment readiness checks and the create-scan wizard.
- Validate authorization scope and runtime settings.
- Start Strix through a subprocess adapter.
- Implement lifecycle reconciliation and safe stop.

Acceptance:

- A valid configuration launches exactly one scan.
- Duplicate launch retries are idempotent.
- Stop targets only the selected run and produces a terminal state.
- Failed startup preserves diagnostics without creating a false running scan.

## Phase 4: Live Observability

Scope:

- Normalize and persist versioned events.
- Add resumable SSE and replay.
- Build Overview, Agents, Activity, Tools, Runtime, and steering interactions.
- Display usage, cost, errors, findings, and reconnecting state.

Acceptance:

- Refresh/reconnect does not duplicate or lose acknowledged events.
- Agent parent/child relationships remain stable.
- Large event streams remain responsive.
- Sensitive inputs and outputs are redacted before reaching the browser.

## Phase 5: Findings and Reports

Scope:

- Build live and historical finding details.
- Add cross-run filtering and severity summaries.
- Present evidence, PoC, affected locations, and remediation safely.
- Support JSON, SARIF, and PDF artifacts when present.

Acceptance:

- Finding identity and deduplication behavior are documented.
- Missing optional fields render as partial data, not errors.
- Downloads preserve exact stored artifacts and correct content types.
- Untrusted report content cannot execute in the console.

## Phase 6: Hardening and Release

Scope:

- Test process crashes, service restarts, Docker loss, rate limits, budget exhaustion, and corrupt
  local data.
- Add accessibility, responsive layouts, reduced motion, destructive confirmations, and audit
  diagnostics.
- Document installation, configuration, upgrade, backup, and release steps.

Acceptance:

- Critical flows have automated integration coverage.
- No secrets appear in logs, events, screenshots, or client storage.
- Local-only defaults are secure.
- A clean environment can install, launch, exercise, and remove the console using documented steps.

## Deferred Decisions

Multi-user tenancy, cloud deployment, scheduling, organization permissions, collaboration,
notifications, and true pause/resume require separate proposals. Do not introduce scaffolding for
them before requirements are approved.
