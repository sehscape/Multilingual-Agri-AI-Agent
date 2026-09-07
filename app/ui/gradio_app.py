"""Gradio UI — redesigned for farmer-friendliness.

Phases wired:
  2  — Whisper STT (auto language detection)
  3  — IndicTrans2 regional → English
  4  — Intent extraction
  8  — Orchestrator (crop / weather / scheme tools + LLM answer)
  10 — IndicTrans2 English → regional + Indic TTS (pending)
"""
import time
import gradio as gr

from app.utils.logging import get_logger
from app.config import DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION, USE_STUB_LLM

logger = get_logger(__name__)

_LANG_DISPLAY = {"hi": "Hindi", "mr": "Marathi", "pa": "Punjabi",
                 "en": "English", "unknown": "Unknown"}

_LANG_FLAG = {"hi": "🇮🇳 Hindi", "mr": "🇮🇳 Marathi", "pa": "🇮🇳 Punjabi",
              "en": "🇬🇧 English", "unknown": "❓ Unknown"}

# ── Singletons ────────────────────────────────────────────────────────────────
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


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _run_pipeline(audio, location: str):
    """Full pipeline: STT → translate → intent → orchestrate → answer."""
    from app.agents.state import AgentState
    from app.agents.intent import extract_intent

    # Return signature:
    # detected_lang, transcription, english_text, answer, audio_out,
    # intent_box, tools_html, trace_box

    if audio is None:
        msg = "⚠️ No audio recorded. Click the microphone and speak your question."
        return "—", "", "", msg, None, "", _no_tools_html(), ""

    trace = []
    detected_display = "—"

    # ── Step 1: Whisper STT ───────────────────────────────────────────────────
    trace.append(f"[STT] Model: {WHISPER_MODEL_ID}")
    try:
        t0 = time.time()
        result = _get_stt().transcribe(audio)
        transcription = result["text"]
        iso_lang = result["language"]
        detected_display = _LANG_FLAG.get(iso_lang, iso_lang)
        trace.append(f"[STT] Detected: {detected_display} in {time.time()-t0:.1f}s")
        trace.append(f"[STT] '{transcription}'")
    except Exception as e:
        logger.error("STT failed: %s", e)
        return "—", "", "", f"❌ Speech recognition failed: {e}", None, "", _no_tools_html(), ""

    state = AgentState(
        source_language=iso_lang,
        original_text=transcription,
        location=location.strip() or None,
    )

    # ── Step 2: Translate regional → English ─────────────────────────────────
    stub_note = " [stub]" if USE_STUB_TRANSLATION else ""
    trace.append(f"[Translate{stub_note}] {_LANG_DISPLAY.get(iso_lang, iso_lang)} → English")
    try:
        t0 = time.time()
        if iso_lang in ("en", "unknown"):
            state.english_text = transcription
            trace.append("[Translate] Already English — skipped.")
        else:
            state.english_text = _get_translator().translate_to_english(transcription, iso_lang)
            trace.append(f"[Translate] Done in {time.time()-t0:.1f}s: '{state.english_text}'")
    except Exception as e:
        logger.error("Translation failed: %s", e)
        state.english_text = transcription
        trace.append(f"[Translate] ERROR: {e} — using original text")

    # ── Step 3: Intent extraction ─────────────────────────────────────────────
    stub_note = " [stub]" if USE_STUB_LLM else ""
    trace.append(f"[Intent{stub_note}]")
    t0 = time.time()
    state = extract_intent(state, _get_llm())
    trace.append(f"[Intent] {state.trace[-1] if state.trace else 'done'} in {time.time()-t0:.1f}s")

    intent_summary = (
        f"Intent    : {state.intent}\n"
        f"Crop      : {state.crop or '—'}\n"
        f"Stage     : {f'{state.crop_stage_days} days' if state.crop_stage_days else '—'}\n"
        f"Location  : {state.location or '—'}\n"
        f"Tools     : "
        f"{'crop ' if state.needs_crop_info else ''}"
        f"{'weather ' if state.needs_weather else ''}"
        f"{'scheme' if state.needs_scheme else ''}"
    )

    # ── Step 4: Orchestrator (tools + LLM answer) ─────────────────────────────
    stub_note = " [stub]" if USE_STUB_LLM else ""
    trace.append(f"[Orchestrator{stub_note}]")
    t0 = time.time()
    state = _get_orchestrator().run(state)
    for msg in state.trace[1:]:
        trace.append(f"  {msg}")
    trace.append(f"[Orchestrator] Done in {time.time()-t0:.1f}s")

    trace.append("[TTS] Voice output — Phase 10 (pending)")

    tools_html = _build_tools_html(state)
    trace_text = "\n".join(trace)

    return (
        detected_display,
        transcription,
        state.english_text,
        state.english_answer,
        None,              # audio output — Phase 10
        intent_summary,
        tools_html,
        trace_text,
    )


def _no_tools_html() -> str:
    return "<div style='color:#888;font-size:13px;padding:8px 0'>No tools called yet.</div>"


def _build_tools_html(state) -> str:
    """Build coloured pill badges for each tool that ran."""
    pills = []

    crop_ok = bool(state.crop_data and state.crop_data.get("context"))
    weather_ok = bool(state.weather_data and state.weather_data.get("context"))
    scheme_ok = bool(state.scheme_docs and state.scheme_docs[0].get("context"))

    def pill(icon, label, active, color):
        bg = color if active else "#e0e0e0"
        fg = "#fff" if active else "#888"
        opacity = "1" if active else "0.5"
        return (
            f"<span style='background:{bg};color:{fg};padding:5px 14px;"
            f"border-radius:20px;font-size:13px;font-weight:600;"
            f"margin-right:8px;opacity:{opacity};display:inline-block'>"
            f"{icon} {label}</span>"
        )

    pills.append(pill("🌱", "Crop Knowledge", crop_ok, "#2e7d32"))
    pills.append(pill("🌤️", "Weather", weather_ok, "#1565c0"))
    pills.append(pill("📋", "Govt Scheme", scheme_ok, "#6a1b9a"))

    status = "✅ Tools used:" if any([crop_ok, weather_ok, scheme_ok]) else "ℹ️ No tools invoked:"
    return f"<p style='margin:0 0 8px 0;font-size:13px;color:#555'>{status}</p>" + "".join(pills)


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
/* Main header */
.agri-header { text-align: center; padding: 16px 0 8px 0; }
.agri-header h1 { font-size: 2rem; margin-bottom: 4px; }
.agri-header p  { color: #555; font-size: 1rem; margin: 0; }

/* Language badge */
.lang-badge {
    background: #e8f5e9; color: #2e7d32;
    border-radius: 20px; padding: 4px 14px;
    font-weight: 700; font-size: 1rem;
    text-align: center; border: 2px solid #a5d6a7;
    min-height: 40px; line-height: 32px;
}

/* Answer box — make it stand out */
.answer-box textarea {
    font-size: 15px !important;
    line-height: 1.7 !important;
    background: #f9fbe7 !important;
    border: 2px solid #aed581 !important;
    border-radius: 10px !important;
}

/* Submit button */
.ask-btn { background: #2e7d32 !important; color: white !important;
           font-size: 16px !important; border-radius: 10px !important; }
.ask-btn:hover { background: #1b5e20 !important; }

/* Example pills */
.example-pill { font-size: 13px; }

/* Input card */
.input-card { background: #f1f8e9; border-radius: 12px; padding: 16px; }

/* Tab tweaks */
.tab-nav button { font-weight: 600; }
"""

# ── Example queries ───────────────────────────────────────────────────────────
_EXAMPLES = {
    "🇮🇳 Hindi": [
        "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?",
        "पुणे में कल बारिश होगी क्या? धान की सिंचाई करूं?",
        "PM किसान योजना के लिए कैसे आवेदन करें?",
        "मेरे टमाटर की पत्तियां पीली हो रही हैं, क्या करूं?",
    ],
    "🇮🇳 Marathi": [
        "माझ्या कापसाला 40 दिवस झाले, कोणते खत द्यावे?",
        "नाशिकमध्ये उद्या पाऊस येईल का?",
        "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?",
        "माझ्या कांद्याची पाने पिवळी पडत आहेत.",
    ],
    "🇮🇳 Punjabi": [
        "ਮੇਰੀ ਕਣਕ 40 ਦਿਨ ਦੀ ਹੈ, ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?",
        "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?",
        "ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਲਈ ਕਿਵੇਂ ਅਪਲਾਈ ਕਰਨਾ ਹੈ?",
        "ਮੇਰੇ ਝੋਨੇ ਵਿੱਚ ਕੀੜੇ ਲੱਗ ਗਏ ਹਨ।",
    ],
}


# ── UI builder ────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    mode_info = (
        f"STT: `{WHISPER_MODEL_ID}` · "
        f"Translation: {'stub' if USE_STUB_TRANSLATION else 'IndicTrans2'} · "
        f"LLM: {'stub' if USE_STUB_LLM else 'HF Inference API'}"
    )

    with gr.Blocks(title="Multilingual Agri Assistant") as demo:

        # ── Header ────────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="agri-header">
          <h1>🌾 Multilingual Agri Assistant</h1>
          <p>Ask your farming question in <strong>Hindi</strong>,
             <strong>Marathi</strong>, or <strong>Punjabi</strong> —
             get instant advice on crops, weather &amp; government schemes.</p>
        </div>
        """)

        if DEV_MODE:
            gr.Markdown(
                f"<center><small>⚙️ Dev mode &nbsp;|&nbsp; {mode_info}</small></center>",
                elem_id="dev-banner"
            )

        gr.Markdown("---")

        # ── Main layout ───────────────────────────────────────────────────────
        with gr.Row(equal_height=False):

            # ── LEFT: Input ───────────────────────────────────────────────────
            with gr.Column(scale=1, min_width=300):

                gr.Markdown("### 🎙️ Record your question")
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    label="Press record and speak",
                    show_label=False,
                )

                gr.Markdown("### 📍 Your location *(for weather)*")
                location_input = gr.Textbox(
                    placeholder="e.g. Nashik, Ludhiana, Varanasi",
                    label="Location",
                    show_label=False,
                )

                gr.Markdown("### 🌐 Detected language")
                detected_lang_output = gr.Textbox(
                    value="—",
                    label="Detected language",
                    show_label=False,
                    interactive=False,
                    elem_classes=["lang-badge"],
                )

                submit_btn = gr.Button(
                    "🌾  Ask the Assistant",
                    variant="primary",
                    size="lg",
                    elem_classes=["ask-btn"],
                )

                # Example queries
                gr.Markdown("---")
                gr.Markdown("### 💡 Example questions")
                for lang_label, examples in _EXAMPLES.items():
                    with gr.Accordion(lang_label, open=False):
                        for ex in examples:
                            gr.Markdown(f"- *{ex}*")

            # ── RIGHT: Output tabs ────────────────────────────────────────────
            with gr.Column(scale=2, min_width=400):

                with gr.Tabs():

                    # TAB 1: Answer (hero)
                    with gr.Tab("💬 Answer"):
                        tools_html_output = gr.HTML(_no_tools_html())

                        answer_output = gr.Textbox(
                            label="Farming advice",
                            lines=14,
                            interactive=False,
                            placeholder="Your answer will appear here after you record and submit a question...",
                            elem_classes=["answer-box"],
                        )

                        audio_output = gr.Audio(
                            label="🔊 Voice response (coming in Phase 10)",
                            autoplay=True,
                            visible=True,
                            interactive=False,
                        )

                    # TAB 2: Transcript
                    with gr.Tab("📝 Transcript"):
                        transcription_output = gr.Textbox(
                            label="What you said (regional language)",
                            lines=3,
                            interactive=False,
                            placeholder="Your speech transcript will appear here...",
                        )
                        english_output = gr.Textbox(
                            label="English translation (IndicTrans2)",
                            lines=3,
                            interactive=False,
                            placeholder="English translation will appear here...",
                        )

                    # TAB 3: Details
                    with gr.Tab("🔍 Details"):
                        intent_output = gr.Textbox(
                            label="Intent extraction",
                            lines=6,
                            interactive=False,
                        )
                        if DEV_MODE:
                            trace_output = gr.Textbox(
                                label="Pipeline trace",
                                lines=12,
                                interactive=False,
                            )
                        else:
                            trace_output = gr.Textbox(visible=False)

        # ── Button click wiring ───────────────────────────────────────────────
        submit_btn.click(
            fn=_run_pipeline,
            inputs=[audio_input, location_input],
            outputs=[
                detected_lang_output,
                transcription_output,
                english_output,
                answer_output,
                audio_output,
                intent_output,
                tools_html_output,
                trace_output,
            ],
        )

        # ── Footer ────────────────────────────────────────────────────────────
        gr.Markdown(
            "---\n"
            "<center><small>"
            "Built for Indian farmers · Powered by Whisper · IndicTrans2 · LLaMA 3.1 · FAISS"
            "</small></center>"
        )

    return demo
