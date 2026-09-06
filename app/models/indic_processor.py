"""Pure-Python IndicProcessor shim.

Replaces the Cython-compiled indictranstoolkit.IndicProcessor which requires
Microsoft Visual C++ Build Tools to compile on Windows. Provides the same
interface expected by translation.py.

Uses indic-nlp-library (pure Python) for Indic normalization/tokenization
and sacremoses (pure Python) for English Moses tokenization.
"""
from __future__ import annotations

import unicodedata
from typing import List

# Flores-200 lang code → indic-nlp-library ISO code
_FLORES_TO_ISO: dict[str, str] = {
    "hin_Deva": "hi",
    "mar_Deva": "mr",
    "pan_Guru": "pa",
    "eng_Latn": "en",
}


class IndicProcessor:
    """
    Inference-mode IndicProcessor using indic-nlp-library + sacremoses.
    Matches the public interface of IndicTransToolkit.IndicProcessor(inference=True).
    """

    def __init__(self, inference: bool = True) -> None:
        self._normalizers: dict[str, object] = {}
        self._moses_tok = None
        self._moses_detok = None

    # ── lazy loaders ────────────────────────────────────────────────────────────

    def _get_normalizer(self, iso: str):
        if iso not in self._normalizers:
            try:
                from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
                self._normalizers[iso] = IndicNormalizerFactory().get_normalizer(iso)
            except Exception:
                self._normalizers[iso] = None
        return self._normalizers[iso]

    def _get_moses_tokenizer(self):
        if self._moses_tok is None:
            from sacremoses import MosesTokenizer
            self._moses_tok = MosesTokenizer(lang="en")
        return self._moses_tok

    def _get_moses_detokenizer(self):
        if self._moses_detok is None:
            from sacremoses import MosesDetokenizer
            self._moses_detok = MosesDetokenizer(lang="en")
        return self._moses_detok

    # ── public API ───────────────────────────────────────────────────────────────

    def preprocess_batch(
        self, sentences: List[str], src_lang: str, tgt_lang: str
    ) -> List[str]:
        iso = _FLORES_TO_ISO.get(src_lang, "")
        is_latin = src_lang.endswith("_Latn") or iso == "en"

        out = []
        for sent in sentences:
            sent = unicodedata.normalize("NFC", sent.strip())
            if is_latin:
                try:
                    sent = self._get_moses_tokenizer().tokenize(
                        sent, return_str=True, escape=False
                    )
                except Exception:
                    pass
            elif iso and iso != "en":
                norm = self._get_normalizer(iso)
                if norm:
                    try:
                        sent = norm.normalize(sent)
                    except Exception:
                        pass
                try:
                    from indicnlp.tokenize import indic_tokenize
                    sent = " ".join(indic_tokenize.trivial_tokenize(sent, iso))
                except Exception:
                    pass
            out.append(sent)
        return out

    def postprocess_batch(self, translations: List[str], lang: str) -> List[str]:
        iso = _FLORES_TO_ISO.get(lang, "")
        is_latin = lang.endswith("_Latn") or iso == "en"

        out = []
        for sent in translations:
            sent = sent.strip()
            if is_latin:
                try:
                    sent = self._get_moses_detokenizer().detokenize(
                        sent.split(), return_str=True, unescape=False
                    )
                except Exception:
                    pass
            elif iso and iso != "en":
                norm = self._get_normalizer(iso)
                if norm:
                    try:
                        sent = norm.normalize(sent)
                    except Exception:
                        pass
            out.append(sent)
        return out
