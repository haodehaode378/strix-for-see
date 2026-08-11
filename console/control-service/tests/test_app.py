from pathlib import Path

from fastapi.testclient import TestClient

from strix_console_service.app import create_app
from strix_console_service.local_runs import RunRoot
from strix_console_service.provider import ProviderService

ACCESS_TOKEN = "test-access-token"
BOOTSTRAP_TOKEN = "test-bootstrap-token"


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


def test_health_requires_access_token() -> None:
    client = TestClient(create_app(access_token=ACCESS_TOKEN, bootstrap_token=BOOTSTRAP_TOKEN))

    unauthorized = client.get("/api/health")
    authorized = client.get(
        "/api/health",
        headers={"X-Strix-Access-Token": ACCESS_TOKEN},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {
        "status": "ok",
        "serviceVersion": "0.1.8",
        "schemaVersion": 1,
        "platform": "windows",
    }


def test_bootstrap_token_can_only_be_exchanged_once() -> None:
    client = TestClient(create_app(access_token=ACCESS_TOKEN, bootstrap_token=BOOTSTRAP_TOKEN))
    headers = {"X-Strix-Bootstrap": BOOTSTRAP_TOKEN}

    first = client.post("/api/session", headers=headers)
    second = client.post("/api/session", headers=headers)

    assert first.status_code == 200
    assert first.json() == {"accessToken": ACCESS_TOKEN}
    assert second.status_code == 401


def test_provider_api_never_returns_write_only_key(tmp_path: Path) -> None:
    provider = ProviderService(
        config_path=tmp_path / "state" / "provider.json",
        credential_store=MemoryCredentialStore(),
    )
    client = TestClient(
        create_app(
            access_token=ACCESS_TOKEN,
            bootstrap_token=BOOTSTRAP_TOKEN,
            run_roots=[RunRoot(tmp_path / "runs", writable=True)],
            provider_service=provider,
        )
    )

    response = client.post(
        "/api/provider",
        headers={"X-Strix-Access-Token": ACCESS_TOKEN},
        json={
            "provider": "openai",
            "model": "openai/gpt-5",
            "apiKey": "never-return-this-key",
        },
    )

    assert response.status_code == 200
    assert response.json()["hasApiKey"]
    assert "never-return-this-key" not in response.text
