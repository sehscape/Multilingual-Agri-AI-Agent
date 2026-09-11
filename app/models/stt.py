"""Speech-to-text with automatic language detection – Phase 2.

Architecture:
    audio_path → WhisperSTT.transcribe() → {"text": str, "language": str}

Language detection:
    Whisper's multilingual output token sequence is always:
        <|startoftranscript|> <|language|> <|transcribe|> <|notimestamps|> ...text...
    Token at index 1 is the detected language. We decode it to get the language name
    (e.g. "<|hindi|>") and map it to our ISO 639-1 code ("hi").

    We use the model API directly (not the pipeline) because the pipeline does not
    expose the detected language in its output dict.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from app.config import WHISPER_MODEL_ID
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Whisper language token names → our ISO 639-1 codes
_WHISPER_LANG_REVERSE: dict[str, str] = {
    "hindi":   "hi",
    "marathi": "mr",
    "punjabi": "pa",
    "english": "en",
}

# Our ISO codes → Whisper language names (used only for forced-language mode)
_WHISPER_LANG_MAP: dict[str, str] = {v: k for k, v in _WHISPER_LANG_REVERSE.items()}


class BaseSTT(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   translate: bool = False) -> dict[str, str]:
        """
        Transcribe audio.

        Args:
            language:  ISO code ("hi" | "mr" | "pa" | "en") to force; None → auto-detect.
            translate: also return Whisper's speech-to-English translation
                       (only when a non-English language is forced).

        Returns:
            {
                "text":         <transcription in the spoken script>,
                "language":     <ISO 639-1 code: "hi" | "mr" | "pa" | "en" | "unknown">,
                "english_text": <English translation — present only when translate=True>
            }
        """


class WhisperSTT(BaseSTT):
    """
    Whisper-based STT using the model API directly for language detection.

    Model controlled by WHISPER_MODEL_ID env var:
        Local dev (CPU) : openai/whisper-tiny
        HF Spaces (GPU) : openai/whisper-large-v3
    """

    def __init__(self, model_id: str = WHISPER_MODEL_ID, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self._model = None
        self._processor = None

    def _load(self) -> None:
        if self._model is not None:
            return

        import torch
        from transformers import WhisperProcessor, WhisperForConditionalGeneration

        dtype = torch.float16 if self.device != "cpu" else torch.float32
        logger.info("Loading Whisper | model=%s  device=%s  dtype=%s",
                    self.model_id, self.device, dtype)

        self._processor = WhisperProcessor.from_pretrained(self.model_id)
        self._model = WhisperForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
        ).to(self.device)

        logger.info("Whisper loaded.")

    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   translate: bool = False) -> dict[str, str]:
        import torch
        import numpy as np
        import soundfile as sf
        from app.utils.audio import ensure_wav

        t0 = time.time()
        self._load()

        # ── 1. Convert browser audio (webm/ogg) → 16 kHz mono WAV ─────────────
        wav_path = ensure_wav(audio_path)

        # ── 2. Load WAV as numpy array (soundfile reads WAV natively, no ffmpeg) ─
        audio_array, sample_rate = sf.read(wav_path)
        if audio_array.ndim > 1:
            audio_array = audio_array.mean(axis=1)   # stereo → mono
        audio_array = audio_array.astype(np.float32)

        # ── 3. Extract input features ───────────────────────────────────────────
        inputs = self._processor(
            audio_array,
            sampling_rate=sample_rate,
            return_tensors="pt",
        )
        input_features = inputs.input_features.to(self.device)

        # ── 4. Generate — forced language when given, else auto-detect ─────────
        # Forcing the language the farmer chose avoids Whisper's frequent
        # mis-detections between Hindi and Marathi (and "unknown" on short clips).
        forced = _WHISPER_LANG_MAP.get(language) if language else None
        gen_kwargs = {"task": "transcribe"}
        if forced:
            gen_kwargs["language"] = forced
        with torch.no_grad():
            predicted_ids = self._model.generate(input_features, **gen_kwargs)

        # ── 5. Detect language by parsing the full special-token sequence ───────
        # Decode keeping special tokens so we can search by name, not by index.
        # Output looks like: "<|startoftranscript|><|english|><|transcribe|><|notimestamps|> Hello..."
        # We skip known non-language tokens and take the first match as the language.
        import re as _re
        raw = self._processor.tokenizer.decode(
            predicted_ids[0].tolist(), skip_special_tokens=False
        )
        logger.info("STT | raw tokens: %s", raw[:150])

        _NON_LANG = {
            "startoftranscript", "endoftext", "transcribe", "translate",
            "notimestamps", "nospeech", "pad",
        }
        all_specials = _re.findall(r"<\|([^|]+)\|>", raw)
        lang_name = "unknown"
        for tok in all_specials:
            t = tok.lower()
            if t in _NON_LANG or _re.match(r"^\d+\.\d+$", t):
                continue
            lang_name = t
            break

        iso_lang = _WHISPER_LANG_REVERSE.get(lang_name, "unknown")
        if forced:
            iso_lang, lang_name = language, forced
        logger.info("STT | lang_name=%r → iso=%r  (all specials: %s)",
                    lang_name, iso_lang, all_specials)

        # ── 6. Decode transcription ─────────────────────────────────────────────
        text = self._processor.batch_decode(
            predicted_ids, skip_special_tokens=True
        )[0].strip()
        result = {"text": text, "language": iso_lang, "language_name": lang_name}

        # ── 7. Optional speech → English translation (same audio features) ─────
        # Whisper's built-in translate task lets regional speech reach the
        # English agent without a separate multi-GB translation model.
        if translate and forced and language != "en":
            with torch.no_grad():
                trans_ids = self._model.generate(
                    input_features, language=forced, task="translate"
                )
            result["english_text"] = self._processor.batch_decode(
                trans_ids, skip_special_tokens=True
            )[0].strip()

        elapsed = time.time() - t0
        logger.info("STT | %.1fs | language=%s (%s) | chars=%d | translated=%s",
                    elapsed, lang_name, iso_lang, len(text), "english_text" in result)
        return result


class StubSTT(BaseSTT):
    """Returns hardcoded results – for unit tests and offline dev."""

    _STUBS = [
        {
            "text": "मेरी गेहूं की फसल 40 दिन की है और अगले तीन दिन बारिश होगी।",
            "language": "hi",
            "language_name": "hindi",
        },
        {
            "text": "माझ्या कांद्याच्या पिकाला ४५ दिवस झाले आहेत. आता काय काळजी घ्यावी?",
            "language": "mr",
            "language_name": "marathi",
        },
        {
            "text": "ਮੇਰੀ ਕਣਕ ਦੀ ਫ਼ਸਲ 40 ਦਿਨ ਦੀ ਹੈ। ਮੈਨੂੰ ਕੀ ਕਰਨਾ ਚਾਹੀਦਾ ਹੈ?",
            "language": "pa",
            "language_name": "punjabi",
        },
    ]
    _idx = 0

    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   translate: bool = False) -> dict[str, str]:
        result = dict(self._STUBS[StubSTT._idx % len(self._STUBS)])
        StubSTT._idx += 1
        logger.warning("StubSTT | returning %s stub.", result["language_name"])
        return result


def get_stt(device: str = "cpu", use_stub: bool = False) -> BaseSTT:
    if use_stub:
        return StubSTT()
    return WhisperSTT(device=device)
