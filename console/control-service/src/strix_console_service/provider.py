from __future__ import annotations

import ctypes
import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from strix_console_service.contracts import (
    ProviderConfigRequest,
    ProviderKind,
    ProviderModelsRequest,
    ProviderModelsResponse,
    ProviderStatus,
    ProviderTestResult,
)

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class CredentialStore(Protocol):
    """Minimal secret-store boundary."""

    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...


class ProviderConfigurationError(ValueError):
    """Stable provider configuration failure."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _CredentialAttributeW(ctypes.Structure):
    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class _CredentialW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.POINTER(_CredentialAttributeW)),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialStore:
    """Store provider keys in Windows Credential Manager as generic credentials."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows Credential Manager is unavailable")
        self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._advapi.CredWriteW.argtypes = [ctypes.POINTER(_CredentialW), wintypes.DWORD]
        self._advapi.CredWriteW.restype = wintypes.BOOL
        self._advapi.CredReadW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_CredentialW)),
        ]
        self._advapi.CredReadW.restype = wintypes.BOOL
        self._advapi.CredFree.argtypes = [ctypes.c_void_p]
        self._advapi.CredFree.restype = None

    def get(self, name: str) -> str | None:
        pointer = ctypes.POINTER(_CredentialW)()
        if not self._advapi.CredReadW(name, _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.get_last_error()
            if error == _ERROR_NOT_FOUND:
                return None
            raise OSError(error, "CredReadW failed")
        try:
            credential = pointer.contents
            blob = ctypes.string_at(
                credential.CredentialBlob,
                credential.CredentialBlobSize,
            )
            return blob.decode("utf-16-le")
        finally:
            self._advapi.CredFree(pointer)

    def set(self, name: str, value: str) -> None:
        encoded = value.encode("utf-16-le")
        buffer = ctypes.create_string_buffer(encoded)
        credential = _CredentialW()
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = name
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "Strix Console"
        if not self._advapi.CredWriteW(ctypes.byref(credential), 0):
            error = ctypes.get_last_error()
            raise OSError(error, "CredWriteW failed")


class EnvironmentCredentialStore:
    """Read-only fallback for developer environments outside Windows."""

    def __init__(self, environment: Mapping[str, str] | None = None) -> None:
        self.environment = environment if environment is not None else os.environ

    def get(self, _name: str) -> str | None:
        return self.environment.get("LLM_API_KEY") or self.environment.get("OPENAI_API_KEY")

    def set(self, _name: str, _value: str) -> None:
        raise OSError("Windows Credential Manager is unavailable")


@dataclass(frozen=True)
class ProviderRuntime:
    """Secret-bearing runtime settings used only to construct a child environment."""

    provider: ProviderKind
    model: str
    api_base: str | None
    api_key: str | None


@dataclass(frozen=True)
class _ProviderMetadata:
    provider: ProviderKind
    model: str
    api_base: str | None
    connection_verified: bool


class ProviderService:
    """Persist non-secret provider metadata and keep API keys in Credential Manager."""

    def __init__(
        self,
        *,
        config_path: Path,
        credential_store: CredentialStore,
    ) -> None:
        self.config_path = config_path
        self.credential_store = credential_store

    def status(self) -> ProviderStatus:
        metadata = self._read_metadata()
        if metadata is None:
            return ProviderStatus(configured=False)
        provider = metadata.provider
        key = self._read_key(provider)
        requires_key = provider != "ollama"
        return ProviderStatus(
            configured=bool(metadata.model and (key or not requires_key)),
            provider=provider,
            model=metadata.model,
            api_base=metadata.api_base,
            has_api_key=bool(key),
            connection_verified=metadata.connection_verified,
        )

    def configure(self, request: ProviderConfigRequest) -> ProviderStatus:
        api_base = _validate_api_base(request.provider, request.api_base)
        model = request.model.strip()
        if not model:
            raise ProviderConfigurationError("modelRequired")
        if request.provider != "ollama" and not (
            request.api_key or self._read_key(request.provider)
        ):
            raise ProviderConfigurationError("apiKeyRequired")
        if request.api_key:
            self.credential_store.set(
                self._credential_name(request.provider),
                request.api_key,
            )
        self._write_metadata(
            {
                "provider": request.provider,
                "model": model,
                "api_base": api_base,
                "connection_verified": False,
            }
        )
        return self.status()

    def runtime(self) -> ProviderRuntime | None:
        metadata = self._read_metadata()
        if metadata is None:
            return None
        provider = metadata.provider
        key = self._read_key(provider)
        if provider != "ollama" and not key:
            return None
        return ProviderRuntime(
            provider=provider,
            model=metadata.model,
            api_base=metadata.api_base,
            api_key=key,
        )

    def test_connectivity(self) -> ProviderTestResult:
        runtime = self.runtime()
        if runtime is None:
            return ProviderTestResult(ok=False, issue="notConfigured")
        request = _connectivity_request(runtime)
        try:
            with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310
                if 200 <= response.status < 300:
                    self._mark_verified()
                    return ProviderTestResult(ok=True)
                return ProviderTestResult(ok=False, issue="providerRejected")
        except urllib.error.HTTPError as error:
            issue = "authenticationFailed" if error.code in {401, 403} else "providerRejected"
            return ProviderTestResult(ok=False, issue=issue)
        except (OSError, urllib.error.URLError, TimeoutError):
            return ProviderTestResult(ok=False, issue="connectionFailed")

    def discover_models(self, request: ProviderModelsRequest) -> ProviderModelsResponse:
        """Fetch a bounded model list using write-only or previously stored credentials."""

        api_base = _validate_api_base(request.provider, request.api_base)
        api_key = request.api_key or self._read_key(request.provider)
        if request.provider != "ollama" and not api_key:
            raise ProviderConfigurationError("apiKeyRequired")
        runtime = ProviderRuntime(
            provider=request.provider,
            model="",
            api_base=api_base,
            api_key=api_key,
        )
        provider_request = _connectivity_request(runtime, model_limit=200)
        try:
            with urllib.request.urlopen(provider_request, timeout=8) as response:  # noqa: S310
                payload = json.loads(response.read(1_048_577))
        except urllib.error.HTTPError as error:
            code = "authenticationFailed" if error.code in {401, 403} else "providerRejected"
            raise ProviderConfigurationError(code) from error
        except (OSError, urllib.error.URLError, TimeoutError) as error:
            raise ProviderConfigurationError("connectionFailed") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProviderConfigurationError("invalidProviderResponse") from error
        return ProviderModelsResponse(models=_extract_model_ids(request.provider, payload))

    def _read_metadata(self) -> _ProviderMetadata | None:
        if not self.config_path.is_file():
            return None
        try:
            value = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        provider = value.get("provider")
        model = value.get("model")
        api_base = value.get("api_base")
        if provider not in {
            "openai",
            "anthropic",
            "gemini",
            "openaiCompatible",
            "ollama",
        } or not isinstance(model, str):
            return None
        return _ProviderMetadata(
            provider=provider,
            model=model,
            api_base=api_base if isinstance(api_base, str) else None,
            connection_verified=value.get("connection_verified") is True,
        )

    def _write_metadata(self, value: dict[str, str | bool | None]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.config_path)

    @staticmethod
    def _credential_name(provider: str) -> str:
        return f"StrixConsole/llm/{provider}"

    def _read_key(self, provider: str) -> str | None:
        try:
            return self.credential_store.get(self._credential_name(provider))
        except OSError:
            return None

    def _mark_verified(self) -> None:
        metadata = self._read_metadata()
        if metadata is None:
            return
        self._write_metadata(
            {
                "provider": metadata.provider,
                "model": metadata.model,
                "api_base": metadata.api_base,
                "connection_verified": True,
            }
        )


def default_credential_store() -> CredentialStore:
    """Return Credential Manager on Windows and an environment-only developer fallback."""

    if os.name == "nt":
        return WindowsCredentialStore()
    return EnvironmentCredentialStore()


def _validate_api_base(provider: ProviderKind, value: str | None) -> str | None:
    if provider == "ollama" and not value:
        return "http://127.0.0.1:11434/v1"
    if provider == "openaiCompatible" and not value:
        raise ProviderConfigurationError("apiBaseRequired")
    if not value:
        return None
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if not parsed.hostname or parsed.username or parsed.password:
        raise ProviderConfigurationError("invalidApiBase")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ProviderConfigurationError("invalidApiBase")
    if parsed.query or parsed.fragment:
        raise ProviderConfigurationError("invalidApiBase")
    return normalized


def _connectivity_request(
    runtime: ProviderRuntime,
    *,
    model_limit: int = 1,
) -> urllib.request.Request:
    headers = {"Accept": "application/json"}
    if runtime.provider == "anthropic":
        default_base = "https://api.anthropic.com/v1"
        endpoint = f"{runtime.api_base or default_base}/models?limit={model_limit}"
        headers["x-api-key"] = runtime.api_key or ""
        headers["anthropic-version"] = "2023-06-01"
    elif runtime.provider == "gemini":
        default_base = "https://generativelanguage.googleapis.com/v1beta"
        endpoint = f"{runtime.api_base or default_base}/models?pageSize={model_limit}"
        headers["x-goog-api-key"] = runtime.api_key or ""
    else:
        default_base = "https://api.openai.com/v1"
        endpoint = f"{runtime.api_base or default_base}/models"
        if runtime.api_key:
            headers["Authorization"] = f"Bearer {runtime.api_key}"
    return urllib.request.Request(endpoint, headers=headers, method="GET")  # noqa: S310


def _extract_model_ids(provider: ProviderKind, payload: object) -> list[str]:
    if not isinstance(payload, dict):
        raise ProviderConfigurationError("invalidProviderResponse")
    collection = payload.get("models" if provider == "gemini" else "data")
    if not isinstance(collection, list):
        raise ProviderConfigurationError("invalidProviderResponse")
    models: list[str] = []
    for item in collection:
        if not isinstance(item, dict):
            continue
        value = item.get("name" if provider == "gemini" else "id")
        if not isinstance(value, str):
            continue
        model_id = value.removeprefix("models/").strip()
        if model_id and len(model_id) <= 200 and model_id not in models:
            models.append(model_id)
        if len(models) == 200:
            break
    return sorted(models, key=str.casefold)
