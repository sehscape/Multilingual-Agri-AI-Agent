"""Phase 10 smoke-test: output boundary (translate → TTS → audio).

Covers:
  1. gTTS engine produces real audio for en / hi / mr / pa.
  2. Factory (get_tts) selects the right engine per config value.
  3. StubTTS returns no audio (graceful).
  4. Production IndicParlerTTS guards a missing dependency with a clear message
     (verified WITHOUT downloading the model).
  5. The full output stage (translate + TTS) yields a playable audio file.

Usage (from project root, venv active):
    python scripts/test_tts_phase10.py

Note: gTTS needs internet (like the weather/scheme tests).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.models.tts import GttsTTS, StubTTS, IndicParlerTTS, get_tts

_failures = 0
_total = 0


def check(label, ok, detail=""):
    global _failures, _total
    _total += 1
    if not ok:
        _failures += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))


def _valid_audio(path) -> bool:
    return bool(path) and os.path.exists(path) and os.path.getsize(path) > 0


TEXTS = {
    "en": "Your wheat crop needs a second irrigation now.",
    "hi": "आपकी गेहूं की फसल को अब दूसरी सिंचाई की जरूरत है।",
    "mr": "तुमच्या गव्हाच्या पिकाला आता दुसरे पाणी द्या.",
    "pa": "ਤੁਹਾਡੀ ਕਣਕ ਦੀ ਫਸਲ ਨੂੰ ਹੁਣ ਦੂਜੀ ਸਿੰਚਾਈ ਦੀ ਲੋੜ ਹੈ।",
}


def run():
    print("=" * 60 + "\n1. gTTS produces audio per language\n" + "=" * 60)
    tts = GttsTTS()
    for lang, text in TEXTS.items():
        path = tts.generate(text, lang)
        size = os.path.getsize(path) if _valid_audio(path) else 0
        check(f"gTTS {lang}", _valid_audio(path), f"{size} bytes")

    print("\n" + "=" * 60 + "\n2. Factory selects engine by name\n" + "=" * 60)
    check("get_tts('gtts') → GttsTTS", isinstance(get_tts(engine="gtts"), GttsTTS))
    check("get_tts('parler') → IndicParlerTTS", isinstance(get_tts(engine="parler"), IndicParlerTTS))
    check("get_tts('stub') → StubTTS", isinstance(get_tts(engine="stub"), StubTTS))

    print("\n" + "=" * 60 + "\n3. StubTTS returns no audio (graceful)\n" + "=" * 60)
    check("StubTTS → None", StubTTS().generate("hello", "hi") is None)

    print("\n" + "=" * 60 + "\n4. Production Parler guards missing dependency\n" + "=" * 60)
    try:
        IndicParlerTTS().generate("test", "hi")
        check("Parler raises when not installed", False, "no error raised")
    except RuntimeError as e:
        check("Parler raises clear install hint", "not installed" in str(e))
    except Exception as e:  # any other error means the guard is wrong
        check("Parler raises RuntimeError", False, f"got {type(e).__name__}: {e}")

    print("\n" + "=" * 60 + "\n5. Full output stage: translate + TTS → audio\n" + "=" * 60)
    from app.agents.state import AgentState
    from app.ui.gradio_app import _run_output_stage
    state = AgentState(
        source_language="hi",
        english_answer="Your wheat crop needs a second irrigation now. Apply 25 kg urea.",
    )
    trace = []
    path = _run_output_stage(state, trace)
    check("output stage yields audio", _valid_audio(path))
    check("regional_answer populated", bool(state.regional_answer))
    print("   trace:")
    for t in trace:
        print(f"     {t}")

    print("\n" + "=" * 60)
    passed = _total - _failures
    print(f"Result: {passed}/{_total} checks passed — "
          f"{'ALL PASSED' if _failures == 0 else f'{_failures} FAILED'}")
    sys.exit(0 if _failures == 0 else 1)


if __name__ == "__main__":
    run()
