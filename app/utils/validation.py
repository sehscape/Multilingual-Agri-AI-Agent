"""Input validation helpers used at system boundaries."""
from typing import Optional
from app.config import SUPPORTED_LANGUAGES


def validate_language(lang_code: str) -> str:
    """Return lang_code if supported, else default to 'hi'."""
    return lang_code if lang_code in SUPPORTED_LANGUAGES else "hi"


def validate_location(location: Optional[str]) -> Optional[str]:
    if not location or not location.strip():
        return None
    return location.strip()


def validate_audio_input(audio) -> bool:
    """Return True if the audio input is non-empty."""
    return audio is not None
