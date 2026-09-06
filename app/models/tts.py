"""Indic TTS model abstraction (Phase 10).

Receives regional-language text (post IndicTrans2) and returns audio bytes.

Interface:
    tts.generate(text, language) → bytes (WAV)
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.config import TTS_MODEL_ID
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseTTS(ABC):
    @abstractmethod
    def generate(self, text: str, language: str) -> bytes:
        """Return WAV audio bytes for the given regional-language text."""


class IndicParlerTTS(BaseTTS):
    """AI4Bharat Indic Parler TTS – implemented in Phase 10."""

    def __init__(self, model_id: str = TTS_MODEL_ID, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading Indic TTS: %s on %s", self.model_id, self.device)
        raise NotImplementedError("IndicParlerTTS will be implemented in Phase 10.")

    def generate(self, text: str, language: str) -> bytes:
        t0 = time.time()
        self._load()
        raise NotImplementedError("IndicParlerTTS will be implemented in Phase 10.")


class StubTTS(BaseTTS):
    """Returns empty bytes; used when TTS is unavailable (text answer still shown)."""

    def generate(self, text: str, language: str) -> bytes:
        logger.warning("StubTTS: TTS not available, returning empty audio.")
        return b""


def get_tts(device: str = "cpu", use_stub: bool = False) -> BaseTTS:
    if use_stub:
        return StubTTS()
    return IndicParlerTTS(device=device)
