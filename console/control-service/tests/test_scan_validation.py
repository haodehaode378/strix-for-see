from __future__ import annotations

from pathlib import Path

import pytest

from strix_console_service.contracts import CreateScanRequest
from strix_console_service.scan_validation import (
    ScanValidationError,
    validate_scan_request,
    validate_steering_message,
)


def _request(**updates: object) -> CreateScanRequest:
    values: dict[str, object] = {
        "targetType": "web",
        "target": "https://example.com",
        "scope": {
            "allowedHosts": ["api.example.com"],
            "allowedPorts": [443],
            "allowedPaths": ["/api"],
            "exclusions": ["/logout"],
        },
        "options": {
            "riskMode": "safe",
            "scanProfile": "standard",
            "requestRatePerMinute": 30,
            "maxDurationMinutes": 60,
            "maxBudgetUsd": 10,
            "instructions": "Focus on access control.",
        },
        "authorizationConfirmed": True,
        "fullModeConfirmed": False,
    }
    values.update(updates)
    return CreateScanRequest.model_validate(values)


def test_web_scan_is_normalized_and_gets_immutable_constraints() -> None:
    validated = validate_scan_request(_request())

    assert validated.engine_target == "https://example.com"
    assert validated.request.scope.allowed_hosts == ["api.example.com"]
    assert "Primary target: https://example.com" in validated.constraint_instruction
    assert "safe mode" in validated.constraint_instruction
    assert "cannot add targets" in validated.constraint_instruction


@pytest.mark.parametrize(
    ("updates", "code"),
    [
        ({"authorizationConfirmed": False}, "authorizationRequired"),
        (
            {
                "options": {
                    "riskMode": "full",
                    "scanProfile": "deep",
                    "requestRatePerMinute": 30,
                    "maxDurationMinutes": 60,
                    "maxBudgetUsd": 10,
                },
            },
            "fullModeConfirmationRequired",
        ),
        (
            {
                "options": {
                    "riskMode": "safe",
                    "scanProfile": "standard",
                    "requestRatePerMinute": 30,
                    "maxDurationMinutes": 60,
                    "maxBudgetUsd": 10,
                    "instructions": "Use token=do-not-store",
                },
            },
            "instructionsContainSecret",
        ),
        ({"target": "https://user:secret@example.com"}, "invalidTargetUrl"),
        ({"target": "https://example.com/?token=secret"}, "targetContainsSecret"),
    ],
)
def test_scan_validation_rejects_unsafe_requests(
    updates: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(ScanValidationError, match=code):
        validate_scan_request(_request(**updates))


def test_local_target_must_be_a_bounded_existing_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    validated = validate_scan_request(
        _request(targetType="local", target=str(source))
    )

    assert validated.engine_target == str(source.resolve())


def test_public_repository_rejects_local_network_url() -> None:
    with pytest.raises(ScanValidationError, match="repositoryMustBePublic"):
        validate_scan_request(
            _request(targetType="repository", target="https://127.0.0.1/repo.git")
        )


def test_steering_rejects_secrets_and_out_of_scope_targets() -> None:
    request = _request()

    with pytest.raises(ScanValidationError, match="steeringContainsSecret"):
        validate_steering_message(request, "Use token=super-secret-value")
    with pytest.raises(ScanValidationError, match="steeringExpandsScope"):
        validate_steering_message(request, "Also inspect https://outside.example.net")

    assert (
        validate_steering_message(request, "Re-check https://example.com/login")
        == "Re-check https://example.com/login"
    )
