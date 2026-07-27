# Repository Guidelines

## Project Structure & Module Organization

The Python package lives in `strix/`, with core orchestration, agents, runtime backends, reporting,
tools, configuration, and CLI code in matching subpackages. Tests are focused modules in `tests/`.
Documentation lives in `docs/`, container assets in `containers/`, and helpers in `scripts/`. The
Vite/React viewer source is in `strix/viewer/frontend/`; its committed bundle is in
`strix/viewer/static/`.

## Build, Test, and Development Commands

- `make setup-dev`: install Python dependencies with `uv` and configure pre-commit hooks.
- `uv run strix --target https://example.com`: run the CLI from the working tree.
- `uv run pytest`: execute the full Python test suite; add a path such as
  `tests/test_models.py` for a focused run.
- `make check-all`: format, lint, type-check with mypy and Pyright, and run Bandit.
- `make pre-commit`: run every configured hook across the repository.
- `make viewer`: install frontend dependencies and rebuild `strix/viewer/static/`.

## Coding Style & Naming Conventions

Use four-space indentation, type hints on all functions, and docstrings for public APIs. Ruff
formats and lints Python with double quotes and a 100-character line limit. Use `snake_case` for
modules, functions, and variables; `PascalCase` for classes; and descriptive test names beginning
with `test_`. Follow existing React/TypeScript component conventions in the viewer.

## Testing Guidelines

Tests use `pytest` with `pytest-asyncio` in automatic mode. Add regression tests for behavior
changes and keep fixtures self-contained. No numeric coverage threshold is configured; exercise
success and failure paths.

## Branch, Commit & Pull Request Guidelines

Treat `main` as stable and releasable. Use `develop` for daily integration; branch `feat/<topic>`,
`fix/<topic>`, or `refactor/<topic>` from `develop` and merge back by PR. Create
`release/<version>` branches for release freezes. `main` accepts PRs only from `develop` or
`release/*`. Solo contributors may work directly on `develop` and merge completed phases to
`main`.

Write commits as `<type>: <中文简述>`, using lowercase `feat`, `fix`, `refactor`, `docs`, `test`,
`chore`, or `style`. Put one space after the colon, keep the summary under 50 Chinese characters,
and describe what changed and why. Keep one logical change per commit; add a body only when useful.

Open or link an issue, explain the change and motivation, include reproduction or before/after
evidence, and keep PRs focused. Before committing, run `uv run pytest` and `make check-all`; remove
debug output, dead commented code, and hard-coded local paths. Include screenshots for viewer
changes. Changes under `strix/viewer/frontend/` must include rebuilt `strix/viewer/static/` output.

## Security & Configuration

Never commit API keys or scan credentials. Configure providers through environment variables such
as `STRIX_LLM` and `LLM_API_KEY`, and use only targets you are authorized to test.

## Independent Console Product Scope

Build the new Strix control console as an independent project and repository. Do not extend or
import UI code from `strix/viewer/frontend/`; it may only be consulted for event formats, run-file
parsing, and existing behavior. The browser must communicate with a dedicated control service.
That service starts and stops Strix, reads local artifacts, protects credentials, and streams
structured events.

The console is organized around `Scan`, `Target`, `Agent`, `Event`, `ToolCall`, `Finding`,
`Runtime`, `Report`, and `SteeringMessage`. Its primary routes are:

- `/dashboard`: active scans, recent critical findings, environment health, and quick launch.
- `/scans/new`: target, scan strategy, model/runtime settings, authorization review, and launch.
- `/scans` and `/scans/:id`: task history plus Overview, Agents, Activity, Tools, Findings,
  Runtime, and Report views.
- `/local-runs` and `/local-runs/:id`: records discovered from `strix_runs/`, including active,
  completed, interrupted, malformed, and partial runs.
- `/findings`: findings aggregated across runs.
- `/settings` and `/system`: provider status, defaults, Docker/image health, versions, disk, and
  diagnostics.

Do not show a fabricated completion percentage for autonomous Agent work. Show the current phase,
completed milestones, last activity, active Agents, findings, elapsed time, token usage, and cost.
Use HTTP for commands and queries, SSE with resumable event IDs for live updates, and POST requests
for steering. Do not implement pause/resume until the engine supports real state restoration.
Local run files remain the source of truth; an optional SQLite index is only a rebuildable cache.

## Console Delivery Phases

Implement one verifiable phase at a time:

1. **Contracts and skeleton**: create the new repository, choose the frontend/control-service
   stack, define scan states and API/event schemas, and add CI checks.
2. **Local records**: index `strix_runs/`, build `/local-runs`, open partial or malformed records
   safely, and support report downloads. This phase is read-only.
3. **Scan control**: add environment checks, the create-scan wizard, subprocess isolation,
   start/stop behavior, and the console-owned state machine:
   `draft -> validating -> preparing -> running -> reporting -> completed`, with `failed`,
   `stopping`, and `stopped` exits.
4. **Live observability**: stream events, display Agent hierarchy, tool calls, errors, usage,
   findings, and steering. Reconnect without losing events.
5. **Findings and reports**: add cross-run filtering, finding details, PoC/evidence presentation,
   and JSON, SARIF, and PDF exports.
6. **Hardening**: test failure and restart paths, redact secrets, validate authorized targets,
   add destructive-action confirmations, accessibility, responsive behavior, and release docs.

Each phase uses a focused branch from `develop`, includes tests and documentation, passes its
applicable build/lint/type checks, and is merged before the next phase begins. Never mix multiple
phases into one commit or PR.
