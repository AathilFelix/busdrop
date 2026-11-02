"""Crowd signals: Tamil/English driver and rider speech parsed into a
form the dispatcher can act on.

A signal is a timestamped note — "bus full at LIC", "LIC-la periya
koottam" — carrying how many extra waiting riders the dispatcher should
assume at that stop. The transcript may come from Muse Voice Transcribe
(transcribe.py) or straight from text in demos and tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LEVELS = ("ok", "busy", "crush")

# Extra waiting riders the dispatcher assumes per signal level.
BOOST_BY_LEVEL = {"ok": 0, "busy": 3, "crush": 6}
# A signal counts for this long after it is spoken.
SIGNAL_WINDOW_MIN = 10
# Cap on the total boost at one stop so a chatterbox can't invent a crowd.
MAX_BOOST = 12

# Transliterated spoken Tamil as Voice Transcribe returns it.
TA_CRUSH = ("nirambu", "nirambi", "seat illa", "yera mudiyala",
            "yeri mudiyala", "koottam adhigam", "suthama mudiyala",
            "full-a")
TA_BUSY = ("koottam", "kottam", "rush", "waiting", "queue", "periya",
           "jasthi")
# Distinctly Tamil tokens for language detection. Loanwords ("rush",
# "waiting", "queue") help the level but never mark the language — they
# also match inside English words ("rush" in "crush").
TA_MARKERS = ("nirambu", "nirambi", "seat illa", "mudiyala", "koottam",
              "kottam", "adhigam", "periya", "jasthi", "poguthu",
              "illa", "suthama")
EN_CRUSH = ("can't board", "cannot board", "left behind", "no space",
            "packed", "crush", "bursting", "jam-packed", "standing only",
            "no seat", "overcrowd", "too full")
EN_BUSY = ("crowd", "heavy", "rush", "long queue", "many people",
           "waiting", "queue", "busy", "filling")

STOP_ALIASES = {
    "royapettah": "ROY", "royapettai": "ROY",
    "pycrofts": "PYC", "pycrofts road": "PYC",
    "teynampet": "TEY", "teynampettai": "TEY",
    "siet": "SIE",
    "gemini": "GEM",
    "thousand lights": "THL", "thousandlights": "THL",
    "lic": "LIC",
    "simpson": "SIM", "simpsons": "SIM",
    "central": "CEN",
    "broadway": "BWY", "parrys": "BWY", "parry's": "BWY",
}


@dataclass(frozen=True)
class CrowdSignal:
    minute: int
    text: str
    language: str  # "en", "ta", or "mixed"
    level: str  # "ok", "busy", or "crush"
    stop_id: str | None  # None when no stop name was heard
    extra_waiting: int


def detect_stop(text: str) -> str | None:
    lowered = text.lower()
    for alias, stop_id in sorted(STOP_ALIASES.items(),
                                 key=lambda kv: -len(kv[0])):
        if alias in lowered:
            return stop_id
    return None


def parse_transcript(text: str, minute: int,
                     stop_id: str | None = None) -> CrowdSignal:
    """Keyword parse of one transcript into a crowd signal.

    Crush keywords win over busy ones; an explicit stop_id wins over
    name detection. Anything with no crowd keywords parses as "ok" with
    zero boost — hearing "all clear" is still hearing something.
    """
    lowered = text.lower()
    ta = any(k in lowered for k in TA_MARKERS)
    en = any(k in lowered for k in EN_CRUSH + EN_BUSY)
    language = "mixed" if ta and en else ("ta" if ta else "en")
    if any(k in lowered for k in TA_CRUSH + EN_CRUSH):
        level = "crush"
    elif any(k in lowered for k in TA_BUSY + EN_BUSY):
        level = "busy"
    else:
        level = "ok"
    resolved = stop_id or detect_stop(text)
    return CrowdSignal(minute=minute, text=text, language=language,
                       level=level, stop_id=resolved,
                       extra_waiting=BOOST_BY_LEVEL[level])


class VoiceFeed:
    """Timestamped signals; the sim asks for the boost at a stop/minute."""

    def __init__(self, signals: list[CrowdSignal] | None = None) -> None:
        self.signals = sorted(signals or [], key=lambda s: s.minute)

    def __len__(self) -> int:
        return len(self.signals)

    def boost_at(self, stop_id: str, minute: int,
                 window: int = SIGNAL_WINDOW_MIN) -> int:
        """Extra waiting riders assumed at a stop right now.

        Only signals naming this stop and spoken within the window count;
        stop-less signals are logged color, not actionable intel.
        """
        if minute is None:
            return 0
        boost = sum(s.extra_waiting for s in self.signals
                    if s.stop_id == stop_id
                    and 0 <= minute - s.minute <= window)
        return min(boost, MAX_BOOST)

    def latest_at(self, minute: int) -> CrowdSignal | None:
        """Most recent signal at or before a minute, for the dashboard."""
        past = [s for s in self.signals if s.minute <= minute]
        return past[-1] if past else None


def load_demo() -> VoiceFeed:
    """Morning-peak driver notes: Tamil + English, timed for the rush."""
    return VoiceFeed([
        parse_transcript("LIC-la periya koottam, bus full-a poguthu",
                         92, "LIC"),
        parse_transcript("Thousand Lights crowd building, long queue",
                         100, "THL"),
        parse_transcript("Central-la seat illa, yera mudiyala", 108, "CEN"),
        parse_transcript("Simpson crush, can't board, many left behind",
                         115, "SIM"),
    ])


def load_file(path: str | Path) -> VoiceFeed:
    """Load a JSON array of {minute, text, stop_id?} transcripts."""
    items = json.loads(Path(path).read_text())
    if not isinstance(items, list):
        raise ValueError(f"{path}: expected a JSON array of transcripts")
    signals = []
    for i, item in enumerate(items):
        try:
            signals.append(parse_transcript(
                item["text"], int(item["minute"]),
                item.get("stop_id")))
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"{path}[{i}]: need {{minute: int, text: str}}")
    return VoiceFeed(signals)
