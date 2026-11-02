"""BusDrop voice input: Tamil/English speech becomes crowd signals.

Muse Voice Transcribe turns driver and rider speech into text;
signals.py parses that text into levels the dispatcher acts on.
Phase 6."""
from .signals import (BOOST_BY_LEVEL, LEVELS, MAX_BOOST, SIGNAL_WINDOW_MIN,
                      STOP_ALIASES, CrowdSignal, VoiceFeed, detect_stop,
                      load_demo, load_file, parse_transcript)
from .transcribe import (BASE_URL, MODEL_ID, VoiceClient, VoiceError,
                         resolve_api_key)

__all__ = ["BASE_URL", "BOOST_BY_LEVEL", "LEVELS", "MAX_BOOST", "MODEL_ID",
           "SIGNAL_WINDOW_MIN", "STOP_ALIASES", "CrowdSignal", "VoiceClient",
           "VoiceError", "VoiceFeed", "detect_stop", "load_demo",
           "load_file", "parse_transcript", "resolve_api_key"]
