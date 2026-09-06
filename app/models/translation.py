"""IndicTrans2 translation model abstraction.

Architecture role:
    Input boundary:  original_text (regional) → translate_to_english() → english_text
    Output boundary: english_answer           → translate_from_english() → regional_answer

IndicTrans2 uses two separate checkpoints:
    Indic → English : ai4bharat/indictrans2-indic-en-1B
    English → Indic : ai4bharat/indictrans2-en-indic-1B

Language codes (Flores-200 / IndicTrans2):
    Hindi   → hin_Deva
    Marathi → mar_Deva
    Punjabi → pan_Guru
    English → eng_Latn

Dependencies (install in Phase 3):
    pip install git+https://github.com/VarunGumma/IndicTransTokenizer
    pip install sentencepiece sacremoses
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from app.config import (
    TRANSLATION_MODEL_INDIC_EN,
    TRANSLATION_MODEL_EN_INDIC,
    INDICTRANS2_LANG_CODES,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseTranslator(ABC):
    """Interface every translation backend must implement."""

    @abstractmethod
    def translate_to_english(self, text: str, source_language: str) -> str:
        """Translate regional-language text to English."""

    @abstractmethod
    def translate_from_english(self, text: str, target_language: str) -> str:
        """Translate English text to a regional language."""


class IndicTrans2Translator(BaseTranslator):
    """
    Production translator backed by IndicTrans2.

    Loads lazily on first use to avoid blocking app startup.
    Requires the IndicTransTokenizer library (Phase 3 dependency).
    """

    def __init__(self, device: str = "cpu") -> None:
        self.device = device
        self._model_indic_en = None
        self._model_en_indic = None
        self._tokenizer_indic_en = None
        self._tokenizer_en_indic = None
        self._processor = None

    def _load_indic_en(self) -> None:
        if self._model_indic_en is not None:
            return
        logger.info("Loading IndicTrans2 Indic→EN model: %s", TRANSLATION_MODEL_INDIC_EN)
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            try:
                from IndicTransTokenizer import IndicProcessor
            except ImportError:
                from app.models.indic_processor import IndicProcessor

            self._processor = IndicProcessor(inference=True)
            self._tokenizer_indic_en = AutoTokenizer.from_pretrained(
                TRANSLATION_MODEL_INDIC_EN, trust_remote_code=True
            )
            self._model_indic_en = AutoModelForSeq2SeqLM.from_pretrained(
                TRANSLATION_MODEL_INDIC_EN, trust_remote_code=True
            ).to(self.device)
            logger.info("IndicTrans2 Indic→EN loaded.")
        except ImportError as e:
            raise RuntimeError(
                "IndicTransTokenizer not installed. "
                "Run: pip install git+https://github.com/VarunGumma/IndicTransTokenizer"
            ) from e

    def _load_en_indic(self) -> None:
        if self._model_en_indic is not None:
            return
        logger.info("Loading IndicTrans2 EN→Indic model: %s", TRANSLATION_MODEL_EN_INDIC)
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            if self._processor is None:
                try:
                    from IndicTransTokenizer import IndicProcessor
                except ImportError:
                    from app.models.indic_processor import IndicProcessor
                self._processor = IndicProcessor(inference=True)

            self._tokenizer_en_indic = AutoTokenizer.from_pretrained(
                TRANSLATION_MODEL_EN_INDIC, trust_remote_code=True
            )
            self._model_en_indic = AutoModelForSeq2SeqLM.from_pretrained(
                TRANSLATION_MODEL_EN_INDIC, trust_remote_code=True
            ).to(self.device)
            logger.info("IndicTrans2 EN→Indic loaded.")
        except ImportError as e:
            raise RuntimeError(
                "IndicTransTokenizer not installed. "
                "Run: pip install git+https://github.com/VarunGumma/IndicTransTokenizer"
            ) from e

    def _run_translation(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        model,
        tokenizer,
    ) -> str:
        import torch

        batch = self._processor.preprocess_batch([text], src_lang=src_lang, tgt_lang=tgt_lang)
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt").to(
            self.device
        )
        with torch.no_grad():
            output_tokens = model.generate(
                **inputs,
                num_beams=4,
                max_length=256,
            )
        with tokenizer.as_target_tokenizer():
            decoded = tokenizer.batch_decode(output_tokens.tolist(), skip_special_tokens=True)
        return self._processor.postprocess_batch(decoded, lang=tgt_lang)[0]

    def translate_to_english(self, text: str, source_language: str) -> str:
        src_code = INDICTRANS2_LANG_CODES.get(source_language)
        if not src_code:
            raise ValueError(f"Unsupported source language: {source_language!r}")
        if source_language == "en":
            return text  # already English

        t0 = time.time()
        self._load_indic_en()
        result = self._run_translation(
            text,
            src_lang=src_code,
            tgt_lang=INDICTRANS2_LANG_CODES["en"],
            model=self._model_indic_en,
            tokenizer=self._tokenizer_indic_en,
        )
        logger.info("translate_to_english | %.2fs | %s→en", time.time() - t0, source_language)
        return result

    def translate_from_english(self, text: str, target_language: str) -> str:
        tgt_code = INDICTRANS2_LANG_CODES.get(target_language)
        if not tgt_code:
            raise ValueError(f"Unsupported target language: {target_language!r}")
        if target_language == "en":
            return text

        t0 = time.time()
        self._load_en_indic()
        result = self._run_translation(
            text,
            src_lang=INDICTRANS2_LANG_CODES["en"],
            tgt_lang=tgt_code,
            model=self._model_en_indic,
            tokenizer=self._tokenizer_en_indic,
        )
        logger.info(
            "translate_from_english | %.2fs | en→%s", time.time() - t0, target_language
        )
        return result


class PassthroughTranslator(BaseTranslator):
    """
    Stub translator for local dev / unit tests (no model needed).
    Returns the input text unchanged with a [STUB] tag.
    """

    def translate_to_english(self, text: str, source_language: str) -> str:
        logger.warning("PassthroughTranslator: returning original text as-is (no model loaded).")
        return f"[STUB-EN] {text}"

    def translate_from_english(self, text: str, target_language: str) -> str:
        logger.warning("PassthroughTranslator: returning English text as-is (no model loaded).")
        return f"[STUB-{target_language.upper()}] {text}"


def get_translator(device: str = "cpu", use_stub: bool = False) -> BaseTranslator:
    """Factory – returns a real or stub translator based on the flag."""
    if use_stub:
        return PassthroughTranslator()
    return IndicTrans2Translator(device=device)
