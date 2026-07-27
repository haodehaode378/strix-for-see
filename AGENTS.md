# Repository Guidelines

## Project Structure

Python source lives in `strix/`, with orchestration, agents, runtimes, tools, reporting,
configuration, and CLI code grouped by subpackage. Tests live in `tests/`, documentation in
`docs/`, container assets in `containers/`, and helpers in `scripts/`. The existing viewer is under
`strix/viewer/frontend/`, with its generated bundle in `strix/viewer/static/`.

The new Strix Console lives in `console/` as an independent React/Tauri app with a Python control
service. Do not import or extend the existing viewer UI; consult it only for behavior, event
formats, and run-file parsing. Console requirements, architecture, and phases are in
`docs/console/`.

## Development Commands

- `make setup-dev`: install Python dependencies with `uv` and configure pre-commit.
- `uv run strix --target https://example.com`: run Strix from the working tree.
- `uv run pytest`: run all Python tests; append a test path for focused execution.
- `make check-all`: format, lint, type-check, and run security checks.
- `make pre-commit`: run all configured hooks.
- `make viewer`: rebuild the existing viewer and committed static bundle.

## Style and Testing

Use four-space Python indentation, type hints, and docstrings for public APIs. Ruff enforces double
quotes and a 100-character line limit. Name modules and functions in `snake_case`, classes in
`PascalCase`, and tests `test_<behavior>`. Add focused regression tests for behavior changes.

## Commits and Reviews

Work directly on `main` unless the user requests isolation or collaboration requires a branch.
Write commits as `<type>: <中文简述>` with a lowercase `feat`, `fix`, `refactor`, `docs`, `test`,
`chore`, or `style`. Keep the summary under 50 Chinese characters and each commit to one logical
change. Run relevant checks before pushing. If a PR is requested, explain motivation, link issues,
include evidence, and add screenshots for UI changes.

## Console and Security Rules

- Target Windows with one React UI for Tauri and a local browser.
- Support Simplified Chinese and English; never hard-code user-facing text.
- Keep the control service loopback-only. Do not add login, cloud sync, remote access, or telemetry.
- Store secrets in Windows Credential Manager and redact browser responses, logs, and diagnostics.
- Treat local run files as authoritative and indexes as disposable.
- Run one scan at a time; queue later tasks.
- Show phases and real activity, never fabricated completion percentages.
- Use HTTP for commands, resumable SSE for events, and POST for steering.
- Do not claim pause/resume without real state restoration.
- Never commit credentials, unauthorized target data, or `.ua/` artifacts.

See [product requirements](docs/console/product-requirements.md),
[technical architecture](docs/console/architecture.md), and
[delivery roadmap](docs/console/roadmap.md).
