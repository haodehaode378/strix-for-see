from pathlib import Path

from strix.core.paths import run_dir_for, runs_base_dir


def test_explicit_runs_directory_is_used(
    monkeypatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "console-runs"
    monkeypatch.setenv("STRIX_RUNS_DIR", str(configured))

    assert runs_base_dir() == configured.resolve()
    assert run_dir_for("console-scan") == configured.resolve() / "console-scan"


def test_explicit_cwd_ignores_runs_directory_override(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STRIX_RUNS_DIR", str(tmp_path / "console-runs"))

    assert runs_base_dir(cwd=tmp_path) == tmp_path / "strix_runs"
