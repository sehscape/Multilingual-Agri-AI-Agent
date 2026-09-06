"""Tests for the STT module – Phase 2.

Unit tests (StubSTT) run without any model download.
Integration test (WhisperSTT) is marked slow and requires the model to be cached.
Run unit tests only: pytest tests/test_stt.py -m "not slow"
Run all tests:       pytest tests/test_stt.py
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.stt import StubSTT, WhisperSTT, get_stt, _WHISPER_LANG_MAP, _WHISPER_LANG_REVERSE


# ─── Language mapping tests ────────────────────────────────────────────────────

def test_whisper_lang_map_contains_indic_and_english():
    assert {"hi", "mr", "pa", "en"}.issubset(_WHISPER_LANG_MAP.keys())

def test_whisper_lang_map_values():
    assert _WHISPER_LANG_MAP["hi"] == "hindi"
    assert _WHISPER_LANG_MAP["mr"] == "marathi"
    assert _WHISPER_LANG_MAP["pa"] == "punjabi"
    assert _WHISPER_LANG_MAP["en"] == "english"

def test_whisper_lang_reverse():
    assert _WHISPER_LANG_REVERSE["hindi"]   == "hi"
    assert _WHISPER_LANG_REVERSE["marathi"] == "mr"
    assert _WHISPER_LANG_REVERSE["punjabi"] == "pa"
    assert _WHISPER_LANG_REVERSE["english"] == "en"


# ─── StubSTT tests ────────────────────────────────────────────────────────────

class TestStubSTT:
    def setup_method(self):
        # Reset cycle index so each test class starts at Hindi
        StubSTT._idx = 0
        self.stt = StubSTT()

    def test_returns_dict_with_required_keys(self):
        result = self.stt.transcribe("fake_path.wav")
        assert isinstance(result, dict)
        assert "text" in result
        assert "language" in result
        assert "language_name" in result

    def test_text_is_nonempty(self):
        result = self.stt.transcribe("fake.wav")
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0

    def test_first_stub_is_hindi(self):
        result = self.stt.transcribe("fake.wav")
        assert result["language"] == "hi"
        assert result["language_name"] == "hindi"

    def test_second_stub_is_marathi(self):
        self.stt.transcribe("fake.wav")          # hindi (index 0)
        result = self.stt.transcribe("fake.wav") # marathi (index 1)
        assert result["language"] == "mr"
        assert "कांद्या" in result["text"]

    def test_third_stub_is_punjabi(self):
        self.stt.transcribe("fake.wav")
        self.stt.transcribe("fake.wav")
        result = self.stt.transcribe("fake.wav")
        assert result["language"] == "pa"
        assert "ਕਣਕ" in result["text"]

    def test_cycle_wraps_around(self):
        for _ in range(3):
            self.stt.transcribe("fake.wav")
        result = self.stt.transcribe("fake.wav")   # index 3 → wraps to 0 (hindi)
        assert result["language"] == "hi"


# ─── Factory tests ─────────────────────────────────────────────────────────────

def test_get_stt_stub():
    stt = get_stt(use_stub=True)
    assert isinstance(stt, StubSTT)

def test_get_stt_whisper_returns_instance():
    stt = get_stt(use_stub=False)
    assert isinstance(stt, WhisperSTT)

def test_whisper_not_loaded_before_first_call():
    stt = WhisperSTT()
    assert stt._model is None       # lazy: model not loaded at construction
    assert stt._processor is None


# ─── Integration test (requires model download) ───────────────────────────────

@pytest.mark.slow
def test_whisper_auto_detects_language(tmp_path):
    """
    Real transcription test – requires torch + transformers + model download.
    Uses whisper-tiny (WHISPER_MODEL_ID in .env) for speed on CPU.
    Run with: pytest tests/test_stt.py -m slow

    Silence input → Whisper may return empty or filler text but should not crash,
    and must return a language key in the result.
    """
    import numpy as np
    import soundfile as sf

    # 2 seconds of silence at 16 kHz
    audio = np.zeros(32000, dtype=np.float32)
    audio_path = str(tmp_path / "test_audio.wav")
    sf.write(audio_path, audio, 16000)

    stt = WhisperSTT()              # uses WHISPER_MODEL_ID from .env
    result = stt.transcribe(audio_path)    # no language hint — auto-detect

    assert "text" in result
    assert "language" in result
    assert "language_name" in result
    assert isinstance(result["text"], str)
    # language must be a known ISO code or "unknown"
    assert result["language"] in {"hi", "mr", "pa", "en", "unknown"}
