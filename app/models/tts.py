"""Indic TTS model abstraction (Phase 10).

Receives regional-language text (post IndicTrans2) and returns a path to a
playable audio file (or None when audio is unavailable — the caller still shows
the text answer).

Interface:
    tts.generate(text, language) → Optional[str]   # path to .mp3/.wav, or None

Engines (selected via TTS_ENGINE in .env):
    "gtts"   → Google TTS. Lightweight, CPU-friendly, needs internet. Dev default.
    "parler" → ai4bharat/indic-parler-tts. Production quality, large, GPU.
    "stub"   → returns None (no audio).

Languages: Hindi (hi), Marathi (mr), Punjabi (pa), English (en).
"""
from __future__ import annotations

import tempfile
import time
from abc import ABC, abstractmethod
from typing import Optional

from app.config import TTS_ENGINE, TTS_MODEL_ID
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Human-readable language names (used to steer the Parler voice description).
_LANG_NAME = {"hi": "Hindi", "mr": "Marathi", "pa": "Punjabi", "en": "English"}


class BaseTTS(ABC):
    @abstractmethod
    def generate(self, text: str, language: str) -> Optional[str]:
        """Return a path to an audio file for the text, or None if unavailable."""


class GttsTTS(BaseTTS):
    """Lightweight TTS via Google Translate's TTS endpoint (needs internet).

    Ideal for local/CPU development: no multi-GB model download, real
    Hindi/Marathi/Punjabi speech. Returns an .mp3 path.
    """

    _GTTS_LANG = {"hi": "hi", "mr": "mr", "pa": "pa", "en": "en"}

    def generate(self, text: str, language: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        try:
            from gtts import gTTS
            lang = self._GTTS_LANG.get(language, "en")
            t0 = time.time()
            path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            gTTS(text=text, lang=lang).save(path)
            logger.info("gTTS | %s | %d chars | %.1fs → %s",
                        lang, len(text), time.time() - t0, path)
            return path
        except Exception as exc:
            logger.error("gTTS failed (%s) — no audio; text answer still shown.", exc)
            return None


class IndicParlerTTS(BaseTTS):
    """Production TTS backed by ai4bharat/indic-parler-tts (large, GPU-oriented).

    Requires:  pip install git+https://github.com/ai4bharat/indic-parler-tts
    Loads lazily on first use. Returns a .wav path.
    """

    def __init__(self, model_id: str = TTS_MODEL_ID, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self._model = None
        self._tokenizer = None
        self._desc_tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
        except ImportError as e:
            raise RuntimeError(
                "indic-parler-tts not installed. Run: "
                "pip install git+https://github.com/ai4bharat/indic-parler-tts"
            ) from e
        from transformers import AutoTokenizer

        logger.info("Loading Indic Parler TTS: %s on %s", self.model_id, self.device)
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(self.model_id).to(self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        # The description encoder may use a different tokenizer.
        self._desc_tokenizer = AutoTokenizer.from_pretrained(
            self._model.config.text_encoder._name_or_path
        )
        logger.info("Indic Parler TTS loaded.")

    def generate(self, text: str, language: str) -> Optional[str]:
        if not text or not text.strip():
            return None
        import torch
        import soundfile as sf

        self._load()
        lang_name = _LANG_NAME.get(language, "Hindi")
        description = (
            f"A clear, natural female voice speaking in {lang_name} at a moderate "
            f"pace, with expressive intonation and very high recording quality."
        )
        t0 = time.time()
        desc = self._desc_tokenizer(description, return_tensors="pt").to(self.device)
        prompt = self._tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            generation = self._model.generate(
                input_ids=desc.input_ids,
                attention_mask=desc.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        audio = generation.cpu().numpy().squeeze()
        path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        sf.write(path, audio, self._model.config.sampling_rate)
        logger.info("Parler TTS | %s | %d samples | %.1fs → %s",
                    language, len(audio), time.time() - t0, path)
        return path


class StubTTS(BaseTTS):
    """No-op TTS — returns None so the pipeline still shows the text answer."""

    def generate(self, text: str, language: str) -> Optional[str]:
        logger.warning("StubTTS: TTS disabled, returning no audio.")
        return None


def get_tts(device: str = "cpu", engine: Optional[str] = None) -> BaseTTS:
    engine = (engine or TTS_ENGINE).lower()
    if engine == "stub":
        return StubTTS()
    if engine == "parler":
        return IndicParlerTTS(device=device)
    return GttsTTS()  # default: lightweight, CPU-friendly
