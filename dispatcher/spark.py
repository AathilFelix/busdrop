"""Muse Spark client for the BusDrop dispatcher (phase 4).

Model: muse-spark-1.3-contributor, pinned — this dispatcher only ever
calls the contributor tier (identical weights to standard Spark 1.3 at
contributor pricing). Contributor traffic may be used to improve Meta's
products; our payloads are synthetic sim state, nothing sensitive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE_URL = "https://api.meta.ai/v1"
MODEL_ID = "muse-spark-1.3-contributor"


class DispatcherError(Exception):
    """No API key, failed API call, or unusable model output."""


def _load_dotenv(root: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    path = root / ".env"
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip("'\"")
    return env


def resolve_api_key(dotenv_root: Path | None = None) -> str:
    """MODEL_API_KEY env, META_API_KEY env, then busdrop/.env (gitignored)."""
    for var in ("MODEL_API_KEY", "META_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    root = dotenv_root or Path(__file__).resolve().parent.parent
    key = _load_dotenv(root).get("MODEL_API_KEY")
    if key:
        return key
    raise DispatcherError(
        "No Meta API key: export MODEL_API_KEY=... (get one at "
        "https://dev.meta.ai) or put MODEL_API_KEY=... in busdrop/.env.")


class SparkClient:
    """Thin wrapper over the OpenAI-compatible Meta Model API."""

    def __init__(self, api_key: str | None = None,
                 model: str = MODEL_ID, timeout: float = 120.0,
                 max_retries: int = 1) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise DispatcherError(
                "openai package required: pip install -r requirements.txt")
        self.model = model
        self._client = OpenAI(
            base_url=BASE_URL,
            api_key=api_key or resolve_api_key(),
            timeout=timeout,
            max_retries=max_retries,
        )

    def propose(self, messages: list[dict], tool_schema: dict) -> dict:
        """One propose_handoff tool call; returns its arguments.

        The endpoint only supports tool_choice "auto", so the prompt
        demands the call and _extract also accepts a raw JSON answer.
        """
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool_schema],
                tool_choice="auto",
                temperature=0,
                # Reasoning model: needs headroom for its thinking trace;
                # 400 cut it off before it answered.
                max_tokens=4000,
            )
        except Exception as e:
            raise DispatcherError(f"Spark API call failed: {e}")
        return self._extract(resp)

    @staticmethod
    def _extract(resp) -> dict:
        msg = resp.choices[0].message
        for call in msg.tool_calls or []:
            if call.function.name == "propose_handoff":
                try:
                    return json.loads(call.function.arguments)
                except json.JSONDecodeError as e:
                    raise DispatcherError(
                        f"model returned invalid JSON: {e}")
        content = msg.content or ""
        start = content.find("{")
        if start < 0:
            raise DispatcherError("model returned no proposal")
        try:
            obj, _ = json.JSONDecoder().raw_decode(content[start:])
        except json.JSONDecodeError as e:
            raise DispatcherError(f"model returned invalid JSON: {e}")
        if not isinstance(obj, dict):
            raise DispatcherError("model proposal is not an object")
        return obj
