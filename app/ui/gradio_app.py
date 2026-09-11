"""Gradio UI — farmer-facing console, in English, Hindi, Punjabi and Marathi.

Flow: a spoken or typed question → understanding (what is asked, what is
missing) → a question back to the farmer when something is missing, else the
agent (LangChain ReAct by default: crop / weather / scheme tools) → the answer
in the farmer's language → spoken reply.

The language picked in the top bar drives the whole interface (app/ui/i18n.py),
the language the microphone listens in, and the language of the answer.

Engines (app/config.py):
  • GROQ_API_KEY set — Groq's Whisper-large-v3 hears all four languages and
    an open-weight LLM understands the question and writes the answer in the
    farmer's language, from the tool facts only. Fits the 512 MB Render host.
  • no key, full build — local Whisper; answers in English unless IndicTrans2
    is configured.
  • no key, LITE build — typed English questions only.
"""
import html
import time
import gradio as gr

from app.utils.logging import get_logger
from app.config import (
    DEV_MODE, WHISPER_MODEL_ID, USE_STUB_TRANSLATION, USE_STUB_LLM,
    USE_HF_INFERENCE_API, LOCAL_LLM_MODEL_ID, TTS_ENGINE, LITE_MODE, RAG_BACKEND,
    AGENT_BACKEND, USE_GROQ, GROQ_LLM_MODELS, GROQ_STT_MODEL, STT_ENGINE,
    VOICE_READY, REGIONAL_READY,
)
from app.ui.i18n import (
    DEFAULT_LANG, LANG_CHOICES, SPOKEN_EXAMPLES, lang_name, normalize_lang, t,
)

logger = get_logger(__name__)

# A local English↔regional translator (IndicTrans2) is configured.
_MT_READY = not USE_STUB_TRANSLATION

# Groq failures → what the farmer is told.
_GROQ_ERROR_KEYS = {"rate_limit": "err_busy", "too_large": "err_too_long"}


def _has_indic(text: str) -> bool:
    """True if text contains Devanagari (U+0900–097F) or Gurmukhi (U+0A00–0A7F)."""
    return any(0x0900 <= ord(ch) <= 0x0A7F for ch in text)


def _typed_language(text: str, ui_lang: str) -> str:
    """The language a typed question is written in, judged by its script."""
    if any(0x0A00 <= ord(ch) <= 0x0A7F for ch in text):
        return "pa"
    if any(0x0900 <= ord(ch) <= 0x097F for ch in text):
        return ui_lang if ui_lang in ("hi", "mr") else "hi"
    return "en"

# ── Singletons ────────────────────────────────────────────────────────────────
_stt = None
_translator = None
_llm = None
_orchestrator = None
_tts = None


def _get_stt():
    global _stt
    if _stt is None:
        if STT_ENGINE == "groq":
            from app.models.stt import GroqWhisperSTT
            _stt = GroqWhisperSTT()
        else:
            from app.models.stt import WhisperSTT
            from app.utils.device import get_device
            _stt = WhisperSTT(device=get_device())
    return _stt


def _groq():
    """The shared Groq client, or None when no key is configured."""
    if not USE_GROQ:
        return None
    from app.models.groq_client import get_groq_client
    return get_groq_client()


def _get_translator():
    global _translator
    if _translator is None:
        from app.models.translation import get_translator
        from app.utils.device import get_device
        _translator = get_translator(device=get_device(), use_stub=USE_STUB_TRANSLATION)
    return _translator


def _get_llm():
    """The agent's own answer LLM. With Groq on, Groq writes the farmer's answer
    and this rule-based composer only provides the English fallback, so no slow
    local model is loaded. Otherwise: real (local/API) when USE_STUB_LLM is off."""
    global _llm
    if _llm is None:
        from app.models.llm import get_llm
        # Only probe the device for a real local model — the stub needs nothing,
        # and device probing would import torch (absent on LITE_MODE hosts).
        if USE_STUB_LLM or USE_GROQ:
            _llm = get_llm(use_stub=True)
        else:
            from app.utils.device import get_device
            _llm = get_llm(device=get_device(), use_stub=False)
    return _llm


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


def _speak(text: str, lang: str, trace: list) -> "str | None":
    """Voice for `text` in `lang` — a path to an audio file, or None."""
    from app.agents.reply_writer import clean_for_speech
    voice_text = clean_for_speech(text)[:1200]
    if not voice_text:
        return None
    try:
        t0 = time.time()
        path = _get_tts().generate(voice_text, lang)
        trace.append(f"[TTS] {TTS_ENGINE} · {lang} in {time.time()-t0:.1f}s"
                     f"{'' if path else ' — no audio, text still shown'}")
        return path
    except Exception as e:
        logger.error("TTS failed: %s", e)
        trace.append(f"[TTS] ERROR: {e} — text answer still shown")
        return None


def _run_output_stage(state, trace, target_lang: "str | None" = None) -> "str | None":
    """Output boundary for the IndicTrans2 build — translate the English answer
    to the farmer's language and synthesize voice. Returns an audio path or None.

    target_lang: the language to answer in (the one chosen on the page). When
    omitted, the language the question was asked in is used."""
    answer = (state.english_answer or "").strip()
    if not answer:
        return None

    if target_lang is None:
        target_lang = state.source_language
    target = target_lang if target_lang in ("hi", "mr", "pa") else "en"

    # English answer → regional text (skip when stubbed or already English)
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

    # Text → voice (trim long text to keep the clip reasonable)
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

def _pending(u, plan) -> "dict | None":
    """What to remember when the farmer was asked for a missing detail, so a
    reply of just "40 days" or "Nashik" completes the earlier question."""
    if not plan.missing:
        return None
    return {"english": u.english, "missing": plan.missing, "understanding": u.to_dict()}


def _intent_label(u) -> str:
    wants = [u.wants_crop_advice, u.wants_weather, u.wants_scheme]
    if sum(wants) > 1:
        return "multiple"
    if u.wants_scheme:
        return "government_scheme"
    if u.wants_weather:
        return "weather"
    return {"fertilizer": "fertilizer", "irrigation": "irrigation",
            "pest_disease": "pest_or_disease"}.get(u.advice_topic or "", "crop_advice")


def _intent_summary(u, plan) -> str:
    tools = [n for n, on in (("crop", plan.run_crop), ("weather", plan.run_weather),
                             ("scheme", plan.run_scheme)) if on]
    age = f"{u.crop_age_days} days" if u.crop_age_days is not None else "—"
    return (f"Understood by : {u.engine}\n"
            f"Topic         : {u.topic}\n"
            f"Crop          : {u.crop or '—'}\n"
            f"Age           : {age}\n"
            f"Place         : {u.weather_place or '—'}\n"
            f"Tools         : {' '.join(tools) or '—'}\n"
            f"Asked back    : {', '.join(plan.missing) or '—'}")


def _pipeline(audio, text_query, location, lang, pending=None) -> dict:
    """Full pipeline: (typed text OR voice) → understanding → agent → answer → voice.

    `lang` is the language chosen on the page. It controls every message the
    farmer sees and hears, the language the microphone listens for, and the
    language of the answer. `pending` is the question the assistant is waiting
    on a detail for (crop age, place, crop), if any.
    """
    from app.agents.answering import generate_answer
    from app.agents.clarify import check_results, plan_request
    from app.agents.state import AgentState
    from app.agents.understanding import understand

    lang = normalize_lang(lang)
    text_query = (text_query or "").strip()
    saved_location = (location or "").strip() or None
    started = time.time()
    client = _groq()
    trace = [f"[UI] language: {lang} · stt {STT_ENGINE} · "
             f"understanding {'groq llm' if client else 'rules'}"]

    def reply_only(message, detected_key=None, heard="", english="", intent="", keep=None):
        """A reply that is just a message — a question back to the farmer, or a
        problem to report. Shown and spoken like any answer."""
        audio_path = _speak(message, lang, trace)
        trace.append(f"[Total] response time: {time.time()-started:.1f}s")
        return {"detected": _detected_text(lang, detected_key), "transcription": heard,
                "english": english, "answer": message, "audio": audio_path,
                "intent": intent, "tools_html": _no_tools_html(lang),
                "trace": "\n".join(trace), "detected_key": detected_key,
                "tools_flags": None, "pending": keep, "heard": heard}

    # ── 1. The farmer's words ────────────────────────────────────────────────
    english_hint = None
    if text_query:
        mode, q_lang, heard = "typed", _typed_language(text_query, lang), text_query
        if q_lang != "en" and not REGIONAL_READY:
            key = "err_type_english_lite" if LITE_MODE else "err_type_english"
            return reply_only(t(key, lang), keep=pending)
        trace.append(f"[Input] typed ({q_lang}): '{heard}'")
    elif audio is None:
        return reply_only(t("err_no_input" if VOICE_READY else "err_no_input_lite", lang),
                          keep=pending)
    else:
        from app.models.groq_client import GroqError
        mode, q_lang = "voice", lang
        # Without a regional-language engine, Whisper's own speech→English
        # translation carries a regional question to the agent.
        whisper_mt = lang != "en" and not REGIONAL_READY
        t0 = time.time()
        try:
            result = _get_stt().transcribe(audio, language=lang, translate=whisper_mt)
        except GroqError as e:
            logger.error("STT failed: %s", e)
            trace.append(f"[STT] ERROR ({e.kind}): {e}")
            return reply_only(t(_GROQ_ERROR_KEYS.get(e.kind, "err_service"), lang),
                              detected_key=(lang, "voice"), keep=pending)
        except Exception as e:
            logger.error("STT failed: %s", e)
            return reply_only(t("err_stt", lang, err=e), keep=pending)
        heard = (result.get("text") or "").strip()
        trace.append(f"[STT] {getattr(_get_stt(), 'model_id', WHISPER_MODEL_ID)} · {lang} · "
                     f"{time.time()-t0:.1f}s: '{heard}'")
        if not heard:
            return reply_only(t("err_no_speech", lang), detected_key=(lang, "voice"),
                              keep=pending)
        if whisper_mt:
            english_hint = result.get("english_text") or None
            trace.append(f"[Translate] Whisper speech→English: '{english_hint}'")
    detected_key = (q_lang, mode)

    # IndicTrans2 build (no Groq): translate the question for the router.
    if english_hint is None and q_lang != "en" and _MT_READY and not client:
        try:
            english_hint = _get_translator().translate_to_english(heard, q_lang)
            trace.append(f"[Translate] {q_lang}→en: '{english_hint}'")
        except Exception as e:
            logger.error("Translation failed: %s", e)
            trace.append(f"[Translate] ERROR: {e} — using original text")

    # ── 2. Understand: what is asked, and what is missing ────────────────────
    t0 = time.time()
    u = understand(heard, lang, saved_location=saved_location, pending=pending,
                   client=client, english=english_hint)
    trace.append(f"[Understand] {u.summary()} ({time.time()-t0:.1f}s)")
    trace.append(f"[Understand] english: '{u.english}'")
    plan = plan_request(u, lang)
    intent = _intent_summary(u, plan)
    if plan.reply:
        trace.append(f"[Clarify] {', '.join(plan.missing) or u.topic} → asking the farmer")
        return reply_only(plan.reply, detected_key, heard, u.english, intent,
                          keep=_pending(u, plan))

    # ── 3. Agent: the tools the question needs ───────────────────────────────
    state = AgentState(source_language=q_lang, original_text=heard,
                       english_text=u.english, location=plan.location)
    state.intent = _intent_label(u)
    state.crop, state.crop_stage_days = plan.crop, plan.days
    state.needs_crop_info, state.needs_weather = plan.run_crop, plan.run_weather
    state.needs_scheme, state.scheme_query = plan.run_scheme, plan.scheme_query
    state.tool_plan = plan.tool_plan()
    trace.append(f"[Agent] {AGENT_BACKEND}{' · rule-based ReAct policy' if USE_STUB_LLM or client else ''}")
    t0 = time.time()
    state = _get_orchestrator().run(state)
    trace += [f"  {msg}" for msg in state.trace]
    trace.append(f"[Agent] done in {time.time()-t0:.1f}s")

    had = (bool(state.weather_data), bool(state.scheme_docs))
    check_results(plan, state, u, lang)
    if plan.reply:  # the only part asked about could not be answered
        trace.append(f"[Clarify] after tools: {', '.join(plan.missing) or 'not covered'}")
        return reply_only(plan.reply, detected_key, heard, u.english, intent,
                          keep=_pending(u, plan))
    if (bool(state.weather_data), bool(state.scheme_docs)) != had:
        generate_answer(state, _get_llm())  # the fallback answer, minus what was dropped

    # ── 4. The answer, in the farmer's language ──────────────────────────────
    answer, answer_lang = None, lang
    if client is not None:
        from app.agents.reply_writer import write_reply
        t0 = time.time()
        try:
            answer = write_reply(client, state, lang)
            trace.append(f"[Answer] {client.last_model} wrote the {lang} answer "
                         f"in {time.time()-t0:.1f}s")
        except Exception as e:
            logger.error("Answer writing failed: %s", e)
            trace.append(f"[Answer] LLM failed ({e}) — rule-based English answer")
    if answer is None and lang != "en" and _MT_READY:
        t0 = time.time()
        try:
            answer = _get_translator().translate_from_english(state.english_answer, lang)
            trace.append(f"[Translate-out] en→{lang} in {time.time()-t0:.1f}s")
        except Exception as e:
            logger.error("Output translation failed: %s", e)
            trace.append(f"[Translate-out] ERROR: {e}")
    if answer is None:
        answer, answer_lang = state.english_answer, "en"
    state.regional_answer = answer

    notes = plan.notes(lang)
    text = answer + (f"\n\n{notes}" if notes else "")
    if answer_lang == lang:
        audio_path = _speak(text, lang, trace)
    elif REGIONAL_READY:
        # Couldn't write it in their language right now: tell them so, in their
        # language and out loud. The English stays on screen for a helper.
        fallback = t("note_english_fallback", lang, language=lang_name(lang, lang))
        text = f"{fallback}\n\n{text}"
        audio_path = _speak(f"{fallback} {notes}", lang, trace)
    else:
        audio_path = _speak(answer, "en", trace)  # English-answer build

    total = time.time() - started
    state.latency["total"] = round(total, 2)
    trace.append(f"[Total] response time: {total:.1f}s")

    flags = _tool_flags(state)
    return {"detected": _detected_text(lang, detected_key), "transcription": heard,
            "english": u.english, "answer": text, "audio": audio_path,
            "intent": intent, "tools_html": _tools_strip(lang, flags),
            "trace": "\n".join(trace), "detected_key": detected_key, "tools_flags": flags,
            "pending": _pending(u, plan), "heard": heard}


def _run_pipeline(audio, text_query, location, lang_code=DEFAULT_LANG, pending=None):
    """Pipeline result as an 8-tuple: detected language, transcript, English
    text, answer, audio path, intent summary, tool-status HTML, trace."""
    r = _pipeline(audio, text_query, location, lang_code, pending)
    return (r["detected"], r["transcription"], r["english"], r["answer"], r["audio"],
            r["intent"], r["tools_html"], r["trace"])


def _outputs(r: dict, lang: str) -> tuple:
    """Values for the page, in the order of the handlers' `outputs` lists."""
    return (r["detected"], r["transcription"], r["english"], r["answer"], r["audio"],
            r["intent"], r["tools_html"], r["trace"], _heard_html(r["heard"], lang),
            r["detected_key"], r["tools_flags"], r["pending"], r["heard"])


def _on_ask(audio, text_query, location, lang_code, pending=None):
    """Ask button: the typed question if there is one, else the recording."""
    return _outputs(_pipeline(audio, text_query, location, lang_code, pending), lang_code)


def _on_voice(audio, location, lang_code, pending=None):
    """The farmer tapped stop — answer the recording straight away. If the
    recording hasn't reached the server, change nothing: the Ask button still
    sends it."""
    if audio is None:
        return tuple(gr.skip() for _ in range(14))
    result = _outputs(_pipeline(audio, "", location, lang_code, pending), lang_code)
    return result + (None,)  # clear the recorder, ready for the next question


def _on_example(example, location, lang_code):
    """An example question was tapped — ask it as a fresh question."""
    return _outputs(_pipeline(None, example, location, lang_code, None), lang_code)


def _detected_text(ui_lang: str, detected_key) -> str:
    """'Hindi · voice', written in the UI language — or the waiting message."""
    if not detected_key:
        return t("pending", ui_lang)
    q_lang, mode = detected_key
    return f"{lang_name(q_lang, ui_lang)} · {t('mode_' + mode, ui_lang)}"


def _heard_html(heard: "str | None", lang: str) -> str:
    """'You asked: “…”' above the answer. The farmer's words are escaped."""
    if not heard:
        return ""
    return (f'<div class="ag-heard"><span class="ag-heard-label">{t("heard_prefix", lang)}</span>'
            f'“{html.escape(heard)}”</div>')


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
   lang="hi|mr|pa" once a language is picked, so relax them there.
   Gradio re-emits every rule behind a long `.gradio-container… .contain`
   prefix, which outranks a plain html[lang] selector; `:not(#ag-none)` adds
   ID-level weight so these overrides still win. */
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) :is(
  .ag-brand-name, .ag-hero-eyebrow, .ag-eyebrow-text, .ag-tools-caption,
  .ag-chip-note, .ag-footer, .ag-phrase-lang, .ag-panel label > span,
  .ag-ask button, button.ag-ask, .ag-diag .label-wrap, .ag-heard-label
) {
  letter-spacing: .01em !important;
  text-transform: none !important;
}
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) .ag-hero h1 {
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

/* ═══ Voice-first additions ═══ */
/* The microphone is the main way in: give it room and a clear edge. */
.ag-mic { min-height: 132px; border-width: 2px !important; border-color: var(--ag-accent) !important; }
.ag-mic button { font-size: 15px !important; }
/* Location field + 📍 button on one line */
.ag-place { gap: 8px !important; align-items: stretch !important; flex-wrap: nowrap !important; }
.ag-place > * { min-width: 0 !important; }
button.ag-gps {
  white-space: nowrap !important;
  font-size: 13px !important;
  border-radius: 2px !important;
  padding: 0 12px !important;
}
/* "You asked: …" above the answer */
.ag-heard { font-size: 15px; line-height: 1.6; color: var(--ag-dim); margin: 0 0 14px; }
.ag-heard-label {
  font-size: 11px; font-weight: 600;
  letter-spacing: .12em; text-transform: uppercase;
  color: var(--ag-faint);
  margin-right: 10px;
}
.ag-answer textarea { font-size: 17px !important; }
/* What I can help with */
.ag-help-line {
  font-size: 14px; line-height: 1.7;
  color: var(--ag-dim);
  padding: 11px 0;
  border-bottom: 1px solid var(--ag-line);
}
.ag-help-line:last-child { border-bottom: none; }

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
# Tapping one asks it straight away. They follow the page language when the
# app can take questions in every language; otherwise typed questions are
# English, so the examples are too.
_TYPED_EXAMPLES = [
    "My wheat is 40 days old, which fertiliser should I apply?",
    "Will it rain in Nashik tomorrow? Should I irrigate my paddy?",
    "How do I apply for the PM-Kisan scheme?",
    "The leaves on my tomato plants are turning yellow.",
]


def _examples(lang: str) -> list[str]:
    lang = normalize_lang(lang)
    if REGIONAL_READY and lang != "en":
        return list(SPOKEN_EXAMPLES[lang])
    return list(_TYPED_EXAMPLES)


def _help_html(lang: str) -> str:
    """What the assistant can help with — sets expectations before asking."""
    lines = "".join(f'<div class="ag-help-line">{t(key, lang)}</div>'
                    for key in ("help_crop", "help_weather", "help_scheme"))
    return f'<div class="ag-help">{lines}</div>'


# ── Localised fragments ───────────────────────────────────────────────────────

def _mode_info() -> str:
    """Technical build line under the hero (kept in English — it's diagnostic)."""
    if USE_GROQ:
        llm_mode = f"groq {GROQ_LLM_MODELS[0] if GROQ_LLM_MODELS else '?'}"
    elif USE_STUB_LLM:
        llm_mode = "rule-based"
    elif USE_HF_INFERENCE_API:
        llm_mode = "HF Inference API"
    else:
        llm_mode = f"local ({LOCAL_LLM_MODEL_ID})"
    voice = {"groq": f"groq {GROQ_STT_MODEL}", "local": WHISPER_MODEL_ID}.get(STT_ENGINE, "off")
    answers = "4 languages" if REGIONAL_READY else "English answers"
    return (f"{'lite' if LITE_MODE else 'full'} · voice {voice} · llm {llm_mode} · "
            f"agent {AGENT_BACKEND} · rag {RAG_BACKEND} · tts {TTS_ENGINE} · {answers}")


def _brand_html(lang: str) -> str:
    return ('<div class="ag-brand"><span class="ag-brand-mark"></span>'
            f'<span class="ag-brand-name">{t("brand", lang)}</span></div>')


def _hero_body_key() -> str:
    if VOICE_READY and REGIONAL_READY:
        return "hero_body_voice"
    return "hero_body_full" if VOICE_READY else "hero_body_lite"


def _hero_html(lang: str) -> str:
    return (f'<div class="ag-hero">'
            f'<div class="ag-hero-eyebrow">{t("hero_eyebrow", lang)}</div>'
            f'<h1>{t("hero_title", lang)}</h1><p>{t(_hero_body_key(), lang)}</p>'
            f'<div class="ag-mode">{_mode_info()}</div></div>')


def _footer_html(lang: str) -> str:
    stack = "Whisper · Groq · LangChain · gTTS" if USE_GROQ else "Whisper · LangChain · FAISS · gTTS"
    return (f'<div class="ag-footer"><span>{t("footer_left", lang)}</span>'
            f'<span>{stack}</span></div>')


def _mic_note(lang: str) -> str:
    return _note(t("mic_note_auto", lang, language=lang_name(lang, lang)))


def _localized(lang, detected_key=None, tools_flags=None, heard=None) -> list:
    """An update for every language-dependent component, in the same order as
    the `localized` list in build_ui(). Runs whenever the language changes."""
    lang = normalize_lang(lang)
    regional = REGIONAL_READY
    return [
        gr.update(value=_brand_html(lang)),
        gr.update(value=_hero_html(lang)),
        gr.update(value=_eyebrow(t("eyebrow_speak", lang), "01")),
        gr.update(value=_mic_note(lang)),
        gr.update(value=_eyebrow(t("eyebrow_or_type_any" if regional else "eyebrow_or_type",
                                   lang), "02")),
        gr.update(value=_eyebrow(t("eyebrow_question", lang), "01")),
        gr.update(value=_note(t("lite_note", lang))),
        gr.update(placeholder=t("text_placeholder_native" if regional else "text_placeholder",
                                lang)),
        gr.update(value=_eyebrow(t("eyebrow_location", lang), "03" if VOICE_READY else "02")),
        gr.update(value=_note(t("location_note_voice" if VOICE_READY else "location_note",
                                lang))),
        gr.update(placeholder=t("location_placeholder_native" if regional
                                else "location_placeholder", lang)),
        gr.update(value=t("ask_button", lang)),
        gr.update(value=_eyebrow(t("eyebrow_detected", lang))),
        gr.update(value=_detected_text(lang, detected_key)),
        gr.update(value=_eyebrow(t("eyebrow_try", lang))),
        gr.update(value=_eyebrow(t("eyebrow_response", lang))),
        gr.update(value=_note(t("answer_note", lang)),
                  visible=lang != "en" and not regional),
        gr.update(value=_tools_strip(lang, tools_flags)),
        gr.update(placeholder=t("answer_placeholder", lang)),
        gr.update(label=t("audio_label", lang)),
        gr.update(value=_eyebrow(t("eyebrow_can_help", lang))),
        gr.update(value=_help_html(lang)),
        gr.update(label=t("diag", lang)),
        gr.update(label=t("heard_label", lang), placeholder=t("heard_placeholder", lang)),
        gr.update(label=t("english_label", lang), placeholder=t("english_placeholder", lang)),
        gr.update(label=t("intent_label", lang)),
        gr.update(label=t("trace_label", lang)),
        gr.update(value=_footer_html(lang)),
        gr.update(value=t("gps_button", lang)),
        gr.update(value=_heard_html(heard, lang)),
        *[gr.update(value=e) for e in _examples(lang)],
    ]


# ── Browser-side helpers ──────────────────────────────────────────────────────
# Remember the farmer's language and place on this phone, so the next visit
# opens ready to talk. First visit: follow the phone's own language.
_RESTORE_JS = """
() => {
  let lang = null, place = "";
  try { lang = localStorage.getItem("ag_lang"); place = localStorage.getItem("ag_place") || ""; }
  catch (e) {}
  if (!["en", "hi", "pa", "mr"].includes(lang)) {
    const nav = (navigator.language || "").toLowerCase();
    lang = nav.startsWith("hi") ? "hi" : nav.startsWith("mr") ? "mr"
         : nav.startsWith("pa") ? "pa" : "en";
  }
  document.documentElement.lang = lang;
  return [lang, place];
}
"""
_SAVE_LANG_JS = """
(l) => { document.documentElement.lang = l; try { localStorage.setItem("ag_lang", l); } catch (e) {} }
"""
_SAVE_PLACE_JS = """
(p) => { try { localStorage.setItem("ag_place", p || ""); } catch (e) {} }
"""
# 📍 — the phone's GPS position, as "lat, lon" for the weather lookup.
_GPS_JS = """
async (current) => {
  if (!navigator.geolocation) { return current; }
  try {
    const pos = await new Promise((ok, fail) => navigator.geolocation.getCurrentPosition(
      ok, fail, {enableHighAccuracy: false, timeout: 15000, maximumAge: 600000}));
    return pos.coords.latitude.toFixed(4) + ", " + pos.coords.longitude.toFixed(4);
  } catch (e) { return current; }
}
"""


# ── UI builder ────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    lang = DEFAULT_LANG
    regional = REGIONAL_READY

    with gr.Blocks(title="Agri Assistant", fill_width=True) as demo:
        # Remembered so a language switch can re-render the last result's
        # language readout, tool chips and "you asked" line in the new language.
        detected_state = gr.State(None)
        tools_state = gr.State(None)
        heard_state = gr.State(None)
        # The question waiting on a detail the farmer was asked for.
        pending_state = gr.State(None)

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
                # Voice — whenever a speech-to-text engine is available.
                speak_eyebrow = gr.HTML(_eyebrow(t("eyebrow_speak", lang), "01"),
                                        visible=VOICE_READY)
                mic_note = gr.HTML(_mic_note(lang), visible=VOICE_READY)
                audio_input = gr.Audio(
                    sources=["microphone"],
                    type="filepath",
                    show_label=False,
                    editable=False,
                    elem_classes=["ag-mic"],
                    visible=VOICE_READY,
                )
                or_type_eyebrow = gr.HTML(
                    _eyebrow(t("eyebrow_or_type_any" if regional else "eyebrow_or_type",
                               lang), "02"),
                    visible=VOICE_READY)
                # Typed-only build (LITE without a Groq key)
                question_eyebrow = gr.HTML(_eyebrow(t("eyebrow_question", lang), "01"),
                                           visible=not VOICE_READY)
                lite_note = gr.HTML(_note(t("lite_note", lang)), visible=not VOICE_READY)

                text_input = gr.Textbox(
                    placeholder=t("text_placeholder_native" if regional
                                  else "text_placeholder", lang),
                    show_label=False,
                    lines=3,
                )

                location_eyebrow = gr.HTML(
                    _eyebrow(t("eyebrow_location", lang), "03" if VOICE_READY else "02"))
                location_note = gr.HTML(_note(t("location_note_voice" if VOICE_READY
                                                else "location_note", lang)))
                with gr.Row(equal_height=True, elem_classes=["ag-place"]):
                    location_input = gr.Textbox(
                        placeholder=t("location_placeholder_native" if regional
                                      else "location_placeholder", lang),
                        show_label=False,
                        scale=3,
                    )
                    gps_btn = gr.Button(t("gps_button", lang), size="sm", scale=2,
                                        elem_classes=["ag-gps"])

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
                    example_btns = [gr.Button(e, size="sm", elem_classes=["ag-example"])
                                    for e in _examples(lang)]

            # ── RIGHT: the answer ────────────────────────────────────────────
            with gr.Column(scale=7, min_width=340,
                           elem_classes=["ag-panel", "ag-panel--answer"]):

                response_eyebrow = gr.HTML(_eyebrow(t("eyebrow_response", lang)))
                answer_note = gr.HTML(_note(t("answer_note", lang)), visible=False)

                tools_html_output = gr.HTML(_no_tools_html(lang))
                heard_html = gr.HTML("")

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

                help_eyebrow = gr.HTML(_eyebrow(t("eyebrow_can_help", lang)))
                help_html = gr.HTML(_help_html(lang))

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
            intent_output = gr.Textbox(label=t("intent_label", lang), lines=7,
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
            answer_output, audio_output, help_eyebrow, help_html, diag_accordion,
            transcription_output, english_output, intent_output, trace_output,
            footer_html, gps_btn, heard_html, *example_btns,
        ]
        # Order must match _outputs().
        results = [
            detected_lang_output, transcription_output, english_output, answer_output,
            audio_output, intent_output, tools_html_output, trace_output, heard_html,
            detected_state, tools_state, pending_state, heard_state,
        ]

        submit_btn.click(
            fn=_on_ask,
            inputs=[audio_input, text_input, location_input, lang_radio, pending_state],
            outputs=results,
        )
        # Voice-first: tapping stop sends the question — no extra button to find.
        # The recorder is then cleared, ready for the next question.
        audio_input.stop_recording(
            fn=_on_voice,
            inputs=[audio_input, location_input, lang_radio, pending_state],
            outputs=results + [audio_input],
        )
        for btn in example_btns:
            btn.click(fn=lambda e: e, inputs=btn, outputs=text_input).then(
                fn=_on_example, inputs=[btn, location_input, lang_radio], outputs=results)

        gps_btn.click(fn=None, inputs=location_input, outputs=location_input, js=_GPS_JS)
        location_input.change(fn=None, inputs=location_input, js=_SAVE_PLACE_JS)

        lang_radio.change(
            fn=_localized,
            inputs=[lang_radio, detected_state, tools_state, heard_state],
            outputs=localized,
        )
        # Tag the page with the language (the CSS relaxes the letterspacing that
        # would break Devanagari / Gurmukhi) and remember it on this phone.
        lang_radio.change(fn=None, inputs=lang_radio, js=_SAVE_LANG_JS)
        demo.load(fn=None, inputs=None, outputs=[lang_radio, location_input], js=_RESTORE_JS)

    return demo
