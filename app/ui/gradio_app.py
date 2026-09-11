"""Gradio UI — farmer-facing console, in English, Hindi, Punjabi and Marathi.

Flow: typed or spoken question → intent extraction → agent (LangChain ReAct by
default: crop / weather / scheme tools) → answer → spoken reply.

The language picked in the top bar drives the whole interface (app/ui/i18n.py)
and the language the microphone listens in. Answers are English unless a real
translator (IndicTrans2) is configured — see _pipeline().
"""
import time
import gradio as gr

from app.utils.logging import get_logger
from app.config import (
    DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION, USE_STUB_LLM,
    USE_HF_INFERENCE_API, LOCAL_LLM_MODEL_ID, TTS_ENGINE, LITE_MODE, RAG_BACKEND,
    AGENT_BACKEND,
)
from app.ui.i18n import (
    DEFAULT_LANG, LANG_CHOICES, SPOKEN_EXAMPLES, lang_name, normalize_lang, t,
)

logger = get_logger(__name__)

# A real English↔regional text translator (IndicTrans2) is configured. Without
# it, spoken regional questions reach the agent via Whisper's speech→English
# translation plus the original transcript, and answers stay in English.
_MT_READY = not USE_STUB_TRANSLATION


def _has_indic(text: str) -> bool:
    """True if text contains Devanagari (U+0900–097F) or Gurmukhi (U+0A00–0A7F)."""
    return any(0x0900 <= ord(ch) <= 0x0A7F for ch in text)

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
    """Agent engine: the LangChain ReAct agent by default, or the deterministic
    sequential orchestrator (AGENT_BACKEND=sequential, or if LangChain is absent)."""
    global _orchestrator
    if _orchestrator is None:
        if AGENT_BACKEND == "langchain":
            try:
                from app.agents.langchain_agent import get_langchain_agent
                _orchestrator = get_langchain_agent(_get_llm())
                return _orchestrator
            except ImportError as exc:
                logger.warning("LangChain unavailable (%s) — using sequential orchestrator.", exc)
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


def _run_output_stage(state, trace, target_lang: "str | None" = None) -> "str | None":
    """Output boundary — translate the English answer to the farmer's language
    and synthesize voice. Returns a path to an audio file, or None.

    target_lang: the language to answer in (the one chosen on the page). When
    omitted, the language the question was asked in is used."""
    answer = (state.english_answer or "").strip()
    if not answer:
        return None

    if target_lang is None:
        target_lang = state.source_language
    target = target_lang if target_lang in ("hi", "mr", "pa") else "en"

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

def _pipeline(audio, text_query, location, lang) -> dict:
    """Full pipeline: (typed text OR voice) → intent → agent → answer → voice.

    `lang` is the language chosen on the page. It controls every message the
    farmer sees and the language the microphone listens for:
      • Typed questions are English. Typed Hindi/Punjabi/Marathi is translated
        only when a real translator (IndicTrans2) is configured; otherwise the
        farmer gets a message, in their language, asking for English.
      • Spoken questions are transcribed in the chosen language. Without
        IndicTrans2, Whisper's own speech→English translation plus the
        original transcript carry them to the agent (see routing_text()).
      • The answer is given in the chosen language when IndicTrans2 is
        configured, otherwise in English.
    """
    from app.agents.state import AgentState
    from app.agents.intent import extract_intent

    lang = normalize_lang(lang)
    text_query = (text_query or "").strip()
    location = (location or "").strip() or None
    pipeline_t0 = time.time()
    trace = [f"[UI] language: {lang}"]

    def prompt_only(message: str) -> dict:
        """Result for a request that never reached the agent."""
        return {"detected": t("pending", lang), "transcription": "", "english": "",
                "answer": message, "audio": None, "intent": "",
                "tools_html": _no_tools_html(lang), "trace": "",
                "detected_key": None, "tools_flags": None}

    if text_query:
        # ── Typed input ───────────────────────────────────────────────────────
        mode, q_lang, english = "typed", "en", text_query
        if _has_indic(text_query):
            if not _MT_READY:
                key = "err_type_english_lite" if LITE_MODE else "err_type_english"
                return prompt_only(t(key, lang))
            gurmukhi = any(0x0A00 <= ord(ch) <= 0x0A7F for ch in text_query)
            q_lang = "pa" if gurmukhi else (lang if lang in ("hi", "mr") else "hi")
            try:
                english = _get_translator().translate_to_english(text_query, q_lang)
                trace.append(f"[Translate] {q_lang}→en: '{english}'")
            except Exception as e:
                logger.error("Translation failed: %s", e)
                trace.append(f"[Translate] ERROR: {e} — using original text")
        transcription = text_query
        state = AgentState(source_language=q_lang, original_text=text_query,
                           english_text=english, location=location)
        trace.append(f"[Input] typed: '{text_query}'")
    elif audio is None:
        key = "err_no_input_lite" if LITE_MODE else "err_no_input"
        return prompt_only(t(key, lang))
    else:
        # ── Voice input — Whisper listens in the chosen language ─────────────
        mode, q_lang = "voice", lang
        whisper_mt = lang != "en" and not _MT_READY
        trace.append(f"[STT] {WHISPER_MODEL_ID} · language={lang}"
                     f"{' · speech→English' if whisper_mt else ''}")
        try:
            t0 = time.time()
            result = _get_stt().transcribe(audio, language=lang, translate=whisper_mt)
        except Exception as e:
            logger.error("STT failed: %s", e)
            return prompt_only(t("err_stt", lang, err=e))
        transcription = result["text"]
        trace.append(f"[STT] {time.time()-t0:.1f}s: '{transcription}'")
        state = AgentState(source_language=lang, original_text=transcription,
                           location=location)
        if lang == "en":
            state.english_text = transcription
        elif whisper_mt:
            state.english_text = result.get("english_text") or transcription
            trace.append(f"[Translate] Whisper speech→English: '{state.english_text}'")
        else:
            try:
                t0 = time.time()
                state.english_text = _get_translator().translate_to_english(transcription, lang)
                trace.append(f"[Translate] {lang}→en in {time.time()-t0:.1f}s: "
                             f"'{state.english_text}'")
            except Exception as e:
                logger.error("Translation failed: %s", e)
                state.english_text = transcription
                trace.append(f"[Translate] ERROR: {e} — using original text")

    # ── Intent extraction (entities + tool hints) ─────────────────────────────
    t0 = time.time()
    state = extract_intent(state, _get_router_llm())
    trace.append(f"[Intent] {state.trace[-1] if state.trace else 'done'} "
                 f"in {time.time()-t0:.1f}s")

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

    # ── Agent: tools + answer ─────────────────────────────────────────────────
    trace.append(f"[Agent] {AGENT_BACKEND}{' · rule-based LLM' if USE_STUB_LLM else ''}")
    t0 = time.time()
    state = _get_orchestrator().run(state)
    for msg in state.trace[1:]:
        trace.append(f"  {msg}")
    trace.append(f"[Agent] done in {time.time()-t0:.1f}s")

    # ── Output: answer language + voice ───────────────────────────────────────
    target = lang if (lang != "en" and _MT_READY) else "en"
    trace.append(f"[Output] answer language: {target} · TTS {TTS_ENGINE}")
    audio_path = _run_output_stage(state, trace, target_lang=target)
    translated = (target != "en" and state.regional_answer
                  and state.regional_answer != state.english_answer)
    answer = state.regional_answer if translated else state.english_answer

    total = time.time() - pipeline_t0
    state.latency["total"] = round(total, 2)
    trace.append(f"[Total] response time: {total:.1f}s")

    flags = _tool_flags(state)
    detected_key = (q_lang, mode)
    return {"detected": _detected_text(lang, detected_key), "transcription": transcription,
            "english": state.english_text, "answer": answer, "audio": audio_path,
            "intent": intent_summary, "tools_html": _tools_strip(lang, flags),
            "trace": "\n".join(trace), "detected_key": detected_key, "tools_flags": flags}


def _run_pipeline(audio, text_query, location, lang_code=DEFAULT_LANG):
    """Pipeline result as an 8-tuple: detected language, transcript, English
    text, answer, audio path, intent summary, tool-status HTML, trace."""
    r = _pipeline(audio, text_query, location, lang_code)
    return (r["detected"], r["transcription"], r["english"], r["answer"], r["audio"],
            r["intent"], r["tools_html"], r["trace"])


def _on_ask(audio, text_query, location, lang_code):
    """Ask-button handler: the pipeline result plus the two states the page keeps
    so it can re-render the language readout and tool chips on a language switch."""
    r = _pipeline(audio, text_query, location, lang_code)
    return (r["detected"], r["transcription"], r["english"], r["answer"], r["audio"],
            r["intent"], r["tools_html"], r["trace"], r["detected_key"], r["tools_flags"])


def _detected_text(ui_lang: str, detected_key) -> str:
    """'Hindi · voice', written in the UI language — or the waiting message."""
    if not detected_key:
        return t("pending", ui_lang)
    q_lang, mode = detected_key
    return f"{lang_name(q_lang, ui_lang)} · {t('mode_' + mode, ui_lang)}"


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
    ("crop", "tool_crop"),
    ("weather", "tool_weather"),
    ("scheme", "tool_scheme"),
)


def _eyebrow(text: str, num: str = "") -> str:
    """A thin letterspaced section marker with a hairline running off to the right."""
    index = f'<span class="ag-eyebrow-num">{num}</span>' if num else ""
    return (
        f'<div class="ag-eyebrow">{index}'
        f'<span class="ag-eyebrow-text">{text}</span>'
        f'<span class="ag-eyebrow-rule"></span></div>'
    )


def _note(text: str) -> str:
    return f'<div class="ag-field-note">{text}</div>'


def _tool_chip(label: str, active: bool, lang: str) -> str:
    state = "on" if active else "off"
    note = t("chip_used" if active else "chip_idle", lang)
    return (
        f'<span class="ag-chip ag-chip--{state}">'
        f'<i class="ag-chip-dot"></i>'
        f'<span class="ag-chip-label">{label}</span>'
        f'<span class="ag-chip-note">{note}</span></span>'
    )


def _tools_strip(lang: str = DEFAULT_LANG, flags=None) -> str:
    """Status strip for the three knowledge sources. flags=None → standing by."""
    used = dict(zip(("crop", "weather", "scheme"), flags or (False, False, False)))
    chips = "".join(_tool_chip(t(key, lang), used[tool], lang) for tool, key in _TOOL_SPECS)
    if flags is None:
        caption = t("tools_idle", lang)
    elif any(used.values()):
        caption = t("tools_used", lang, n=sum(used.values()))
    else:
        caption = t("tools_none", lang)
    return (
        f'<div class="ag-tools">'
        f'<div class="ag-tools-caption">{caption}</div>'
        f'<div class="ag-tools-row">{chips}</div>'
        f'</div>'
    )


def _no_tools_html(lang: str = DEFAULT_LANG) -> str:
    return _tools_strip(lang, None)


def _tool_flags(state) -> tuple:
    """Which knowledge sources the agent actually consulted for this answer."""
    return (
        bool(state.crop_data and state.crop_data.get("context")),
        bool(state.weather_data and state.weather_data.get("context")),
        bool(state.scheme_docs and state.scheme_docs[0].get("context")),
    )


# ── Theme ─────────────────────────────────────────────────────────────────────

def build_theme():
    """Drive Gradio's own components from the palette.

    Gradio exposes a `*_dark` twin for every colour variable, so setting both
    here keeps the native widgets in step with the custom CSS in either theme —
    far more robust than overriding Gradio's internals from CSS alone.
    """
    return gr.themes.Base(
        # Inter for Latin; Noto Sans covers Devanagari (Hindi, Marathi) and
        # Gurmukhi (Punjabi) — the browser picks per glyph.
        font=[gr.themes.GoogleFont("Inter"), gr.themes.GoogleFont("Noto Sans Devanagari"),
              gr.themes.GoogleFont("Noto Sans Gurmukhi"), "system-ui", "-apple-system",
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
/* The top bar is a Gradio Row: stop its children stretching to equal widths */
.ag-topbar > * { flex: 0 1 auto !important; min-width: 0 !important; width: auto !important; }
.ag-topbar .block, .ag-topbar .form { padding: 0 !important; border: none !important;
  background: transparent !important; box-shadow: none !important; }

/* ═══ Language picker — segmented control ═══ */
.ag-lang { background: transparent !important; }
.ag-lang .wrap { display: flex !important; flex-wrap: wrap; gap: 6px !important; }
.ag-lang label {
  display: inline-flex !important; align-items: center;
  margin: 0 !important;
  padding: 7px 13px !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 2px !important;
  background: transparent !important;
  box-shadow: none !important;
  font-size: 13px !important; font-weight: 500 !important;
  color: var(--ag-dim) !important;
  cursor: pointer;
  transition: border-color .16s ease, color .16s ease, background .16s ease;
}
.ag-lang label:hover { color: var(--ag-text) !important; border-color: var(--ag-line-2) !important; }
.ag-lang label.selected, .ag-lang label:has(input:checked) {
  border-color: var(--ag-accent) !important;
  background: var(--ag-accent-bg) !important;
  color: var(--ag-text) !important;
  font-weight: 600 !important;
}
/* Hide the radio dot but keep it focusable for keyboard users */
.ag-lang input[type="radio"] {
  position: absolute !important; opacity: 0 !important;
  width: 1px !important; height: 1px !important; margin: 0 !important;
}
.ag-lang label:has(input:focus-visible) { outline: 2px solid var(--ag-accent); outline-offset: 2px; }
.ag-lang label span { margin-left: 0 !important; }

/* ═══ Indic scripts ═══
   The design's wide tracking and uppercase are Latin-only devices: tracking
   pulls Devanagari/Gurmukhi letters off their headline bar. The page carries
   lang="hi|mr|pa" once a language is picked, so relax them there. */
html:is([lang="hi"], [lang="mr"], [lang="pa"]) :is(
  .ag-brand-name, .ag-hero-eyebrow, .ag-eyebrow-text, .ag-tools-caption,
  .ag-chip-note, .ag-footer, .ag-phrase-lang, .ag-panel label > span,
  .ag-ask button, button.ag-ask, .ag-diag .label-wrap
) {
  letter-spacing: .01em !important;
  text-transform: none !important;
}
html:is([lang="hi"], [lang="mr"], [lang="pa"]) .ag-hero h1 {
  letter-spacing: 0;
  line-height: 1.3;
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
# Typed questions are English, so the clickable examples are English in every
# UI language. The spoken prompts under "Or say it aloud" follow the language
# picked on the page (app/ui/i18n.py → SPOKEN_EXAMPLES).
_TYPED_EXAMPLES = [
    "My wheat is 40 days old, which fertiliser should I apply?",
    "Will it rain in Nashik tomorrow? Should I irrigate my paddy?",
    "How do I apply for the PM-Kisan scheme?",
    "The leaves on my tomato plants are turning yellow.",
]


def _phrases_html(lang: str) -> str:
    lines = "".join(f'<div class="ag-phrase">{p}</div>'
                    for p in SPOKEN_EXAMPLES[normalize_lang(lang)])
    return f'<div class="ag-phrases"><div class="ag-phrase-group">{lines}</div></div>'


# ── Localised fragments ───────────────────────────────────────────────────────

def _mode_info() -> str:
    """Technical build line under the hero (kept in English — it's diagnostic)."""
    if USE_STUB_LLM:
        llm_mode = "rule-based"
    elif USE_HF_INFERENCE_API:
        llm_mode = "HF Inference API"
    else:
        llm_mode = f"local ({LOCAL_LLM_MODEL_ID})"
    if LITE_MODE:
        return (f"lite · typed input · keyword scheme search · {AGENT_BACKEND} agent · "
                f"rule-based answers · gTTS")
    return (f"stt {WHISPER_MODEL_ID} · "
            f"mt {'stub' if USE_STUB_TRANSLATION else 'indictrans2'} · "
            f"agent {AGENT_BACKEND} · llm {llm_mode} · rag {RAG_BACKEND} · tts {TTS_ENGINE}")


def _brand_html(lang: str) -> str:
    return ('<div class="ag-brand"><span class="ag-brand-mark"></span>'
            f'<span class="ag-brand-name">{t("brand", lang)}</span></div>')


def _hero_html(lang: str) -> str:
    body = t("hero_body_lite" if LITE_MODE else "hero_body_full", lang)
    return (f'<div class="ag-hero">'
            f'<div class="ag-hero-eyebrow">{t("hero_eyebrow", lang)}</div>'
            f'<h1>{t("hero_title", lang)}</h1><p>{body}</p>'
            f'<div class="ag-mode">{_mode_info()}</div></div>')


def _footer_html(lang: str) -> str:
    return (f'<div class="ag-footer"><span>{t("footer_left", lang)}</span>'
            f'<span>Whisper · LangChain · FAISS · gTTS</span></div>')


def _localized(lang, detected_key=None, tools_flags=None) -> list:
    """An update for every language-dependent component, in the same order as
    the `localized` list in build_ui(). Runs whenever the language changes."""
    lang = normalize_lang(lang)
    return [
        gr.update(value=_brand_html(lang)),
        gr.update(value=_hero_html(lang)),
        gr.update(value=_eyebrow(t("eyebrow_speak", lang), "01")),
        gr.update(value=_note(t("mic_note", lang, language=lang_name(lang, lang)))),
        gr.update(value=_eyebrow(t("eyebrow_or_type", lang), "02")),
        gr.update(value=_eyebrow(t("eyebrow_question", lang), "01")),
        gr.update(value=_note(t("lite_note", lang))),
        gr.update(placeholder=t("text_placeholder", lang)),
        gr.update(value=_eyebrow(t("eyebrow_location", lang), "02" if LITE_MODE else "03")),
        gr.update(value=_note(t("location_note", lang))),
        gr.update(placeholder=t("location_placeholder", lang)),
        gr.update(value=t("ask_button", lang)),
        gr.update(value=_eyebrow(t("eyebrow_detected", lang))),
        gr.update(value=_detected_text(lang, detected_key)),
        gr.update(value=_eyebrow(t("eyebrow_try", lang))),
        gr.update(value=_eyebrow(t("eyebrow_response", lang))),
        gr.update(value=_note(t("answer_note", lang)),
                  visible=lang != "en" and not _MT_READY),
        gr.update(value=_tools_strip(lang, tools_flags)),
        gr.update(placeholder=t("answer_placeholder", lang)),
        gr.update(label=t("audio_label", lang)),
        gr.update(value=_eyebrow(t("eyebrow_say_aloud", lang))),
        gr.update(value=_phrases_html(lang)),
        gr.update(label=t("diag", lang)),
        gr.update(label=t("heard_label", lang), placeholder=t("heard_placeholder", lang)),
        gr.update(label=t("english_label", lang), placeholder=t("english_placeholder", lang)),
        gr.update(label=t("intent_label", lang)),
        gr.update(label=t("trace_label", lang)),
        gr.update(value=_footer_html(lang)),
    ]


# ── UI builder ────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    lang = DEFAULT_LANG

    with gr.Blocks(title="Agri Assistant", fill_width=True) as demo:
        # Remembered so a language switch can re-render the last result's
        # language readout and tool chips in the new language.
        detected_state = gr.State(None)
        tools_state = gr.State(None)

        # ── Top bar: brand + language picker ──────────────────────────────────
        with gr.Row(equal_height=True, elem_classes=["ag-topbar"]):
            brand_html = gr.HTML(_brand_html(lang))
            lang_radio = gr.Radio(
                choices=LANG_CHOICES,
                value=lang,
                label=t("lang_picker", lang),
                show_label=False,
                container=False,
                elem_classes=["ag-lang"],
            )

        # ── Hero ──────────────────────────────────────────────────────────────
        hero_html = gr.HTML(_hero_html(lang))

        # ── Console ───────────────────────────────────────────────────────────
        with gr.Row(equal_height=False, elem_classes=["ag-console"]):

            # ── LEFT: the ask ────────────────────────────────────────────────
            with gr.Column(scale=5, min_width=300,
                           elem_classes=["ag-panel", "ag-panel--ask"]):
                # Voice (full build) — hidden on LITE_MODE hosts (no Whisper).
                speak_eyebrow = gr.HTML(_eyebrow(t("eyebrow_speak", lang), "01"),
                                        visible=not LITE_MODE)
                mic_note = gr.HTML(_note(t("mic_note", lang, language=lang_name(lang, lang))),
                                   visible=not LITE_MODE)
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    show_label=False,
                    elem_classes=["ag-mic"],
                    visible=not LITE_MODE,
                )
                or_type_eyebrow = gr.HTML(_eyebrow(t("eyebrow_or_type", lang), "02"),
                                          visible=not LITE_MODE)
                # Typed-only (LITE_MODE)
                question_eyebrow = gr.HTML(_eyebrow(t("eyebrow_question", lang), "01"),
                                           visible=LITE_MODE)
                lite_note = gr.HTML(_note(t("lite_note", lang)), visible=LITE_MODE)

                text_input = gr.Textbox(
                    placeholder=t("text_placeholder", lang),
                    show_label=False,
                    lines=3,
                )

                location_eyebrow = gr.HTML(
                    _eyebrow(t("eyebrow_location", lang), "02" if LITE_MODE else "03"))
                location_note = gr.HTML(_note(t("location_note", lang)))
                location_input = gr.Textbox(
                    placeholder=t("location_placeholder", lang),
                    show_label=False,
                )

                submit_btn = gr.Button(
                    t("ask_button", lang),
                    variant="primary",
                    size="lg",
                    elem_classes=["ag-ask"],
                )

                detected_eyebrow = gr.HTML(_eyebrow(t("eyebrow_detected", lang)))
                detected_lang_output = gr.Textbox(
                    value=t("pending", lang),
                    show_label=False,
                    container=False,
                    interactive=False,
                    lines=1,
                    max_lines=1,
                    elem_classes=["ag-detected"],
                )

                try_eyebrow = gr.HTML(_eyebrow(t("eyebrow_try", lang)))
                with gr.Column(elem_classes=["ag-examples"]):
                    for example in _TYPED_EXAMPLES:
                        gr.Button(
                            example, size="sm", elem_classes=["ag-example"]
                        ).click(fn=lambda e=example: e, inputs=None,
                                outputs=text_input)

            # ── RIGHT: the answer ────────────────────────────────────────────
            with gr.Column(scale=7, min_width=340,
                           elem_classes=["ag-panel", "ag-panel--answer"]):

                response_eyebrow = gr.HTML(_eyebrow(t("eyebrow_response", lang)))
                answer_note = gr.HTML(_note(t("answer_note", lang)), visible=False)

                tools_html_output = gr.HTML(_no_tools_html(lang))

                answer_output = gr.Textbox(
                    show_label=False,
                    lines=10,
                    max_lines=26,
                    interactive=False,
                    placeholder=t("answer_placeholder", lang),
                    elem_classes=["ag-answer"],
                )

                audio_output = gr.Audio(
                    label=t("audio_label", lang),
                    autoplay=True,
                    interactive=False,
                    elem_classes=["ag-audio"],
                )

                say_eyebrow = gr.HTML(_eyebrow(t("eyebrow_say_aloud", lang)),
                                      visible=not LITE_MODE)
                phrases_html = gr.HTML(_phrases_html(lang), visible=not LITE_MODE)

        # ── Diagnostics ───────────────────────────────────────────────────────
        with gr.Accordion(t("diag", lang), open=False,
                          elem_classes=["ag-diag"]) as diag_accordion:
            with gr.Row():
                transcription_output = gr.Textbox(
                    label=t("heard_label", lang),
                    lines=3,
                    interactive=False,
                    placeholder=t("heard_placeholder", lang),
                )
                english_output = gr.Textbox(
                    label=t("english_label", lang),
                    lines=3,
                    interactive=False,
                    placeholder=t("english_placeholder", lang),
                )
            intent_output = gr.Textbox(label=t("intent_label", lang), lines=6,
                                       interactive=False)
            trace_output = gr.Textbox(label=t("trace_label", lang), lines=14,
                                      interactive=False, visible=DEV_MODE)

        # ── Footer ────────────────────────────────────────────────────────────
        footer_html = gr.HTML(_footer_html(lang))

        # ── Wiring ────────────────────────────────────────────────────────────
        # Order must match _localized().
        localized = [
            brand_html, hero_html, speak_eyebrow, mic_note, or_type_eyebrow,
            question_eyebrow, lite_note, text_input, location_eyebrow, location_note,
            location_input, submit_btn, detected_eyebrow, detected_lang_output,
            try_eyebrow, response_eyebrow, answer_note, tools_html_output,
            answer_output, audio_output, say_eyebrow, phrases_html, diag_accordion,
            transcription_output, english_output, intent_output, trace_output,
            footer_html,
        ]

        submit_btn.click(
            fn=_on_ask,
            inputs=[audio_input, text_input, location_input, lang_radio],
            outputs=[
                detected_lang_output,
                transcription_output,
                english_output,
                answer_output,
                audio_output,
                intent_output,
                tools_html_output,
                trace_output,
                detected_state,
                tools_state,
            ],
        )
        lang_radio.change(
            fn=_localized,
            inputs=[lang_radio, detected_state, tools_state],
            outputs=localized,
        )
        # Tag the page with the language so the CSS can relax the letterspacing
        # that would otherwise break Devanagari / Gurmukhi letterforms.
        lang_radio.change(fn=None, inputs=lang_radio,
                          js="(l) => { document.documentElement.lang = l; }")

    return demo
