from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from strix_console_service.contracts import ProviderConfigRequest, ProviderModelsRequest
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


def test_runtime_adds_provider_prefix_to_manually_entered_model(tmp_path: Path) -> None:
    store = MemoryCredentialStore()
    service = ProviderService(
        config_path=tmp_path / "provider.json",
        credential_store=store,
    )
    service.configure(
        ProviderConfigRequest(
            provider="openai",
            model="deepseek-v4-pro",
            api_key="secret-provider-key",
        )
    )

    runtime = service.runtime()

    assert runtime is not None
    assert runtime.model == "openai/deepseek-v4-pro"


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


def test_model_discovery_uses_custom_anthropic_base_without_persisting_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = MemoryCredentialStore()
    service = ProviderService(
        config_path=tmp_path / "provider.json",
        credential_store=store,
    )
    captured: list[urllib.request.Request] = []

    class ModelsResponse:
        status = 200

        def __enter__(self) -> ModelsResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return b'{"data":[{"id":"claude-sonnet-4"},{"id":"claude-haiku-3"}]}'

    def open_request(request: urllib.request.Request, **_kwargs: object) -> ModelsResponse:
        captured.append(request)
        return ModelsResponse()

    monkeypatch.setattr(urllib.request, "urlopen", open_request)

    result = service.discover_models(
        ProviderModelsRequest(
            provider="anthropic",
            api_base="https://gateway.example.com/v1",
            api_key="write-only-key",
        )
    )

    assert result.models == ["claude-haiku-3", "claude-sonnet-4"]
    assert captured[0].full_url == "https://gateway.example.com/v1/models?limit=200"
    assert captured[0].headers["X-api-key"] == "write-only-key"
    assert store.values == {}
    assert not (tmp_path / "provider.json").exists()


def test_translation_sends_only_supplied_prose_and_parses_json(
    monkeypatch,
    tmp_path: Path,
) -> None:
    store = MemoryCredentialStore()
    service = ProviderService(config_path=tmp_path / "provider.json", credential_store=store)
    service.configure(
        ProviderConfigRequest(
            provider="openaiCompatible",
            model="deepseek-chat",
            api_base="https://api.example.com/v1",
            api_key="secret-key",
        )
    )
    captured: list[urllib.request.Request] = []

    class TranslationResponse:
        def __enter__(self) -> TranslationResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            content = json.dumps({"description": "需要普通用户权限。"})
            return json.dumps({"choices": [{"message": {"content": content}}]}).encode()

    def open_request(request: urllib.request.Request, **_kwargs: object) -> TranslationResponse:
        captured.append(request)
        return TranslationResponse()

    monkeypatch.setattr(urllib.request, "urlopen", open_request)

    result = service.translate_to_chinese({"description": "Requires a normal user."})

    assert result.description == "需要普通用户权限。"
    request = captured[0]
    assert request.full_url == "https://api.example.com/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret-key"
    body = json.loads(request.data or b"{}")
    assert body["model"] == "deepseek-chat"
    assert "Requires a normal user." in body["messages"][1]["content"]
    assert "evidence" not in body["messages"][1]["content"]
