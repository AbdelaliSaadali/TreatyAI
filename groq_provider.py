"""Groq structured-generation adapter. No SDK install, API keys or prompts in logs.

The model can propose intentions; it never authorizes business actions.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

import httpx


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
KEYCHAIN_SERVICE = "TreatyAI-Groq-API"
DEFAULT_MODEL = "openai/gpt-oss-20b"
SUPPORTED_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
MAX_ATTEMPTS = 3


class GroqConfigurationError(RuntimeError):
    pass


class GroqGenerationError(RuntimeError):
    pass


def resolve_key() -> str | None:
    """Environment first, otherwise the macOS login Keychain, never filesystem."""
    env = os.environ.get("GROQ_API_KEY", "").strip()
    if env:
        return env
    if os.uname().sysname != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
             "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def model_name() -> str:
    configured = os.environ.get("TREATYAI_GROQ_MODEL", DEFAULT_MODEL)
    if configured not in SUPPORTED_MODELS:
        raise GroqConfigurationError("Unsupported model; choose a listed supported model.")
    return configured


def status() -> dict[str, Any]:
    return {
        "configured": bool(resolve_key()),
        "provider": "GroqCloud",
        "model": model_name(),
        "endpoint": "api.groq.com",
        "structured_outputs": "strict-json-schema",
        "external_actions_enabled": False,
        "credential_storage": "GROQ_API_KEY environment or macOS login Keychain",
    }


class GroqProvider:
    """Small authenticated HTTP client with limited retries and strict output parsing."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None,
                 client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else resolve_key()
        if not self.api_key:
            raise GroqConfigurationError(
                "Groq is not configured. Add the key to the macOS Keychain using setup_groq.sh."
            )
        self.model = model or model_name()
        if self.model not in SUPPORTED_MODELS:
            raise GroqConfigurationError("Unsupported Groq model")
        self.client = client

    def complete(self, *, system: str, user: dict[str, Any],
                 schema_name: str, schema: dict[str, Any],
                 max_tokens: int = 600) -> dict[str, Any]:
        body = {
            "model": self.model,
            "temperature": 0.15,
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, sort_keys=True, ensure_ascii=False)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = "Provider unavailable"
        for attempt in range(MAX_ATTEMPTS):
            started = time.monotonic()
            try:
                if self.client is None:
                    with httpx.Client(timeout=httpx.Timeout(45, connect=8)) as client:
                        response = client.post(GROQ_URL, json=body, headers=headers)
                else:
                    response = self.client.post(GROQ_URL, json=body, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError):
                last_error = "Groq request timeout or network connection failure"
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(0.35 * (attempt + 1))
                    continue
                raise GroqGenerationError(last_error)

            if response.status_code in (408, 409, 429, 500, 502, 503, 504):
                last_error = f"Groq service returned HTTP {response.status_code}"
                if attempt < MAX_ATTEMPTS - 1:
                    delay = 0.5 * (attempt + 1)
                    if response.status_code == 429:
                        try:
                            delay = min(3.0, max(0.5, float(response.headers.get("retry-after", delay))))
                        except ValueError:
                            pass
                    time.sleep(delay)
                    continue
                raise GroqGenerationError(last_error)
            if response.status_code == 401:
                raise GroqConfigurationError("Groq rejected the API key (HTTP 401).")
            if response.status_code >= 400:
                raise GroqGenerationError(f"Groq request failed (HTTP {response.status_code}).")

            try:
                result = response.json()
                message = result["choices"][0]["message"]
                if message.get("refusal"):
                    raise GroqGenerationError("Groq returned a model refusal.")
                content = message["content"]
                if not isinstance(content, str):
                    raise ValueError("Model content must be a string")
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise ValueError("Model content must be a JSON object")
                usage = result.get("usage") or {}
                return {
                    "output": parsed,
                    "usage": {
                        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                        "completion_tokens": int(usage.get("completion_tokens") or 0),
                        "total_tokens": int(usage.get("total_tokens") or 0),
                    },
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "model": self.model,
                    "finish_reason": result["choices"][0].get("finish_reason", "unknown"),
                }
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise GroqGenerationError("Groq returned an invalid structured response.") from exc
        raise GroqGenerationError(last_error)


def validate_remote_key(secret: str) -> dict[str, Any]:
    """Verify the key with Groq Models API before writing it to Keychain."""
    try:
        response = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            timeout=httpx.Timeout(16, connect=6),
        )
    except (httpx.TransportError, httpx.TimeoutException) as exc:
        raise GroqGenerationError("Cannot reach Groq to verify the credential.") from exc
    if response.status_code in (401, 403):
        raise GroqConfigurationError("Groq rejected this API credential.")
    if response.status_code != 200:
        raise GroqGenerationError(f"Groq key verification returned HTTP {response.status_code}.")
    try:
        ids = {item["id"] for item in response.json()["data"]}
    except (ValueError, TypeError, KeyError) as exc:
        raise GroqGenerationError("Groq models response was malformed.") from exc
    supported = [item for item in SUPPORTED_MODELS if item in ids]
    if not supported:
        raise GroqConfigurationError("No supported Groq structured-output model is enabled for this key.")
    return {"validated": True, "available_models": supported}
