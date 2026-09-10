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
from app.config import (
    DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION, USE_STUB_LLM,
    USE_HF_INFERENCE_API, LOCAL_LLM_MODEL_ID, TTS_ENGINE, LITE_MODE, RAG_BACKEND,
)

logger = get_logger(__name__)

_LANG_DISPLAY = {"hi": "Hindi", "mr": "Marathi", "pa": "Punjabi",
                 "en": "English", "unknown": "Unknown"}

_LANG_FLAG = {"hi": "Hindi", "mr": "Marathi", "pa": "Punjabi",
              "en": "English", "unknown": "Unrecognised"}

_LANG_PENDING = "Awaiting your question"

# ── Singletons ────────────────────────────────────────────────────────────────
_stt = None
_translator = None
_llm = None
_router_llm = None
_orchestrator = None
_tts = None


def _get_stt():
    global _stt
    if _stt is None:
        from app.models.stt import WhisperSTT
        from app.utils.device import get_device
        _stt = WhisperSTT(device=get_device())
    return _stt


def _get_translator():
    global _translator
    if _translator is None:
        from app.models.translation import get_translator
        from app.utils.device import get_device
        _translator = get_translator(device=get_device(), use_stub=USE_STUB_TRANSLATION)
    return _translator


def _get_llm():
    """Answer LLM — real (local/API) when USE_STUB_LLM is off, else the stub."""
    global _llm
    if _llm is None:
        from app.models.llm import get_llm
        # Only probe the device for a real local model — the stub needs nothing,
        # and device probing would import torch (absent on LITE_MODE hosts).
        if USE_STUB_LLM:
            _llm = get_llm(use_stub=True)
        else:
            from app.utils.device import get_device
            _llm = get_llm(device=get_device(), use_stub=False)
    return _llm


def _get_router_llm():
    """Intent router — always the fast, deterministic rule-based classifier.
    Kept separate from the answer LLM so routing stays instant and reliable on
    CPU (no slow model call just to pick which tools to run)."""
    global _router_llm
    if _router_llm is None:
        from app.models.llm import StubLLM
        _router_llm = StubLLM()
    return _router_llm


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from app.agents.orchestrator import get_orchestrator
        _orchestrator = get_orchestrator(_get_llm())
    return _orchestrator


def _get_tts():
    global _tts
    if _tts is None:
        from app.models.tts import get_tts
        # Device only matters for the parler engine; gtts/stub need nothing
        # (and probing would import torch, absent on LITE_MODE hosts).
        if TTS_ENGINE == "parler":
            from app.utils.device import get_device
            _tts = get_tts(device=get_device())
        else:
            _tts = get_tts()
    return _tts


def _run_output_stage(state, trace) -> "str | None":
    """Output boundary — translate the English answer to the farmer's language
    and synthesize voice. Returns a path to an audio file, or None."""
    answer = (state.english_answer or "").strip()
    if not answer:
        return None

    # Target voice language: the detected regional language, else English.
    target = state.source_language if state.source_language in ("hi", "mr", "pa") else "en"

    # Step 5a: English answer → regional text (skip when stubbed or already English)
    if target != "en" and not USE_STUB_TRANSLATION:
        try:
            t0 = time.time()
            state.regional_answer = _get_translator().translate_from_english(answer, target)
            trace.append(f"[Translate-out] en→{target} in {time.time()-t0:.1f}s")
            tts_lang = target
        except Exception as e:
            logger.error("Output translation failed: %s", e)
            trace.append(f"[Translate-out] ERROR: {e} — speaking English")
            state.regional_answer, tts_lang = answer, "en"
    else:
        state.regional_answer = answer
        tts_lang = "en"
        note = "stub, " if (target != "en" and USE_STUB_TRANSLATION) else ""
        trace.append(f"[Translate-out] {note}speaking English answer")

    # Step 5b: text → voice (trim long text to keep the clip reasonable)
    voice_text = state.regional_answer[:1200]
    try:
        t0 = time.time()
        audio_path = _get_tts().generate(voice_text, tts_lang)
        if audio_path:
            trace.append(f"[TTS] {TTS_ENGINE} · {tts_lang} in {time.time()-t0:.1f}s → audio ready")
        else:
            trace.append("[TTS] no audio produced — text answer still shown")
        return audio_path
    except Exception as e:
        logger.error("TTS failed: %s", e)
        trace.append(f"[TTS] ERROR: {e} — text answer still shown")
        return None


# ── Pipeline ──────────────────────────────────────────────────────────────────

def _run_pipeline(audio, text_query, location: str):
    """Full pipeline: (typed text OR STT→translate) → intent → orchestrate → answer.

    A typed English question takes priority and bypasses STT + translation — the
    reliable way to exercise the weather and government-scheme tools in dev mode,
    where Whisper-small + stub translation cannot carry spoken Indic queries
    through to the English router.
    """
    from app.agents.state import AgentState
    from app.agents.intent import extract_intent

    # Return signature:
    # detected_lang, transcription, english_text, answer, audio_out,
    # intent_box, tools_html, trace_box

    text_query = (text_query or "").strip()
    pipeline_t0 = time.time()
    trace = []
    detected_display = _LANG_PENDING

    if text_query:
        # ── Typed input — skip STT + translation ──────────────────────────────
        detected_display = "English (typed)"
        transcription = text_query
        state = AgentState(
            source_language="en",
            original_text=text_query,
            english_text=text_query,
            location=location.strip() or None,
        )
        trace.append(f"[Input] Typed query: '{text_query}'")
        trace.append("[STT] skipped — typed input")
        trace.append("[Translate] skipped — already English")
    elif audio is None:
        msg = "Type a question above, or tap the microphone and speak."
        return _LANG_PENDING, "", "", msg, None, "", _no_tools_html(), ""
    else:
        # ── Step 1: Whisper STT ───────────────────────────────────────────────
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
            return (_LANG_PENDING, "", "",
                    f"Speech recognition failed: {e}", None, "",
                    _no_tools_html(), "")

        state = AgentState(
            source_language=iso_lang,
            original_text=transcription,
            location=location.strip() or None,
        )

        # ── Step 2: Translate regional → English ─────────────────────────────
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
    trace.append("[Intent] rule-based router")
    t0 = time.time()
    state = extract_intent(state, _get_router_llm())
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

    # ── Step 5: Output boundary — translate answer + synthesize voice ─────────
    stub_note = " [stub]" if USE_STUB_TRANSLATION else ""
    trace.append(f"[Output{stub_note}] translate + TTS ({TTS_ENGINE})")
    audio_path = _run_output_stage(state, trace)

    total = time.time() - pipeline_t0
    state.latency["total"] = round(total, 2)
    trace.append(f"[Total] response time: {total:.1f}s")

    tools_html = _build_tools_html(state)
    trace_text = "\n".join(trace)

    return (
        detected_display,
        transcription,
        state.english_text,
        state.english_answer,
        audio_path,        # voice output (Phase 10)
        intent_summary,
        tools_html,
        trace_text,
    )

# ══════════════════════════════════════════════════════════════════════════════
# Presentation layer
#
# Design language: dark-first editorial. A near-black canvas, hairline rules
# instead of boxes, thin letterspaced eyebrow labels, one restrained accent
# (wheat gold), and large tight display type. A full light palette ships
# alongside it — Gradio puts `dark` on <body> and follows the viewer's system
# setting, so every colour below is a token defined for both. Append
# `?__theme=dark` (or `light`) to the URL to pin one.
#
# Rule: never hardcode a colour in generated HTML — only token-backed classes,
# or it inverts badly in the other theme.
# ══════════════════════════════════════════════════════════════════════════════

_TOOL_SPECS = (
    ("crop", "Crop knowledge"),
    ("weather", "Weather"),
    ("scheme", "Govt scheme"),
)


def _eyebrow(text: str, num: str = "") -> str:
    """A thin letterspaced section marker with a hairline running off to the right."""
    index = f'<span class="ag-eyebrow-num">{num}</span>' if num else ""
    return (
        f'<div class="ag-eyebrow">{index}'
        f'<span class="ag-eyebrow-text">{text}</span>'
        f'<span class="ag-eyebrow-rule"></span></div>'
    )


def _tool_chip(label: str, active: bool) -> str:
    state = "on" if active else "off"
    note = "used" if active else "idle"
    return (
        f'<span class="ag-chip ag-chip--{state}">'
        f'<i class="ag-chip-dot"></i>'
        f'<span class="ag-chip-label">{label}</span>'
        f'<span class="ag-chip-note">{note}</span></span>'
    )


def _tools_strip(crop_ok: bool = False, weather_ok: bool = False,
                 scheme_ok: bool = False, idle: bool = False) -> str:
    flags = {"crop": crop_ok, "weather": weather_ok, "scheme": scheme_ok}
    chips = "".join(_tool_chip(label, flags[key]) for key, label in _TOOL_SPECS)
    if idle:
        caption = "Standing by"
    elif any(flags.values()):
        caption = f"{sum(flags.values())} of 3 sources consulted"
    else:
        caption = "Answered without external sources"
    return (
        f'<div class="ag-tools">'
        f'<div class="ag-tools-caption">{caption}</div>'
        f'<div class="ag-tools-row">{chips}</div>'
        f'</div>'
    )


def _no_tools_html() -> str:
    return _tools_strip(idle=True)


def _build_tools_html(state) -> str:
    """Status strip showing which knowledge sources the orchestrator actually hit."""
    return _tools_strip(
        crop_ok=bool(state.crop_data and state.crop_data.get("context")),
        weather_ok=bool(state.weather_data and state.weather_data.get("context")),
        scheme_ok=bool(state.scheme_docs and state.scheme_docs[0].get("context")),
    )


# ── Theme ─────────────────────────────────────────────────────────────────────

def build_theme():
    """Drive Gradio's own components from the palette.

    Gradio exposes a `*_dark` twin for every colour variable, so setting both
    here keeps the native widgets in step with the custom CSS in either theme —
    far more robust than overriding Gradio's internals from CSS alone.
    """
    return gr.themes.Base(
        font=[gr.themes.GoogleFont("Inter"), "system-ui", "-apple-system",
              "Segoe UI", "sans-serif"],
        font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace",
                   "Consolas", "monospace"],
        radius_size=gr.themes.sizes.radius_sm,
        text_size=gr.themes.sizes.text_md,
    ).set(
        # Canvas
        body_background_fill="#F6F5F1",
        body_background_fill_dark="#08090A",
        body_text_color="#15171A",
        body_text_color_dark="#EDEFF0",
        body_text_color_subdued="#5C6166",
        body_text_color_subdued_dark="#9AA1A6",
        background_fill_primary="#FFFFFF",
        background_fill_primary_dark="#0F1113",
        background_fill_secondary="#F0EEE8",
        background_fill_secondary_dark="#141719",
        # Blocks — flat, hairline-bordered, no shadows
        block_background_fill="transparent",
        block_background_fill_dark="transparent",
        block_border_width="0px",
        block_border_color="transparent",
        block_border_color_dark="transparent",
        block_shadow="none",
        block_shadow_dark="none",
        block_label_background_fill="transparent",
        block_label_background_fill_dark="transparent",
        block_label_border_width="0px",
        block_label_text_color="#8A9096",
        block_label_text_color_dark="#646C72",
        block_label_text_size="11px",
        block_label_text_weight="600",
        block_title_text_color="#8A9096",
        block_title_text_color_dark="#646C72",
        block_title_text_weight="600",
        block_info_text_color="#8A9096",
        block_info_text_color_dark="#646C72",
        panel_background_fill="transparent",
        panel_background_fill_dark="transparent",
        panel_border_width="0px",
        # Inputs
        input_background_fill="#FFFFFF",
        input_background_fill_dark="#141719",
        input_background_fill_focus="#FFFFFF",
        input_background_fill_focus_dark="#171B1E",
        input_border_color="#DCD9D0",
        input_border_color_dark="#262B2F",
        input_border_color_focus="#8A6410",
        input_border_color_focus_dark="#D9A441",
        input_border_width="1px",
        input_placeholder_color="#A8AEB3",
        input_placeholder_color_dark="#5A6167",
        input_shadow="none",
        input_shadow_focus="none",
        input_shadow_focus_dark="none",
        # Buttons
        button_primary_background_fill="#15171A",
        button_primary_background_fill_dark="#D9A441",
        button_primary_background_fill_hover="#000000",
        button_primary_background_fill_hover_dark="#E8B65C",
        button_primary_text_color="#FFFFFF",
        button_primary_text_color_dark="#08090A",
        button_primary_border_color="#15171A",
        button_primary_border_color_dark="#D9A441",
        button_secondary_background_fill="transparent",
        button_secondary_background_fill_dark="transparent",
        button_secondary_background_fill_hover="#EDEBE4",
        button_secondary_background_fill_hover_dark="#1A1E21",
        button_secondary_text_color="#15171A",
        button_secondary_text_color_dark="#EDEFF0",
        button_secondary_border_color="#DCD9D0",
        button_secondary_border_color_dark="#262B2F",
        button_border_width="1px",
        button_large_radius="2px",
        button_small_radius="2px",
        # Accents and misc
        color_accent="#8A6410",
        border_color_primary="#E2E0D9",
        border_color_primary_dark="#22262A",
        border_color_accent="#8A6410",
        border_color_accent_dark="#D9A441",
        link_text_color="#8A6410",
        link_text_color_dark="#D9A441",
        link_text_color_hover="#15171A",
        link_text_color_hover_dark="#E8B65C",
        loader_color="#8A6410",
        loader_color_dark="#D9A441",
        slider_color="#8A6410",
        slider_color_dark="#D9A441",
        code_background_fill="#F0EEE8",
        code_background_fill_dark="#141719",
    )


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
/* ═══ Tokens — Gradio puts `dark` on <body>, so both palettes hang off it ═══ */
body {
  --ag-bg:        #F6F5F1;
  --ag-surface:   #FFFFFF;
  --ag-sunk:      #EFEDE6;
  --ag-line:      #E2E0D9;
  --ag-line-2:    #CFCCC2;
  --ag-text:      #15171A;
  --ag-dim:       #5C6166;
  --ag-faint:     #8A9096;
  --ag-accent:    #8A6410;
  --ag-accent-bg: rgba(138,100,16,.09);
  --ag-shade:     rgba(0,0,0,.035);
}
body.dark {
  --ag-bg:        #08090A;
  --ag-surface:   #0F1113;
  --ag-sunk:      #131619;
  --ag-line:      #22262A;
  --ag-line-2:    #2E3439;
  --ag-text:      #EDEFF0;
  --ag-dim:       #9AA1A6;
  --ag-faint:     #646C72;
  --ag-accent:    #D9A441;
  --ag-accent-bg: rgba(217,164,65,.11);
  --ag-shade:     rgba(255,255,255,.02);
}

/* ═══ Shell ═══ */
/* Gradio's page template paints <body> off prefers-color-scheme alone, which
   leaves a mismatched band below the app when the viewer pins a theme by hand
   (?__theme=…) against their OS setting. Repaint it from our own tokens. */
body { background: var(--ag-bg) !important; color: var(--ag-text); }

.gradio-container {
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding: 0 28px 72px !important;
  background: var(--ag-bg);
  color: var(--ag-text);
}
.gradio-container .prose :is(h1,h2,h3,h4) { color: var(--ag-text); }
footer { display: none !important; }

/* ═══ Top bar ═══ */
.ag-topbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 20px; flex-wrap: wrap;
  padding: 22px 0 20px;
  border-bottom: 1px solid var(--ag-line);
}
.ag-brand { display: flex; align-items: center; gap: 11px; }
.ag-brand-mark {
  width: 9px; height: 9px; flex: none;
  background: var(--ag-accent);
  transform: rotate(45deg);
}
.ag-brand-name {
  font-size: 12px; font-weight: 600;
  letter-spacing: .19em; text-transform: uppercase;
  color: var(--ag-text);
}
.ag-langs {
  display: flex; align-items: center; gap: 10px;
  font-size: 11px; letter-spacing: .16em; text-transform: uppercase;
  color: var(--ag-faint);
}
.ag-langs span:not(:last-child)::after {
  content: "·"; margin-left: 10px; color: var(--ag-line-2);
}

/* ═══ Hero ═══ */
.ag-hero { padding: 68px 0 60px; max-width: 720px; }
.ag-hero-eyebrow {
  font-size: 11px; font-weight: 600;
  letter-spacing: .21em; text-transform: uppercase;
  color: var(--ag-accent);
  margin-bottom: 24px;
}
.ag-hero h1 {
  font-size: clamp(2.5rem, 6vw, 4.15rem);
  line-height: 1.02;
  letter-spacing: -.035em;
  font-weight: 600;
  margin: 0 0 26px;
  color: var(--ag-text);
}
.ag-hero h1 em { font-style: normal; color: var(--ag-accent); }
.ag-hero p {
  font-size: 1.0625rem;
  line-height: 1.65;
  color: var(--ag-dim);
  margin: 0;
  max-width: 46ch;
}
.ag-mode {
  display: inline-block;
  margin-top: 30px;
  padding: 6px 12px;
  border: 1px solid var(--ag-line);
  border-radius: 2px;
  background: var(--ag-shade);
  font-size: 11px;
  letter-spacing: .04em;
  color: var(--ag-faint);
  font-family: var(--font-mono);
  word-break: break-word;
}

/* ═══ Eyebrow section markers ═══ */
.ag-eyebrow {
  display: flex; align-items: center; gap: 12px;
  margin: 0 0 18px;
}
.ag-eyebrow-num {
  font-size: 10px; font-weight: 600;
  letter-spacing: .1em;
  color: var(--ag-accent);
  font-family: var(--font-mono);
}
.ag-eyebrow-text {
  font-size: 11px; font-weight: 600;
  letter-spacing: .19em; text-transform: uppercase;
  color: var(--ag-dim);
  white-space: nowrap;
}
.ag-eyebrow-rule { flex: 1; height: 1px; background: var(--ag-line); }

/* ═══ Console panels ═══ */
.ag-console { gap: 0 !important; align-items: stretch !important; }
.ag-panel { padding: 34px 0 40px !important; min-width: 0 !important; }
.ag-panel--ask { padding-right: 40px !important; }
.ag-panel--answer {
  padding-left: 40px !important;
  border-left: 1px solid var(--ag-line);
}
@media (max-width: 860px) {
  .ag-console { flex-direction: column !important; flex-wrap: nowrap !important; }
  .ag-console > .ag-panel {
    width: 100% !important;
    flex: 1 1 auto !important;
    min-width: 0 !important;
  }
  .ag-panel { padding: 26px 0 30px !important; }
  .ag-panel--ask { padding-right: 0 !important; }
  .ag-panel--answer {
    padding-left: 0 !important;
    border-left: none;
    border-top: 1px solid var(--ag-line);
  }
  .gradio-container { padding: 0 18px 56px !important; }
  .ag-hero { padding: 44px 0 40px; }
  .ag-detected input, .ag-detected textarea { font-size: 16px !important; }
}

/* Tighten Gradio's default block chrome inside the panels */
.ag-panel .block { padding: 0 !important; }
.ag-panel .gap { gap: 14px !important; }
.ag-panel label > span { letter-spacing: .1em; text-transform: uppercase; }

/* ═══ Inputs ═══ */
.ag-panel textarea, .ag-panel input[type="text"] {
  font-size: 15px !important;
  line-height: 1.6 !important;
  padding: 13px 14px !important;
  border-radius: 2px !important;
  transition: border-color .16s ease;
}
.ag-field-note {
  font-size: 12px; line-height: 1.6;
  color: var(--ag-faint);
  margin: -4px 0 14px;
}
.ag-mic { border: 1px solid var(--ag-line) !important; border-radius: 2px !important; }

/* ═══ Ask button ═══ */
.ag-ask button, button.ag-ask {
  width: 100%;
  border-radius: 2px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  letter-spacing: .15em !important;
  text-transform: uppercase;
  padding: 17px 20px !important;
  transition: transform .12s ease, background .16s ease;
}
.ag-ask button:active { transform: translateY(1px); }

/* ═══ Detected-language readout ═══ */
/* Gradio wraps the field in label.container.show_textbox_border, and that
   wrapper — not the input — draws the box. Strip every layer back to a rule. */
.ag-detected { min-width: 0 !important; }
.ag-detected,
.ag-detected label,
.ag-detected .input-container {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
}
.ag-detected { margin-top: -4px !important; }
.ag-detected input, .ag-detected textarea {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
  font-size: 18px !important;
  letter-spacing: -.01em !important;
  font-weight: 600 !important;
  color: var(--ag-accent) !important;
  resize: none !important;
  cursor: default;
  text-overflow: ellipsis;
}

/* ═══ Tool status strip ═══ */
.ag-tools { margin: 0 0 26px; }
.ag-tools-caption {
  font-size: 11px; letter-spacing: .15em; text-transform: uppercase;
  color: var(--ag-faint);
  margin-bottom: 12px;
}
.ag-tools-row { display: flex; flex-wrap: wrap; gap: 8px; }
.ag-chip {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 8px 13px;
  border: 1px solid var(--ag-line);
  border-radius: 2px;
  font-size: 12px;
  line-height: 1;
  transition: border-color .2s ease, background .2s ease;
}
.ag-chip-dot {
  width: 6px; height: 6px; flex: none;
  border-radius: 50%;
  background: var(--ag-line-2);
}
.ag-chip-label { color: var(--ag-faint); font-weight: 500; }
.ag-chip-note {
  font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ag-line-2);
}
.ag-chip--on { border-color: var(--ag-accent); background: var(--ag-accent-bg); }
.ag-chip--on .ag-chip-dot   { background: var(--ag-accent); }
.ag-chip--on .ag-chip-label { color: var(--ag-text); font-weight: 600; }
.ag-chip--on .ag-chip-note  { color: var(--ag-accent); }

/* ═══ Answer ═══ */
.ag-answer textarea {
  font-size: 16px !important;
  line-height: 1.78 !important;
  background: var(--ag-surface) !important;
  border: 1px solid var(--ag-line) !important;
  border-left: 2px solid var(--ag-accent) !important;
  border-radius: 2px !important;
  padding: 24px 26px !important;
  color: var(--ag-text) !important;
}
.ag-audio { margin-top: 18px !important; }

/* ═══ Example prompts ═══ */
.ag-examples { margin-top: 8px; }
.ag-examples .gap { gap: 8px !important; }
.ag-examples .gap, .ag-examples .form { gap: 0 !important; }
button.ag-example {
  justify-content: flex-start !important;
  text-align: left !important;
  font-size: 13.5px !important;
  font-weight: 400 !important;
  line-height: 1.55 !important;
  padding: 13px 0 13px 18px !important;
  border: none !important;
  border-bottom: 1px solid var(--ag-line) !important;
  border-radius: 0 !important;
  background: transparent !important;
  color: var(--ag-dim) !important;
  white-space: normal !important;
  height: auto !important;
  position: relative;
  transition: color .16s ease, padding-left .16s ease;
}
button.ag-example::before {
  content: ""; position: absolute; left: 0; top: 1.42em;
  width: 6px; height: 1px; background: var(--ag-line-2);
  transition: background .16s ease, width .16s ease;
}
button.ag-example:hover {
  color: var(--ag-text) !important;
  padding-left: 24px !important;
  background: transparent !important;
}
button.ag-example:hover::before { background: var(--ag-accent); width: 12px; }

/* Spoken-phrase reference list */
.ag-phrases { margin-top: 0; }
.ag-panel--answer .ag-eyebrow { margin-top: 34px; }
.ag-panel--answer .ag-eyebrow:first-child { margin-top: 0; }
.ag-panel--ask .ag-examples { margin-top: 0; }
.ag-phrase-group { border-top: 1px solid var(--ag-line); padding: 16px 0; }
.ag-phrase-group:first-child { border-top: none; padding-top: 0; }
.ag-phrase-lang {
  font-size: 10px; font-weight: 600;
  letter-spacing: .19em; text-transform: uppercase;
  color: var(--ag-faint);
  margin-bottom: 10px;
}
.ag-phrase {
  font-size: 14px; line-height: 1.75;
  color: var(--ag-dim);
  padding-left: 16px;
  position: relative;
}
.ag-phrase::before {
  content: ""; position: absolute; left: 0; top: .72em;
  width: 5px; height: 1px; background: var(--ag-accent);
}

/* ═══ Diagnostics accordion ═══ */
.ag-diag { margin-top: 8px !important; border-top: 1px solid var(--ag-line) !important; }
.ag-diag .label-wrap {
  padding: 22px 0 !important;
  font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: .19em !important; text-transform: uppercase;
  color: var(--ag-faint) !important;
}
.ag-diag .label-wrap:hover { color: var(--ag-text) !important; }
.ag-diag textarea {
  font-family: var(--font-mono) !important;
  font-size: 12px !important;
  line-height: 1.65 !important;
  background: var(--ag-sunk) !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 2px !important;
  color: var(--ag-dim) !important;
}

/* ═══ Footer ═══ */
.ag-footer {
  margin-top: 40px; padding-top: 24px;
  border-top: 1px solid var(--ag-line);
  display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
  font-size: 11px; letter-spacing: .13em; text-transform: uppercase;
  color: var(--ag-faint);
}
"""

# ── Example prompts ───────────────────────────────────────────────────────────
# Typed input is treated as English by the pipeline, so only the English set is
# clickable. The regional phrases below are a spoken-input reference — filling
# one into the text box would have it mislabelled as English and skip translation.
_TYPED_EXAMPLES = [
    "My wheat is 40 days old, which fertiliser should I apply?",
    "Will it rain in Nashik tomorrow? Should I irrigate my paddy?",
    "How do I apply for the PM-Kisan scheme?",
    "The leaves on my tomato plants are turning yellow.",
]

_EXAMPLES = {
    "Hindi": [
        "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?",
        "पुणे में कल बारिश होगी क्या? धान की सिंचाई करूं?",
        "PM किसान योजना के लिए कैसे आवेदन करें?",
        "मेरे टमाटर की पत्तियां पीली हो रही हैं, क्या करूं?",
    ],
    "Marathi": [
        "माझ्या कापसाला 40 दिवस झाले, कोणते खत द्यावे?",
        "नाशिकमध्ये उद्या पाऊस येईल का?",
        "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?",
        "माझ्या कांद्याची पाने पिवळी पडत आहेत.",
    ],
    "Punjabi": [
        "ਮੇਰੀ ਕਣਕ 40 ਦਿਨ ਦੀ ਹੈ, ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?",
        "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?",
        "ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਲਈ ਕਿਵੇਂ ਅਪਲਾਈ ਕਰਨਾ ਹੈ?",
        "ਮੇਰੇ ਝੋਨੇ ਵਿੱਚ ਕੀੜੇ ਲੱਗ ਗਏ ਹਨ।",
    ],
}


def _phrases_html() -> str:
    groups = []
    for lang, phrases in _EXAMPLES.items():
        lines = "".join(f'<div class="ag-phrase">{p}</div>' for p in phrases)
        groups.append(
            f'<div class="ag-phrase-group">'
            f'<div class="ag-phrase-lang">{lang}</div>{lines}</div>'
        )
    return f'<div class="ag-phrases">{"".join(groups)}</div>'


# ── UI builder ────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    if USE_STUB_LLM:
        llm_mode = "rule-based"
    elif USE_HF_INFERENCE_API:
        llm_mode = "HF Inference API"
    else:
        llm_mode = f"local ({LOCAL_LLM_MODEL_ID})"

    if LITE_MODE:
        mode_info = "lite · typed input · keyword scheme search · rule-based answers · gTTS"
    else:
        mode_info = (
            f"stt {WHISPER_MODEL_ID} · "
            f"mt {'stub' if USE_STUB_TRANSLATION else 'indictrans2'} · "
            f"llm {llm_mode} · rag {RAG_BACKEND} · tts {TTS_ENGINE}"
        )

    with gr.Blocks(title="Agri Assistant", fill_width=True) as demo:

        # ── Top bar ───────────────────────────────────────────────────────────
        gr.HTML(
            '<div class="ag-topbar">'
            '  <div class="ag-brand">'
            '    <span class="ag-brand-mark"></span>'
            '    <span class="ag-brand-name">Agri Assistant</span>'
            '  </div>'
            '  <div class="ag-langs">'
            '    <span>Hindi</span><span>Marathi</span>'
            '    <span>Punjabi</span><span>English</span>'
            '  </div>'
            '</div>'
        )

        # ── Hero ──────────────────────────────────────────────────────────────
        speak_or_type = "Type" if LITE_MODE else "Speak"
        gr.HTML(
            '<div class="ag-hero">'
            '  <div class="ag-hero-eyebrow">For Indian farmers</div>'
            '  <h1>Ask in your<br><em>own language.</em></h1>'
            f'  <p>{speak_or_type} a question about your crop, the weather over your '
            '     field, or a government scheme — and get the answer back in the '
            '     language you asked it in.</p>'
            f'  <div class="ag-mode">{mode_info}</div>'
            '</div>'
        )

        # ── Console ───────────────────────────────────────────────────────────
        with gr.Row(equal_height=False, elem_classes=["ag-console"]):

            # ── LEFT: the ask ────────────────────────────────────────────────
            with gr.Column(scale=5, min_width=300,
                           elem_classes=["ag-panel", "ag-panel--ask"]):

                if LITE_MODE:
                    # Voice input needs Whisper (torch) — off on small free hosts.
                    audio_input = gr.Audio(visible=False)
                    gr.HTML(_eyebrow("Your question", "01"))
                    gr.HTML(
                        '<div class="ag-field-note">Voice input runs in the full '
                        'version. This lightweight demo takes typed questions in '
                        'English.</div>'
                    )
                    location_step = "02"
                else:
                    gr.HTML(_eyebrow("Speak", "01"))
                    audio_input = gr.Audio(
                        sources=["microphone"],
                        type="filepath",
                        show_label=False,
                        elem_classes=["ag-mic"],
                    )
                    gr.HTML(_eyebrow("Or type", "02"))
                    location_step = "03"

                text_input = gr.Textbox(
                    placeholder="Will it rain in Pune tomorrow? Any scheme for irrigation?",
                    show_label=False,
                    lines=3,
                )

                gr.HTML(_eyebrow("Location", location_step))
                gr.HTML(
                    '<div class="ag-field-note">Used to pull the live forecast over '
                    'your field.</div>'
                )
                location_input = gr.Textbox(
                    placeholder="Nashik · Ludhiana · Varanasi",
                    show_label=False,
                )

                submit_btn = gr.Button(
                    "Ask the assistant",
                    variant="primary",
                    size="lg",
                    elem_classes=["ag-ask"],
                )

                gr.HTML(_eyebrow("Detected language"))
                detected_lang_output = gr.Textbox(
                    value=_LANG_PENDING,
                    show_label=False,
                    container=False,
                    interactive=False,
                    lines=1,
                    max_lines=1,
                    elem_classes=["ag-detected"],
                )

                gr.HTML(_eyebrow("Try one"))
                with gr.Column(elem_classes=["ag-examples"]):
                    for example in _TYPED_EXAMPLES:
                        gr.Button(
                            example, size="sm", elem_classes=["ag-example"]
                        ).click(fn=lambda e=example: e, inputs=None,
                                outputs=text_input)

            # ── RIGHT: the answer ────────────────────────────────────────────
            with gr.Column(scale=7, min_width=340,
                           elem_classes=["ag-panel", "ag-panel--answer"]):

                gr.HTML(_eyebrow("Response"))

                tools_html_output = gr.HTML(_no_tools_html())

                answer_output = gr.Textbox(
                    show_label=False,
                    lines=10,
                    max_lines=26,
                    interactive=False,
                    placeholder="Your advice will appear here.",
                    elem_classes=["ag-answer"],
                )

                audio_output = gr.Audio(
                    label="Spoken reply",
                    autoplay=True,
                    interactive=False,
                    elem_classes=["ag-audio"],
                )

                gr.HTML(_eyebrow("Or say it aloud"))
                gr.HTML(_phrases_html())

        # ── Diagnostics ───────────────────────────────────────────────────────
        with gr.Accordion("Transcript & pipeline", open=False,
                          elem_classes=["ag-diag"]):
            with gr.Row():
                transcription_output = gr.Textbox(
                    label="Heard",
                    lines=3,
                    interactive=False,
                    placeholder="Your words, as transcribed.",
                )
                english_output = gr.Textbox(
                    label="English translation",
                    lines=3,
                    interactive=False,
                    placeholder="The English the agent reasoned over.",
                )
            intent_output = gr.Textbox(label="Intent", lines=6, interactive=False)
            if DEV_MODE:
                trace_output = gr.Textbox(label="Trace", lines=14, interactive=False)
            else:
                trace_output = gr.Textbox(visible=False)

        # ── Wiring ────────────────────────────────────────────────────────────
        submit_btn.click(
            fn=_run_pipeline,
            inputs=[audio_input, text_input, location_input],
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
        gr.HTML(
            '<div class="ag-footer">'
            '  <span>Built for Indian farmers</span>'
            '  <span>Whisper · IndicTrans2 · FAISS</span>'
            '</div>'
        )

    return demo
