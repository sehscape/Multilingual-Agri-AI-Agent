"""Gradio UI.

Phase 2: voice recording → Whisper STT (auto language detection) → regional text.
Phase 3: regional text → IndicTrans2 → English text.
Phases 4-10 will add: Intent → Agent → IndicTrans2 → Indic TTS.
"""
import time
import gradio as gr

from app.utils.logging import get_logger
from app.config import SUPPORTED_LANGUAGES, DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION

logger = get_logger(__name__)

_LANG_DISPLAY: dict[str, str] = {
    "hi": "Hindi",
    "mr": "Marathi",
    "pa": "Punjabi",
    "en": "English",
    "unknown": "Unknown",
}

# Singletons — loaded once on first call
_stt = None
_translator = None


def _get_stt():
    global _stt
    if _stt is None:
        from app.models.stt import WhisperSTT
        _stt = WhisperSTT()
    return _stt


def _get_translator():
    global _translator
    if _translator is None:
        from app.models.translation import get_translator
        _translator = get_translator(use_stub=USE_STUB_TRANSLATION)
    return _translator


def _run_pipeline(audio, location: str):
    """
    Phase 3 pipeline:
        microphone audio
        → [Phase 2] Whisper STT → regional text + detected language
        → [Phase 3] IndicTrans2 → English text
        → [Phase 4-10] stubs
    """
    trace_lines = [f"Location : {location or 'not provided'}"]
    transcription = ""
    english_text = ""
    answer = ""
    detected_display = ""

    if audio is None:
        return "", "", "", None, "No audio recorded. Press the microphone button and speak.", ""

    # ── Step 1: Whisper STT + auto language detection (Phase 2) ──────────────
    trace_lines.append(f"\nStep 1 | Whisper STT  [{WHISPER_MODEL_ID}]")
    try:
        t0 = time.time()
        result = _get_stt().transcribe(audio)
        transcription = result["text"]
        iso_lang = result["language"]
        lang_name = result.get("language_name", iso_lang)
        elapsed = time.time() - t0

        detected_display = _LANG_DISPLAY.get(iso_lang, lang_name.capitalize())
        trace_lines.append(f"         Detected language : {detected_display} ({iso_lang})")
        trace_lines.append(f"         Transcribed in {elapsed:.1f}s")
        trace_lines.append(f"         '{transcription}'")
    except Exception as e:
        logger.error("STT failed: %s", e)
        trace_lines.append(f"         ERROR: {e}")
        return "", "", f"Speech recognition failed: {e}", None, "\n".join(trace_lines), ""

    # ── Step 2: IndicTrans2 regional → English (Phase 3) ─────────────────────
    stub_label = " [STUB]" if USE_STUB_TRANSLATION else ""
    trace_lines.append(f"\nStep 2 | IndicTrans2 {detected_display} → English{stub_label}")
    try:
        t0 = time.time()
        if iso_lang in ("en", "unknown"):
            english_text = transcription
            trace_lines.append("         Source is English — no translation needed.")
        else:
            translator = _get_translator()
            english_text = translator.translate_to_english(transcription, iso_lang)
            elapsed = time.time() - t0
            trace_lines.append(f"         Translated in {elapsed:.1f}s")
            trace_lines.append(f"         '{english_text}'")
    except Exception as e:
        logger.error("Translation failed: %s", e)
        trace_lines.append(f"         ERROR: {e}")
        english_text = f"[Translation failed: {e}]"

    # ── Steps 3–7: stubs (later phases) ──────────────────────────────────────
    detected_display_full = _LANG_DISPLAY.get(iso_lang, lang_name.capitalize())
    trace_lines.append("\nStep 3 | Intent extraction                     [Phase 4]")
    trace_lines.append("Step 4 | Agent tool calls                      [Phase 5-8]")
    trace_lines.append("Step 5 | LLM reasoning → English answer        [Phase 4]")
    trace_lines.append(f"Step 6 | IndicTrans2 English → {detected_display_full:<8}    [Phase 10]")
    trace_lines.append(f"Step 7 | Indic TTS → {detected_display_full} audio          [Phase 10]")

    answer = (
        f"[Phase 3 — STT + Translation]\n\n"
        f"Detected language: {detected_display_full}\n\n"
        f"You said ({detected_display_full}):\n{transcription}\n\n"
        f"English translation:\n{english_text}\n\n"
        "Agent reasoning and voice response will be added in Phases 4–10."
    )

    return (
        transcription,
        english_text,
        answer,
        None,
        "\n".join(trace_lines),
        detected_display,
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Multilingual Agri Assistant") as demo:
        gr.Markdown(
            "# Multilingual Agricultural Assistant\n"
            "### Speak your farming question in Hindi, Marathi, or Punjabi\n"
            f"*STT model: `{WHISPER_MODEL_ID}` — language is auto-detected from your speech*"
        )

        with gr.Row():
            # ── Left column: inputs ───────────────────────────────────────────
            with gr.Column(scale=1):
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="Record your question",
                )
                location_input = gr.Textbox(
                    label="Your location (e.g. Nashik, Maharashtra)",
                    placeholder="Enter city, state",
                )
                submit_btn = gr.Button("Transcribe & Translate", variant="primary")

            # ── Right column: outputs ─────────────────────────────────────────
            with gr.Column(scale=2):
                detected_language_output = gr.Textbox(
                    label="Detected language",
                    lines=1,
                    interactive=False,
                    placeholder="Language will be auto-detected from your speech...",
                )
                transcription_output = gr.Textbox(
                    label="What you said (regional language)",
                    lines=3,
                    interactive=False,
                    placeholder="Your spoken words will appear here after transcription...",
                )
                english_translation_output = gr.Textbox(
                    label="English translation (IndicTrans2)",
                    lines=3,
                    interactive=False,
                    placeholder="The English translation will appear here...",
                )
                text_output = gr.Textbox(
                    label="Pipeline summary",
                    lines=8,
                    interactive=False,
                    placeholder="The assistant's answer will appear here...",
                )
                audio_output = gr.Audio(
                    label="Voice response",
                    autoplay=True,
                    visible=True,
                )
                trace_output = gr.Textbox(
                    label="Pipeline trace (dev mode)",
                    lines=12,
                    interactive=False,
                    visible=DEV_MODE,
                )

        submit_btn.click(
            fn=_run_pipeline,
            inputs=[audio_input, location_input],
            outputs=[
                transcription_output,
                english_translation_output,
                text_output,
                audio_output,
                trace_output,
                detected_language_output,
            ],
        )

    return demo
