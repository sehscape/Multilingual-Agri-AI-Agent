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

import re
import time
from abc import ABC, abstractmethod
from typing import Optional

from app.config import (
    TRANSLATION_MODEL_INDIC_EN,
    TRANSLATION_MODEL_EN_INDIC,
    INDICTRANS2_LANG_CODES,
    NLLB_MODEL_ID,
    TRANSLATION_ENGINE,
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


class NLLBTranslator(BaseTranslator):
    """
    CPU translator backed by Meta's NLLB-200 (distilled 600M, ~2.5 GB, ungated).

    For machines without a GPU, a Groq key, or access to the gated IndicTrans2
    checkpoints. About 3 s per sentence pair on a laptop CPU.

    The rule-based English answer is translated a sentence at a time (short
    inputs translate far better than a whole answer), in one batch. Section
    labels and growth stages come from the hand-written glossary instead of
    the model — see app/models/agri_glossary.py for why.
    """

    _BATCH = 8

    def __init__(self, device: str = "cpu") -> None:
        import threading

        self.device = device
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str, str], str] = {}

    def _load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            t0 = time.time()
            logger.info("Loading NLLB translator: %s", NLLB_MODEL_ID)
            self._tokenizer = AutoTokenizer.from_pretrained(NLLB_MODEL_ID)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(NLLB_MODEL_ID).to(self.device)
            self._model.eval()
            logger.info("NLLB loaded in %.1fs.", time.time() - t0)

    def _translate_batch(self, texts: list[str], src: str, tgt: str) -> list[str]:
        """Translate short segments, reusing earlier results."""
        todo = [x for x in dict.fromkeys(texts) if (src, tgt, x) not in self._cache]
        if todo:
            import torch

            self._load()
            src_code, tgt_code = INDICTRANS2_LANG_CODES[src], INDICTRANS2_LANG_CODES[tgt]
            for i in range(0, len(todo), self._BATCH):
                chunk = todo[i:i + self._BATCH]
                with self._lock:  # the tokenizer's src_lang is shared state
                    self._tokenizer.src_lang = src_code
                    inputs = self._tokenizer(chunk, return_tensors="pt", padding=True,
                                             truncation=True, max_length=256).to(self.device)
                    with torch.no_grad():
                        out = self._model.generate(
                            **inputs, num_beams=2, max_new_tokens=256,
                            forced_bos_token_id=self._tokenizer.convert_tokens_to_ids(tgt_code))
                    decoded = self._tokenizer.batch_decode(out, skip_special_tokens=True)
                for original, translated in zip(chunk, decoded):
                    self._cache[(src, tgt, original)] = translated.strip()
        return [self._cache[(src, tgt, x)] for x in texts]

    def translate_to_english(self, text: str, source_language: str) -> str:
        if source_language == "en" or not text.strip():
            return text
        if source_language not in INDICTRANS2_LANG_CODES:
            raise ValueError(f"Unsupported source language: {source_language!r}")
        t0 = time.time()
        result = self._translate_batch([text.strip()], source_language, "en")[0]
        logger.info("NLLB translate_to_english | %.2fs | %s→en", time.time() - t0, source_language)
        return result

    def translate_from_english(self, text: str, target_language: str) -> str:
        if target_language == "en" or not text.strip():
            return text
        if target_language not in INDICTRANS2_LANG_CODES:
            raise ValueError(f"Unsupported target language: {target_language!r}")
        t0 = time.time()
        plan = [_plan_line(line, target_language) for line in text.split("\n")]
        segments = [seg for line in plan for kind, seg in line if kind == "mt"]
        done = iter(self._translate_batch(segments, "en", target_language) if segments else [])
        result = "\n".join("".join(next(done) if kind == "mt" else seg for kind, seg in line)
                           for line in plan)
        logger.info("NLLB translate_from_english | %.2fs | en→%s | %d segment(s)",
                    time.time() - t0, target_language, len(segments))
        return result


# ── Answer segmentation for NLLBTranslator ────────────────────────────────────
_STAGE_SENTENCE = re.compile(
    r"^Your (?P<crop>[\w ]+?) crop is currently in the (?P<stage>.+?) stage\.$")
_STAGE_TEMPLATE = {
    "hi": "आपकी {crop} की फसल अभी {stage} की अवस्था में है।",
    "mr": "तुमचे {crop} पीक सध्या {stage} या अवस्थेत आहे.",
    "pa": "ਤੁਹਾਡੀ {crop} ਦੀ ਫਸਲ ਇਸ ਵੇਲੇ {stage} ਦੀ ਅਵਸਥਾ ਵਿੱਚ ਹੈ।",
}
_NUMBERED = re.compile(r"^(\s*\d+\.\s+)(?:([A-Z][A-Za-z ]+):\s+)?(.*)$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
# The model drops dashes between numbers ("3–5 cm" came out as "35 cm"), so
# ranges are spelled out first; it translates "3 to 5" correctly.
_RANGE = re.compile(r"(?<![A-Za-z\d.])(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)(?![\d.])")
# English wording the model reliably mistranslates, reworded before translation.
_REWORD = [
    (re.compile(r"\s+—\s+"), ", "),
    (re.compile(r"\bper hill\b"), "per planting spot"),    # not "per mountain"
    (re.compile(r"\blive weather\b"), "current weather"),  # not "living weather"
]


def _plan_line(line: str, lang: str) -> list[tuple[str, str]]:
    """A line of the English answer as pieces: ("mt", text) to machine-translate,
    ("fixed", text) to keep as written."""
    from app.models.agri_glossary import HEADINGS

    stripped = line.strip()
    if not stripped:
        return [("fixed", line)]
    if stripped.endswith(":") and stripped[:-1] in HEADINGS:
        return [("fixed", HEADINGS[stripped[:-1]][lang] + ":")]

    pieces: list[tuple[str, str]] = []
    m = _NUMBERED.match(line)
    label = None
    if m:
        pieces.append(("fixed", m.group(1)))
        label = m.group(2)
        if label and label in HEADINGS:
            pieces.append(("fixed", HEADINGS[label][lang] + ": "))
        elif label:
            pieces.append(("mt", label))
            pieces.append(("fixed", ": "))
        body = m.group(3)
    else:
        body = stripped

    # "Watch for: A, B, C" — pest names translate far better one at a time.
    separator = ", " if label == "Watch for" else " | "
    parts = [p.strip() for p in body.split(separator) if p.strip()]
    for i, part in enumerate(parts):
        if i:
            pieces.append(("fixed", separator))
        for j, sentence in enumerate(_SENTENCE_END.split(part)):
            if j:
                pieces.append(("fixed", " "))
            pieces.append(_plan_sentence(sentence, lang))
    return pieces


def _plan_sentence(sentence: str, lang: str) -> tuple[str, str]:
    from app.models.agri_glossary import stage_name
    from app.ui.i18n import crop_label

    m = _STAGE_SENTENCE.match(sentence.strip())
    if m:
        stage = stage_name(m.group("stage"), lang)
        if stage:
            crop = crop_label(m.group("crop").strip().lower(), lang)
            return ("fixed", _STAGE_TEMPLATE[lang].format(crop=crop, stage=stage))
    sentence = _RANGE.sub(r"\1 to \2", sentence)
    for pattern, replacement in _REWORD:
        sentence = pattern.sub(replacement, sentence)
    return ("mt", sentence)


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
    if TRANSLATION_ENGINE == "indictrans2":
        return IndicTrans2Translator(device=device)
    return NLLBTranslator(device=device)
