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

Use `main` for normal solo development and push focused, verified commits directly. Create
`feat/<topic>`, `fix/<topic>`, or `refactor/<topic>` branches only when the user requests a branch,
the work needs isolation, or multiple contributors are involved. Pull requests are optional unless
explicitly requested.

Write commits as `<type>: <中文简述>`, using lowercase `feat`, `fix`, `refactor`, `docs`, `test`,
`chore`, or `style`. Put one space after the colon, keep the summary under 50 Chinese characters,
and describe what changed and why. Keep one logical change per commit; add a body only when useful.

Before committing, explain the change and motivation, run relevant checks, and remove debug output,
dead commented code, and hard-coded local paths. When a PR is used, keep it focused, link applicable
issues, and include reproduction or before/after evidence. Include screenshots for viewer changes.
Changes under `strix/viewer/frontend/` must include rebuilt `strix/viewer/static/` output.

## Security & Configuration

Never commit API keys or scan credentials. Configure providers through environment variables such
as `STRIX_LLM` and `LLM_API_KEY`, and use only targets you are authorized to test.

## Independent Console Guardrails

The new Strix control console is an independent project. Do not extend or import UI code from
`strix/viewer/frontend/`; consult it only for existing behavior, event formats, and run-file
parsing. Keep these invariants:

- The browser communicates with a dedicated control service and never receives provider secrets.
- Local files under `strix_runs/` are the source of truth; indexes must be rebuildable.
- Show phases, milestones, activity, findings, elapsed time, usage, and cost instead of a fabricated
  completion percentage.
- Use HTTP for commands and queries, resumable SSE for live events, and POST for steering.
- Do not claim pause/resume until the engine supports real state restoration.
- Never commit `.ua/` analysis artifacts.

Console details are maintained separately:

- [Product requirements](docs/console/product-requirements.md)
- [Technical architecture](docs/console/architecture.md)
- [Delivery roadmap](docs/console/roadmap.md)
