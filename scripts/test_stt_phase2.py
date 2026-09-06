"""
Phase 2 STT test script.

What this does:
  1. Generates short test audio clips for Hindi, Marathi, Punjabi using gTTS
  2. Runs WhisperSTT (whisper-tiny locally, whisper-large-v3 on HF Spaces)
  3. Prints transcription results + latency

Usage:
    # Activate venv first, then:
    python scripts/test_stt_phase2.py

    # Test one language only:
    python scripts/test_stt_phase2.py --lang hi

    # Use a real audio file you recorded:
    python scripts/test_stt_phase2.py --audio path/to/your_file.wav --lang mr

Notes:
    - First run downloads the Whisper model (whisper-tiny ~74 MB on CPU).
    - CPU transcription takes ~30-90 seconds per clip — this is expected.
    - On HF Spaces GPU, whisper-large-v3 takes ~3-8 seconds.
"""
import argparse
import os
import sys
import time
import tempfile

# Force UTF-8 output so Indic script prints correctly on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.logging import get_logger
from app.models.stt import WhisperSTT, StubSTT

logger = get_logger("test_stt_phase2")

# ─── Test sentences (realistic agricultural queries) ──────────────────────────
TEST_SENTENCES = {
    "hi": "मेरी गेहूं की फसल चालीस दिन की है। मौसम कैसा रहेगा?",
    "mr": "माझ्या कांद्याच्या पिकाला पंचेचाळीस दिवस झाले आहेत.",
    "pa": "ਮੇਰੀ ਕਣਕ ਦੀ ਫ਼ਸਲ ਚਾਲੀ ਦਿਨ ਦੀ ਹੈ।",
}

# gTTS language codes (slightly different from Whisper)
GTTS_LANG_CODES = {
    "hi": "hi",
    "mr": "mr",
    "pa": "pa",
}


def generate_audio(text: str, lang: str, output_path: str) -> str:
    """Generate WAV audio from text using gTTS, returns path to WAV file."""
    from gtts import gTTS
    import pydub  # for mp3 → wav

    mp3_path = output_path.replace(".wav", ".mp3")
    tts = gTTS(text=text, lang=GTTS_LANG_CODES[lang], slow=False)
    tts.save(mp3_path)

    # Convert mp3 → wav (Whisper prefers wav/16kHz)
    audio = pydub.AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(output_path, format="wav")
    os.remove(mp3_path)
    return output_path


def run_stub_test():
    """Quick sanity check using StubSTT — no model download needed."""
    print("\n" + "─" * 60)
    print("STUB TEST (no model download)")
    print("─" * 60)
    stt = StubSTT()
    for lang, name in [("hi", "Hindi"), ("mr", "Marathi"), ("pa", "Punjabi")]:
        result = stt.transcribe("fake.wav", language=lang)
        print(f"  [{name}] text : {result['text'][:60]}…")
        print(f"          lang : {result['language']}")
    print("Stub test PASSED ✓")


def run_whisper_test(audio_path: str, lang: str, lang_name: str):
    """Run real WhisperSTT on a single audio file."""
    print(f"\n  Transcribing {lang_name} audio…  (may take 30–90s on CPU)")
    stt = WhisperSTT()  # model_id from WHISPER_MODEL_ID env var

    t0 = time.time()
    result = stt.transcribe(audio_path, language=lang)
    elapsed = time.time() - t0

    print(f"  ✓ Transcription : {result['text']}")
    print(f"    Language      : {result['language']}")
    print(f"    Latency       : {elapsed:.1f}s")
    return result


def main():
    parser = argparse.ArgumentParser(description="Phase 2 STT test")
    parser.add_argument("--lang", choices=["hi", "mr", "pa", "all"], default="all",
                        help="Language to test (default: all)")
    parser.add_argument("--audio", default=None,
                        help="Path to an existing audio file (skips gTTS generation)")
    parser.add_argument("--stub-only", action="store_true",
                        help="Run only the stub test (no model download)")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  PHASE 2 — Whisper STT Test")
    print(f"  WHISPER_MODEL_ID : {os.getenv('WHISPER_MODEL_ID', 'openai/whisper-large-v3')}")
    print("=" * 60)

    # Always run stub test first
    run_stub_test()

    if args.stub_only:
        print("\nStub-only mode. Exiting.")
        return

    # Determine which languages to test
    langs = {"hi": "Hindi", "mr": "Marathi", "pa": "Punjabi"}
    if args.lang != "all":
        langs = {args.lang: langs[args.lang]}

    print("\n" + "─" * 60)
    print(f"WHISPER TEST — {', '.join(langs.values())}")
    print("─" * 60)
    print("NOTE: First run downloads the model. Subsequent runs use cache.")

    with tempfile.TemporaryDirectory() as tmpdir:
        for lang, lang_name in langs.items():
            print(f"\n[{lang_name}]")

            if args.audio:
                audio_path = args.audio
                print(f"  Using provided audio: {audio_path}")
            else:
                wav_path = os.path.join(tmpdir, f"test_{lang}.wav")
                sentence = TEST_SENTENCES[lang]
                print(f"  Generating audio : '{sentence[:50]}…'")
                try:
                    generate_audio(sentence, lang, wav_path)
                    audio_path = wav_path
                    print(f"  Audio generated  : {wav_path}")
                except Exception as e:
                    print(f"  gTTS failed: {e}")
                    print("  → Try: python scripts/test_stt_phase2.py --stub-only")
                    continue

            try:
                run_whisper_test(audio_path, lang, lang_name)
            except Exception as e:
                print(f"  ✗ Error: {e}")
                print("  → Check internet connection (model download) and ffmpeg install.")

    print("\n" + "=" * 60)
    print("  Phase 2 test complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
