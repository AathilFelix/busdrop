"""Muse Spark Open client for BusDrop rider agents (phase 5).

Rider agents run on the open tier via a user-provided OpenAI-compatible
endpoint (Baseten / Modal). Each rider decides walk/stay for one offered
move; the deterministic rule in policy.py is the fallback and the
offline default, so runs never need this endpoint.
"""
from __future__ import annotations

import json
import os

DEFAULT_MODEL = "muse-spark-open"


class RiderError(Exception):
    """No endpoint configured, failed call, or unusable model output."""


def resolve_endpoint() -> tuple[str, str, str]:
    """(base_url, api_key, model) from SPARK_OPEN_* env, else RiderError."""
    base_url = os.environ.get("SPARK_OPEN_BASE_URL", "")
    api_key = os.environ.get("SPARK_OPEN_API_KEY", "")
    model = os.environ.get("SPARK_OPEN_MODEL", DEFAULT_MODEL)
    if not base_url or not api_key:
        raise RiderError(
            "No Spark Open endpoint: export SPARK_OPEN_BASE_URL=... and "
            "SPARK_OPEN_API_KEY=... (Baseten / Modal), or run with "
            "--riders rule for the offline rule-based riders.")
    return base_url, api_key, model


class SparkOpenClient:
    """Thin wrapper over an OpenAI-compatible rider-agent endpoint."""

    def __init__(self, base_url: str | None = None,
                 api_key: str | None = None,
                 model: str | None = None,
                 timeout: float = 60.0,
                 max_retries: int = 1) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise RiderError(
                "openai package required: pip install -r requirements.txt")
        if base_url is None or api_key is None:
            resolved_url, resolved_key, resolved_model = resolve_endpoint()
            base_url = base_url or resolved_url
            api_key = api_key or resolved_key
            model = model or resolved_model
        self.model = model or DEFAULT_MODEL
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )

    def decide(self, messages: list[dict]) -> dict:
        """One walk/stay decision; returns {"walk": bool, "reason": str}."""
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                max_tokens=300,
            )
        except Exception as e:
            raise RiderError(f"Spark Open call failed: {e}")
        return self._extract(resp)

    @staticmethod
    def _extract(resp) -> dict:
        content = resp.choices[0].message.content or ""
        start = content.find("{")
        if start < 0:
            raise RiderError("rider model returned no decision")
        try:
            obj, _ = json.JSONDecoder().raw_decode(content[start:])
        except json.JSONDecodeError as e:
            raise RiderError(f"rider model returned invalid JSON: {e}")
        if not isinstance(obj, dict) or not isinstance(obj.get("walk"), bool):
            raise RiderError("rider decision needs a boolean 'walk' field")
        return {"walk": obj["walk"], "reason": str(obj.get("reason", ""))}
