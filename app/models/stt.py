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

# A farmer's spoken question is a sentence or two; anything longer is the model
# looping, not the farmer talking.
_MAX_QUESTION_TOKENS = 96

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
        # On a CPU, whisper-small sometimes falls into a repetition loop on
        # Indic speech ("अगर अगर अगर …") and generates until the 448-token
        # limit — half a minute of waiting for nothing. A farmer's question is
        # one sentence, so cap the length and penalise repeats: bad clips now
        # fail in seconds instead (and _is_degenerate below catches them).
        forced = _WHISPER_LANG_MAP.get(language) if language else None
        gen_kwargs = {
            "task": "transcribe",
            "max_new_tokens": _MAX_QUESTION_TOKENS,
            "no_repeat_ngram_size": 4,
            "repetition_penalty": 1.15,
        }
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
        if _is_degenerate(text):
            logger.warning("STT | discarded a looping transcript: %.60s…", text)
            text = ""
        result = {"text": text, "language": iso_lang, "language_name": lang_name,
                  "no_speech": not text}

        # ── 7. Optional speech → English translation (same audio features) ─────
        # Whisper's built-in translate task lets regional speech reach the
        # English agent without a separate multi-GB translation model.
        if translate and forced and language != "en":
            with torch.no_grad():
                trans_ids = self._model.generate(
                    input_features, language=forced, task="translate",
                    max_new_tokens=_MAX_QUESTION_TOKENS, no_repeat_ngram_size=4,
                    repetition_penalty=1.15,
                )
            result["english_text"] = self._processor.batch_decode(
                trans_ids, skip_special_tokens=True
            )[0].strip()

        elapsed = time.time() - t0
        logger.info("STT | %.1fs | language=%s (%s) | chars=%d | translated=%s",
                    elapsed, lang_name, iso_lang, len(text), "english_text" in result)
        return result


# A sentence in each language that primes Whisper with the script and the
# farm words farmers use, so crop and scheme names come out spelled right.
_GROQ_STT_PROMPTS: dict[str, str] = {
    "hi": "किसान गेहूं, धान, कपास, प्याज, टमाटर, मक्का, खाद, यूरिया, सिंचाई, "
          "बारिश, मौसम, कीड़े और सरकारी योजनाओं के बारे में पूछ रहा है।",
    "mr": "शेतकरी गहू, भात, कापूस, कांदा, टोमॅटो, मका, खत, युरिया, पाणी, "
          "पाऊस, हवामान, कीड आणि सरकारी योजनांबद्दल विचारत आहे.",
    "pa": "ਕਿਸਾਨ ਕਣਕ, ਝੋਨਾ, ਕਪਾਹ, ਪਿਆਜ਼, ਟਮਾਟਰ, ਮੱਕੀ, ਖਾਦ, ਯੂਰੀਆ, ਪਾਣੀ, "
          "ਮੀਂਹ, ਮੌਸਮ, ਕੀੜੇ ਅਤੇ ਸਰਕਾਰੀ ਸਕੀਮਾਂ ਬਾਰੇ ਪੁੱਛ ਰਿਹਾ ਹੈ।",
    "en": "A farmer asks about wheat, paddy, cotton, onion, tomato, maize, "
          "fertilizer, urea, irrigation, rain, weather, pests and government schemes.",
}

# What Whisper tends to "hear" in silence or noise.
_SILENCE_PHRASES = {
    "thank you", "thanks for watching", "thank you for watching", "you",
    "धन्यवाद", "शुक्रिया", "सब्सक्राइब", "ਧੰਨਵਾਦ", "धन्यवाद.",
}


def _clean_words(text: str) -> list[str]:
    import re
    return re.findall(r"[\wऀ-੿]+", (text or "").lower())


def _is_degenerate(text: str) -> bool:
    """True when the model looped instead of transcribing speech —
    "अगर बारीश अगी अगर अगर अगर अगर …". Better to ask the farmer to say it
    again than to answer a question nobody asked."""
    words = _clean_words(text)
    if len(words) < 6:
        return False
    if len(set(words)) / len(words) < 0.4:
        return True
    top = max(words.count(w) for w in set(words))
    return top / len(words) > 0.35


def _is_silence(text: str, no_speech_prob: float, prompt: Optional[str]) -> bool:
    """True when the 'transcript' is really silence, noise, or an echo of the prompt."""
    words = _clean_words(text)
    if not words:
        return True
    if " ".join(words) in _SILENCE_PHRASES and no_speech_prob > 0.2:
        return True
    if no_speech_prob >= 0.8:
        return True
    if prompt and len(words) >= 4:
        prompt_words = set(_clean_words(prompt))
        if sum(w in prompt_words for w in words) / len(words) >= 0.85:
            return True  # Whisper repeated its priming sentence
    return False


class GroqWhisperSTT(BaseSTT):
    """Whisper-large-v3 on Groq's free API — no model on this machine.

    The language the farmer chose is forced (Whisper often confuses Hindi and
    Marathi on short clips). Silence and noise come back as text="" with
    no_speech=True, so the app can ask the farmer to speak again.
    """

    def __init__(self, client=None) -> None:
        self._client = client

    @property
    def model_id(self) -> str:
        return f"groq/{self.client.stt_model}"

    @property
    def client(self):
        if self._client is None:
            from app.models.groq_client import get_groq_client
            self._client = get_groq_client()
        return self._client

    def transcribe(self, audio_path: str, language: Optional[str] = None,
                   translate: bool = False) -> dict:
        lang = language if language in _WHISPER_LANG_MAP else None
        prompt = _GROQ_STT_PROMPTS.get(lang or "")
        r = self.client.transcribe(audio_path, language=lang, prompt=prompt)
        silent = _is_silence(r["text"], r.get("no_speech_prob") or 0.0, prompt)
        return {
            "text": "" if silent else r["text"],
            "language": lang or "unknown",
            "language_name": _WHISPER_LANG_MAP.get(lang, "unknown"),
            "duration": r.get("duration"),
            "no_speech": silent,
            "raw_text": r["text"],
        }


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
    from app.config import STT_ENGINE
    if use_stub:
        return StubSTT()
    if STT_ENGINE == "groq":
        return GroqWhisperSTT()
    return WhisperSTT(device=device)
