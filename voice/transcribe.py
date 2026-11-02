"""Muse Voice Transcribe client for BusDrop crowd signals (phase 6).

Driver and rider speech goes through Voice Transcribe to text, then
through signals.parse_transcript to a crowd level the dispatcher can act
on. Audio transcription needs a key; text fixtures (demos, tests) never
touch the network.
"""
from __future__ import annotations

import os
from pathlib import Path

from dispatcher.spark import resolve_api_key as _resolve_model_key

BASE_URL = "https://api.meta.ai/v1"
MODEL_ID = "muse-voice-transcribe"


class VoiceError(Exception):
    """No API key, unreadable audio, or failed transcription."""


def resolve_api_key(dotenv_root: Path | None = None) -> str:
    """VOICE_API_KEY env, then the shared MODEL_API_KEY resolution."""
    if os.environ.get("VOICE_API_KEY"):
        return os.environ["VOICE_API_KEY"]
    return _resolve_model_key(dotenv_root)


class VoiceClient:
    """Thin wrapper over the OpenAI-compatible transcription endpoint."""

    def __init__(self, api_key: str | None = None,
                 model: str = MODEL_ID,
                 timeout: float = 120.0,
                 max_retries: int = 1) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise VoiceError(
                "openai package required: pip install -r requirements.txt")
        self.model = model
        self._client = OpenAI(
            base_url=BASE_URL,
            api_key=api_key or resolve_api_key(),
            timeout=timeout,
            max_retries=max_retries,
        )

    def transcribe_file(self, audio_path: str | Path,
                        language: str | None = None) -> str:
        """Transcribe one audio file to text (Tamil/English)."""
        path = Path(audio_path)
        if not path.exists():
            raise VoiceError(f"audio file not found: {path}")
        try:
            with open(path, "rb") as f:
                result = self._client.audio.transcriptions.create(
                    model=self.model,
                    file=f,
                    **({"language": language} if language else {}),
                )
        except Exception as e:
            raise VoiceError(f"Voice Transcribe call failed: {e}")
        return result.text

    @staticmethod
    def transcribe_text(text: str) -> str:
        """Passthrough for demo/test fixtures: text in, text out."""
        return text.strip()
