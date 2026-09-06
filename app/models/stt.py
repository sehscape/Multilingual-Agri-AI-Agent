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
    def transcribe(self, audio_path: str) -> dict[str, str]:
        """
        Transcribe audio and auto-detect language.

        Returns:
            {
                "text":     <transcription in detected script>,
                "language": <ISO 639-1 code: "hi" | "mr" | "pa" | "en" | "unknown">
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

    def transcribe(self, audio_path: str) -> dict[str, str]:
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

        # ── 4. Generate — no forced language → auto-detect ─────────────────────
        with torch.no_grad():
            predicted_ids = self._model.generate(
                input_features,
                task="transcribe",
            )

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
        logger.info("STT | lang_name=%r → iso=%r  (all specials: %s)",
                    lang_name, iso_lang, all_specials)

        # ── 6. Decode transcription ─────────────────────────────────────────────
        text = self._processor.batch_decode(
            predicted_ids, skip_special_tokens=True
        )[0].strip()

        elapsed = time.time() - t0
        logger.info("STT | %.1fs | detected=%s (%s) | chars=%d",
                    elapsed, lang_name, iso_lang, len(text))

        return {"text": text, "language": iso_lang, "language_name": lang_name}


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

    def transcribe(self, audio_path: str) -> dict[str, str]:
        result = self._STUBS[StubSTT._idx % len(self._STUBS)]
        StubSTT._idx += 1
        logger.warning("StubSTT | returning %s stub.", result["language_name"])
        return result


def get_stt(device: str = "cpu", use_stub: bool = False) -> BaseSTT:
    if use_stub:
        return StubSTT()
    return WhisperSTT(device=device)
