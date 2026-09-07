"""Gradio UI.

Phase 2:  voice recording → Whisper STT (auto language detection) → regional text.
Phase 3:  regional text → IndicTrans2 → English text.
Phase 4:  English text → Intent extraction.
Phase 8:  Orchestrator → crop / weather / scheme tools → LLM answer generation.
Phase 10: IndicTrans2 English → regional + Indic TTS (pending).
"""
import time
import gradio as gr

from app.utils.logging import get_logger
from app.config import DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION, USE_STUB_LLM

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
_llm = None
_orchestrator = None


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


def _get_llm():
    global _llm
    if _llm is None:
        from app.models.llm import get_llm
        _llm = get_llm(use_stub=USE_STUB_LLM)
    return _llm


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from app.agents.orchestrator import get_orchestrator
        _orchestrator = get_orchestrator(_get_llm())
    return _orchestrator


def _run_pipeline(audio, location: str):
    """
    Phase 8 pipeline:
        audio → [Ph2] Whisper STT → regional text + language
              → [Ph3] IndicTrans2 → English text
              → [Ph4] Intent extraction → intent, crop, stage, flags
              → [Ph8] Orchestrator:
                        ├─ Crop knowledge tool  (if needs_crop_info)
                        ├─ Weather tool         (if needs_weather)
                        ├─ Scheme RAG tool      (if needs_scheme)
                        └─ LLM answer generation
              → [Ph10] IndicTrans2 English → regional + Indic TTS (pending)
    """
    from app.agents.state import AgentState
    from app.agents.intent import extract_intent

    trace_lines = [f"Location : {location or 'not provided'}"]
    detected_display = ""

    if audio is None:
        return "", "", "", "", None, "No audio recorded. Press the microphone button and speak.", ""

    # ── Step 1: Whisper STT (Phase 2) ─────────────────────────────────────────
    trace_lines.append(f"\nStep 1 | Whisper STT  [{WHISPER_MODEL_ID}]")
    try:
        t0 = time.time()
        stt_result = _get_stt().transcribe(audio)
        transcription = stt_result["text"]
        iso_lang = stt_result["language"]
        lang_name = stt_result.get("language_name", iso_lang)
        detected_display = _LANG_DISPLAY.get(iso_lang, lang_name.capitalize())
        trace_lines.append(f"         Detected : {detected_display} ({iso_lang}) in {time.time()-t0:.1f}s")
        trace_lines.append(f"         '{transcription}'")
    except Exception as e:
        logger.error("STT failed: %s", e)
        return "", "", "", f"Speech recognition failed: {e}", None, "\n".join(trace_lines), ""

    # Build AgentState — single object travels through the whole pipeline
    state = AgentState(
        source_language=iso_lang,
        original_text=transcription,
        location=location.strip() or None,
    )

    # ── Step 2: IndicTrans2 regional → English (Phase 3) ─────────────────────
    stub_label = " [STUB]" if USE_STUB_TRANSLATION else ""
    trace_lines.append(f"\nStep 2 | IndicTrans2 {detected_display} → English{stub_label}")
    try:
        t0 = time.time()
        if iso_lang in ("en", "unknown"):
            state.english_text = transcription
            trace_lines.append("         Source is English — no translation needed.")
        else:
            state.english_text = _get_translator().translate_to_english(transcription, iso_lang)
            trace_lines.append(f"         Translated in {time.time()-t0:.1f}s")
            trace_lines.append(f"         '{state.english_text}'")
    except Exception as e:
        logger.error("Translation failed: %s", e)
        state.english_text = transcription
        trace_lines.append(f"         ERROR: {e} — using original text")

    # ── Step 3: Intent extraction (Phase 4) ──────────────────────────────────
    stub_label = " [STUB]" if USE_STUB_LLM else ""
    trace_lines.append(f"\nStep 3 | Intent extraction{stub_label}")
    t0 = time.time()
    state = extract_intent(state, _get_llm())
    trace_lines.append(f"         {state.trace[-1] if state.trace else 'done'} in {time.time()-t0:.1f}s")

    # ── Steps 4-6: Orchestrator — tools + LLM answer (Phase 8) ───────────────
    trace_lines.append(f"\nStep 4 | Agent orchestrator (Phase 8){stub_label}")
    t0 = time.time()
    state = _get_orchestrator().run(state)
    # Append all orchestrator traces
    for msg in state.trace[1:]:   # skip the intent trace already logged above
        trace_lines.append(f"         {msg}")
    trace_lines.append(f"         Orchestrator done in {time.time()-t0:.1f}s")

    trace_lines.append(f"\nStep 5 | IndicTrans2 English → {detected_display:<8}        [Phase 10]")
    trace_lines.append(f"Step 6 | Indic TTS → {detected_display} audio              [Phase 10]")

    intent_summary = (
        f"Intent   : {state.intent}\n"
        f"Crop     : {state.crop or '—'}\n"
        f"Stage    : {f'{state.crop_stage_days} days' if state.crop_stage_days else '—'}\n"
        f"Needs    : {'weather ' if state.needs_weather else ''}"
        f"{'crop_info ' if state.needs_crop_info else ''}"
        f"{'scheme' if state.needs_scheme else ''}"
    )

    return (
        transcription,
        state.english_text,
        intent_summary,
        state.english_answer,
        None,                        # audio output (Phase 10)
        "\n".join(trace_lines),
        detected_display,
    )


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Multilingual Agri Assistant") as demo:
        gr.Markdown(
            "# Multilingual Agricultural Assistant\n"
            "### Speak your farming question in Hindi, Marathi, or Punjabi\n"
            f"*STT: `{WHISPER_MODEL_ID}` · "
            f"Translation: {'stub' if USE_STUB_TRANSLATION else 'IndicTrans2'} · "
            f"LLM: {'stub' if USE_STUB_LLM else 'HF API'}*"
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
                submit_btn = gr.Button("Ask the Assistant", variant="primary")

            # ── Right column: outputs ─────────────────────────────────────────
            with gr.Column(scale=2):
                detected_language_output = gr.Textbox(
                    label="Detected language",
                    lines=1,
                    interactive=False,
                )
                transcription_output = gr.Textbox(
                    label="What you said (regional language)",
                    lines=3,
                    interactive=False,
                )
                english_translation_output = gr.Textbox(
                    label="English translation (IndicTrans2)",
                    lines=3,
                    interactive=False,
                )
                intent_output = gr.Textbox(
                    label="Intent extraction (Phase 4)",
                    lines=4,
                    interactive=False,
                )
                answer_output = gr.Textbox(
                    label="Answer (English — Phase 4)",
                    lines=10,
                    interactive=False,
                )
                audio_output = gr.Audio(
                    label="Voice response (Phase 10)",
                    autoplay=True,
                    visible=True,
                )
                trace_output = gr.Textbox(
                    label="Pipeline trace (dev mode)",
                    lines=14,
                    interactive=False,
                    visible=DEV_MODE,
                )

        submit_btn.click(
            fn=_run_pipeline,
            inputs=[audio_input, location_input],
            outputs=[
                transcription_output,
                english_translation_output,
                intent_output,
                answer_output,
                audio_output,
                trace_output,
                detected_language_output,
            ],
        )

    return demo
