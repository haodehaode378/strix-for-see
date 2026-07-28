from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from strix_console_service.contracts import ProviderConfigRequest
from strix_console_service.provider import ProviderService


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def set(self, name: str, value: str) -> None:
        self.values[name] = value


def test_provider_key_is_not_written_to_metadata_or_returned(tmp_path: Path) -> None:
    store = MemoryCredentialStore()
    config_path = tmp_path / "provider.json"
    service = ProviderService(config_path=config_path, credential_store=store)

    status = service.configure(
        ProviderConfigRequest(
            provider="openai",
            model="openai/gpt-5",
            api_key="secret-provider-key",
        )
    )

    metadata = json.loads(config_path.read_text(encoding="utf-8"))
    assert status.configured
    assert status.has_api_key
    assert "secret-provider-key" not in status.model_dump_json()
    assert "secret-provider-key" not in json.dumps(metadata)
    assert store.values["StrixConsole/llm/openai"] == "secret-provider-key"


def test_ollama_defaults_to_loopback_and_does_not_require_key(tmp_path: Path) -> None:
    service = ProviderService(
        config_path=tmp_path / "provider.json",
        credential_store=MemoryCredentialStore(),
    )

    status = service.configure(
        ProviderConfigRequest(provider="ollama", model="ollama/qwen3")
    )

    assert status.configured
    assert status.api_base == "http://127.0.0.1:11434/v1"
    assert not status.has_api_key


def test_successful_connectivity_check_marks_configuration_verified(
    monkeypatch,
    tmp_path: Path,
) -> None:
    service = ProviderService(
        config_path=tmp_path / "provider.json",
        credential_store=MemoryCredentialStore(),
    )
    service.configure(
        ProviderConfigRequest(provider="ollama", model="ollama/qwen3")
    )

    class SuccessfulResponse:
        status = 200

        def __enter__(self) -> SuccessfulResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: SuccessfulResponse(),
    )

    result = service.test_connectivity()

    assert result.ok
    assert service.status().connection_verified
