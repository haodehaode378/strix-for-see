from __future__ import annotations

from pathlib import Path

from strix_console_service.system_checks import CommandResult, SystemInspector, redact_text


def _which(command: str) -> str | None:
    paths = {
        "docker": "C:/tools/docker.exe",
        "git": "C:/tools/git.exe",
        "wsl": "C:/Windows/System32/wsl.exe",
    }
    return paths.get(command)


def _successful_command(command: list[str]) -> CommandResult:
    if "--version" in command:
        return CommandResult(return_code=0, stdout="git version 2.51.0")
    if "info" in command:
        return CommandResult(return_code=0, stdout="28.3.2")
    return CommandResult(return_code=0, stdout="available")


def test_system_report_separates_required_and_optional_checks(tmp_path: Path) -> None:
    inspector = SystemInspector(
        run_root=tmp_path,
        environment={
            "STRIX_CONSOLE_STRIX_PATH": str(tmp_path),
            "STRIX_LLM": "openai/gpt-5",
            "OPENAI_API_KEY": "not-returned",
        },
        command_runner=_successful_command,
        which=_which,
        platform_name="win32",
    )

    report = inspector.inspect()

    assert report.summary.ready
    assert report.summary.required_failures == 0
    assert {check.id for check in report.checks if check.requirement == "optional"} == {
        "wsl",
        "git",
        "sandbox",
        "provider",
    }
    assert all("not-returned" not in (check.value or "") for check in report.checks)


def test_missing_docker_is_reported_without_raising(tmp_path: Path) -> None:
    inspector = SystemInspector(
        run_root=tmp_path,
        environment={"STRIX_CONSOLE_STRIX_PATH": str(tmp_path)},
        which=lambda _command: None,
        platform_name="win32",
    )

    report = inspector.inspect()
    checks = {check.id: check for check in report.checks}

    assert not report.summary.ready
    assert checks["dockerCli"].status == "missing"
    assert checks["dockerDaemon"].issue == "dockerCliMissing"
    assert checks["sandbox"].status == "warning"


def test_redaction_removes_home_and_common_secret_forms(tmp_path: Path) -> None:
    text = (
        f"path={tmp_path}\\runs "
        "Authorization: Bearer abc.def "
        "OPENAI_API_KEY=sk-1234567890 "
        'password="do-not-copy"'
    )

    redacted = redact_text(text, home=tmp_path)

    assert str(tmp_path) not in redacted
    assert "abc.def" not in redacted
    assert "sk-1234567890" not in redacted
    assert "do-not-copy" not in redacted
    assert "[REDACTED]" in redacted
