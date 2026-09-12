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


def warm_up() -> None:
    """Load the slow pieces once at startup (in a background thread), so the
    first farmer doesn't wait for a model download or an index build."""
    try:
        t0 = time.time()
        if STT_ENGINE == "local":
            _get_stt()._load()
        from app.tools.scheme_tool import _get_rag
        _get_rag()
        _get_orchestrator()
        logger.info("Warm-up done in %.1fs (stt=%s)", time.time() - t0, STT_ENGINE)
    except Exception as exc:
        logger.warning("Warm-up skipped: %s", exc)


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


def _spoken_text(text: str) -> str:
    """What to read aloud: the advice itself, without the standing cautions and
    source lines the rule-based answer ends with. Shorter speech = less waiting."""
    for marker in ("\nImportant:", "\nSource:", "\nसूचना:"):
        cut = text.find(marker)
        if cut > 120:
            text = text[:cut]
    return text.strip()[:900]


def _speak(text: str, lang: str, trace: list) -> "str | None":
    """Voice for `text` in `lang` — a path to an audio file, or None."""
    from app.agents.reply_writer import clean_for_speech
    voice_text = _spoken_text(clean_for_speech(text))
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


def _pipeline_iter(audio, text_query, location, lang, pending=None):
    """Full pipeline: (typed text OR voice) → understanding → agent → answer → voice.

    Yields the reply twice: first the words, then the same reply with its
    recording attached. Making the speech takes a few seconds, and the farmer
    should not stare at an empty screen while it happens.

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
        problem to report. Shown, then spoken, like any answer."""
        result = {"detected": _detected_text(lang, detected_key), "transcription": heard,
                  "english": english, "answer": message, "audio": None,
                  "intent": intent, "tools_html": _no_tools_html(lang),
                  "trace": "\n".join(trace), "detected_key": detected_key,
                  "tools_flags": None, "pending": keep, "heard": heard}
        yield result
        audio_path = _speak(message, lang, trace)
        trace.append(f"[Total] response time: {time.time()-started:.1f}s")
        yield {**result, "audio": audio_path, "trace": "\n".join(trace)}

    # ── 1. The farmer's words ────────────────────────────────────────────────
    english_hint = None
    if text_query:
        # Typed Hindi/Punjabi/Marathi is understood in every build — by the LLM
        # when there is one, by the keyword rules otherwise (the answer is then
        # English, and the page says so).
        mode, q_lang, heard = "typed", _typed_language(text_query, lang), text_query
        trace.append(f"[Input] typed ({q_lang}): '{heard}'")
    elif audio is None:
        yield from reply_only(t("err_no_input" if VOICE_READY else "err_no_input_lite", lang),
                          keep=pending)
        return
    else:
        from app.models.groq_client import GroqError
        mode, q_lang = "voice", lang
        t0 = time.time()
        try:
            result = _get_stt().transcribe(audio, language=lang)
        except GroqError as e:
            logger.error("STT failed: %s", e)
            trace.append(f"[STT] ERROR ({e.kind}): {e}")
            yield from reply_only(t(_GROQ_ERROR_KEYS.get(e.kind, "err_service"), lang),
                              detected_key=(lang, "voice"), keep=pending)
            return
        except Exception as e:
            logger.error("STT failed: %s", e)
            yield from reply_only(t("err_stt", lang, err=e), keep=pending)
            return
        heard = (result.get("text") or "").strip()
        trace.append(f"[STT] {getattr(_get_stt(), 'model_id', WHISPER_MODEL_ID)} · {lang} · "
                     f"{time.time()-t0:.1f}s: '{heard}'")
        if not heard:
            yield from reply_only(t("err_no_speech", lang), detected_key=(lang, "voice"),
                              keep=pending)
            return
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
    if (mode == "voice" and client is None and lang != "en" and u.topic != "farming"
            and STT_ENGINE == "local"):
        # The keyword rules made nothing of this transcript. Only now is it
        # worth a second (slow) Whisper pass, asking it to translate the same
        # clip into English — most questions never need it.
        try:
            again = _get_stt().transcribe(audio, language=lang, translate=True)
            english_hint = (again.get("english_text") or "").strip() or None
            if english_hint:
                trace.append(f"[Translate] Whisper speech→English: '{english_hint}'")
                u = understand(heard, lang, saved_location=saved_location,
                               pending=pending, client=client, english=english_hint)
        except Exception as e:
            logger.warning("Whisper translate pass failed: %s", e)
    trace.append(f"[Understand] {u.summary()} ({time.time()-t0:.1f}s)")
    trace.append(f"[Understand] english: '{u.english}'")
    plan = plan_request(u, lang)
    intent = _intent_summary(u, plan)
    if plan.reply:
        trace.append(f"[Clarify] {', '.join(plan.missing) or u.topic} → asking the farmer")
        yield from reply_only(plan.reply, detected_key, heard, u.english, intent,
                          keep=_pending(u, plan))
        return

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
        yield from reply_only(plan.reply, detected_key, heard, u.english, intent,
                          keep=_pending(u, plan))
        return
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
    speech, speech_lang = text, answer_lang
    if answer_lang != lang and REGIONAL_READY:
        # Couldn't write it in their language right now: tell them so, in their
        # language and out loud. The English stays on screen for a helper.
        fallback = t("note_english_fallback", lang, language=lang_name(lang, lang))
        text = f"{fallback}\n\n{text}"
        speech, speech_lang = f"{fallback} {notes}", lang
    elif answer_lang != lang:
        speech = answer  # English-answer build: read the advice, skip the notes

    flags = _tool_flags(state)
    result = {"detected": _detected_text(lang, detected_key), "transcription": heard,
              "english": u.english, "answer": text, "audio": None,
              "intent": intent, "tools_html": _tools_strip(lang, flags),
              "trace": "\n".join(trace), "detected_key": detected_key, "tools_flags": flags,
              "pending": _pending(u, plan), "heard": heard}
    trace.append(f"[Answer] shown after {time.time()-started:.1f}s; now speaking")
    yield result

    audio_path = _speak(speech, speech_lang, trace)
    total = time.time() - started
    state.latency["total"] = round(total, 2)
    trace.append(f"[Total] response time: {total:.1f}s")
    yield {**result, "audio": audio_path, "trace": "\n".join(trace)}


def _pipeline(audio, text_query, location, lang, pending=None) -> dict:
    """The finished reply (words and recording) — the whole pipeline, waited out."""
    result = None
    for result in _pipeline_iter(audio, text_query, location, lang, pending):
        pass
    return result


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


# The handlers stream: the words reach the page as soon as they exist, the
# recording follows a few seconds later.

def _on_ask(audio, text_query, location, lang_code, pending=None):
    """Ask button: the typed question if there is one, else the recording."""
    for r in _pipeline_iter(audio, text_query, location, lang_code, pending):
        yield _outputs(r, lang_code)


def _on_voice(audio, location, lang_code, pending=None):
    """The farmer tapped stop — answer the recording straight away. If the
    recording hasn't reached the server, change nothing: the Ask button still
    sends it."""
    if audio is None:
        yield tuple(gr.skip() for _ in range(14))
        return
    for r in _pipeline_iter(audio, "", location, lang_code, pending):
        # The last value clears the recorder, ready for the next question.
        yield _outputs(r, lang_code) + (None,)


def _on_example(example, location, lang_code):
    """An example question was tapped — ask it as a fresh question."""
    for r in _pipeline_iter(None, example, location, lang_code, None):
        yield _outputs(r, lang_code)


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
# One column, one job per screenful, almost no text to read. A farmer who
# cannot read should be able to: see their language, tap the microphone, talk,
# and hear the answer. Everything else (typing, location, what-I-can-help-with,
# diagnostics) is folded away behind a single line each.
#
# Design language: dark-first editorial. A near-black canvas, hairline rules,
# one restrained accent (wheat gold). A full light palette ships alongside —
# Gradio puts `dark` on <body> and follows the viewer's system setting, so every
# colour below is a token defined for both. Append `?__theme=dark` (or `light`)
# to the URL to pin one.
#
# Rule: never hardcode a colour in generated HTML — only token-backed classes,
# or it inverts badly in the other theme.
# ══════════════════════════════════════════════════════════════════════════════

_TOOL_SPECS = (
    ("crop", "tool_crop"),
    ("weather", "tool_weather"),
    ("scheme", "tool_scheme"),
)


def _note(text: str) -> str:
    return f'<div class="ag-field-note">{text}</div>'


def _tools_strip(lang: str = DEFAULT_LANG, flags=None) -> str:
    """One quiet line naming the sources behind the answer. Nothing before the
    first question, and nothing when no source was needed."""
    if not flags or not any(flags):
        return ""
    used = " · ".join(t(key, lang) for (_tool, key), on in zip(_TOOL_SPECS, flags) if on)
    return (f'<div class="ag-src"><span class="ag-src-dot"></span><span>{used}</span>'
            f'<span class="ag-src-note">{t("chip_used", lang)}</span></div>')


def _no_tools_html(lang: str = DEFAULT_LANG) -> str:
    return ""


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
        text_size=gr.themes.sizes.text_lg,
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

/* ═══ Shell — one narrow column, nothing else ═══ */
body { background: var(--ag-bg) !important; color: var(--ag-text); }
.gradio-container {
  max-width: 680px !important;
  margin: 0 auto !important;
  padding: 0 20px 64px !important;
  background: var(--ag-bg);
  color: var(--ag-text);
}
footer { display: none !important; }
.gradio-container .block { padding: 0 !important; }

/* ═══ Top bar: brand + the four languages, always reachable ═══ */
.ag-top {
  position: sticky; top: 0; z-index: 20;
  background: var(--ag-bg);
  padding: 14px 0 12px;
  border-bottom: 1px solid var(--ag-line);
  gap: 10px !important;
}
.ag-brand { display: flex; align-items: center; gap: 9px; padding-bottom: 2px; }
.ag-brand-mark { width: 8px; height: 8px; flex: none; background: var(--ag-accent); transform: rotate(45deg); }
.ag-brand-name { font-size: 12px; font-weight: 600; letter-spacing: .18em; text-transform: uppercase; color: var(--ag-dim); }

/* Language picker — four big taps, no labels to read */
.ag-lang { background: transparent !important; }
.ag-lang .wrap { display: grid !important; grid-template-columns: repeat(4, 1fr); gap: 6px !important; }
.ag-lang label {
  display: flex !important; align-items: center; justify-content: center;
  margin: 0 !important; padding: 12px 4px !important;
  border: 1px solid var(--ag-line) !important; border-radius: 3px !important;
  background: transparent !important; box-shadow: none !important;
  font-size: 15px !important; font-weight: 500 !important;
  color: var(--ag-dim) !important; text-align: center; line-height: 1.25;
  cursor: pointer; transition: border-color .16s ease, color .16s ease, background .16s ease;
}
.ag-lang label:hover { color: var(--ag-text) !important; border-color: var(--ag-line-2) !important; }
.ag-lang label.selected, .ag-lang label:has(input:checked) {
  border-color: var(--ag-accent) !important; background: var(--ag-accent-bg) !important;
  color: var(--ag-text) !important; font-weight: 600 !important;
}
.ag-lang input[type="radio"] { position: absolute !important; opacity: 0 !important; width: 1px !important; height: 1px !important; }
.ag-lang label:has(input:focus-visible) { outline: 2px solid var(--ag-accent); outline-offset: 2px; }
.ag-lang label span { margin-left: 0 !important; }

/* ═══ Hero — one line, then straight to the microphone ═══ */
.ag-hero { padding: 30px 0 20px; text-align: center; }
.ag-hero h1 {
  font-size: clamp(1.7rem, 6.4vw, 2.3rem); line-height: 1.18;
  letter-spacing: -.02em; font-weight: 600; margin: 0 0 10px; color: var(--ag-text);
}
.ag-hero h1 em { font-style: normal; color: var(--ag-accent); }
.ag-hero p { font-size: 15px; line-height: 1.6; color: var(--ag-dim); margin: 0; }

/* ═══ The microphone — the main action ═══ */
.ag-mic {
  border: 2px solid var(--ag-accent) !important;
  border-radius: 4px !important;
  background: var(--ag-accent-bg) !important;
  min-height: 148px;
  display: flex; align-items: center; justify-content: center;
}
.ag-mic .record, .ag-mic .record-button, .ag-mic button.record { font-size: 17px !important; }
.ag-mic button {
  font-size: 17px !important; font-weight: 600 !important;
  padding: 14px 22px !important; border-radius: 3px !important;
}
.ag-mic .icon, .ag-mic svg { width: 22px !important; height: 22px !important; }
.ag-cta {
  text-align: center; font-size: 15px; line-height: 1.6;
  color: var(--ag-dim); margin: 12px 0 4px;
}
.ag-field-note { font-size: 13px; line-height: 1.6; color: var(--ag-faint); margin: 2px 0 10px; }

/* ═══ Answer ═══ */
.ag-section {
  display: flex; align-items: center; gap: 12px; margin: 30px 0 14px;
  font-size: 11px; font-weight: 600; letter-spacing: .19em; text-transform: uppercase;
  color: var(--ag-faint);
}
.ag-section::after { content: ""; flex: 1; height: 1px; background: var(--ag-line); }
.ag-heard { font-size: 15px; line-height: 1.6; color: var(--ag-dim); margin: 0 0 12px; }
.ag-heard-label {
  font-size: 11px; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ag-faint); margin-right: 8px;
}
.ag-answer textarea {
  font-size: 18px !important; line-height: 1.75 !important;
  background: var(--ag-surface) !important;
  border: 1px solid var(--ag-line) !important;
  border-left: 3px solid var(--ag-accent) !important;
  border-radius: 3px !important;
  padding: 20px 22px !important; color: var(--ag-text) !important;
}
.ag-audio { margin-top: 12px !important; }
button.ag-replay {
  width: 100%; margin-top: 10px !important;
  font-size: 15px !important; padding: 13px 16px !important; border-radius: 3px !important;
}
.ag-src {
  display: flex; align-items: center; gap: 9px; flex-wrap: wrap;
  margin-top: 12px; font-size: 13px; color: var(--ag-dim);
}
.ag-src-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ag-accent); flex: none; }
.ag-src-note { font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--ag-faint); }

/* ═══ Sample questions — tap one and it is asked ═══ */
.ag-examples .gap, .ag-examples .form { gap: 8px !important; }
button.ag-example {
  width: 100%; justify-content: flex-start !important; text-align: left !important;
  font-size: 15px !important; font-weight: 400 !important; line-height: 1.5 !important;
  padding: 15px 16px 15px 44px !important;
  border: 1px solid var(--ag-line) !important; border-radius: 3px !important;
  background: var(--ag-surface) !important; color: var(--ag-text) !important;
  white-space: normal !important; height: auto !important; position: relative;
  transition: border-color .16s ease, background .16s ease;
}
button.ag-example::before {
  position: absolute; left: 14px; top: 50%; transform: translateY(-50%); font-size: 17px;
}
.ag-examples > *:nth-child(1) button.ag-example::before { content: "🌾"; }
.ag-examples > *:nth-child(2) button.ag-example::before { content: "🌦"; }
.ag-examples > *:nth-child(3) button.ag-example::before { content: "🏛"; }
.ag-examples > *:nth-child(4) button.ag-example::before { content: "🌱"; }
button.ag-example:hover { border-color: var(--ag-accent) !important; background: var(--ag-accent-bg) !important; }

/* ═══ Folded-away extras ═══ */
.ag-fold { margin-top: 10px !important; border-top: 1px solid var(--ag-line) !important; }
.ag-fold .label-wrap {
  padding: 16px 2px !important; font-size: 14px !important; font-weight: 500 !important;
  color: var(--ag-dim) !important;
}
.ag-fold .label-wrap:hover { color: var(--ag-text) !important; }
.ag-fold textarea, .ag-fold input[type="text"] { font-size: 16px !important; padding: 12px 13px !important; }
.ag-place { gap: 8px !important; align-items: stretch !important; flex-wrap: nowrap !important; margin-top: 4px; }
.ag-place > * { min-width: 0 !important; }
button.ag-gps, button.ag-ask {
  white-space: nowrap !important; font-size: 15px !important;
  border-radius: 3px !important; padding: 12px 14px !important;
}
button.ag-ask { width: 100%; font-weight: 600 !important; margin-top: 8px !important; }
.ag-help-line { font-size: 15px; line-height: 1.65; color: var(--ag-dim); padding: 11px 0; border-bottom: 1px solid var(--ag-line); }
.ag-help-line:last-child { border-bottom: none; }
.ag-diag textarea {
  font-family: var(--font-mono) !important; font-size: 12px !important; line-height: 1.6 !important;
  background: var(--ag-sunk) !important; border: 1px solid var(--ag-line) !important;
  border-radius: 2px !important; color: var(--ag-dim) !important;
}
.ag-mode {
  display: block; margin-top: 10px; padding: 8px 10px;
  border: 1px solid var(--ag-line); border-radius: 2px; background: var(--ag-shade);
  font-size: 11px; letter-spacing: .04em; color: var(--ag-faint);
  font-family: var(--font-mono); word-break: break-word;
}

/* ═══ Footer ═══ */
.ag-footer {
  margin-top: 34px; padding-top: 20px; border-top: 1px solid var(--ag-line);
  display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap;
  font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--ag-faint);
}

/* ═══ Indic scripts ═══
   The design's wide tracking and uppercase are Latin-only devices: tracking
   pulls Devanagari/Gurmukhi letters off their headline bar. The page carries
   lang="hi|mr|pa" once a language is picked, so relax them there.
   Gradio re-emits every rule behind a long `.gradio-container… .contain`
   prefix, which outranks a plain html[lang] selector; `:not(#ag-none)` adds
   ID-level weight so these overrides still win. */
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) :is(
  .ag-brand-name, .ag-section, .ag-heard-label, .ag-src-note, .ag-footer,
  .ag-fold .label-wrap, button.ag-ask, .ag-hero h1
) {
  letter-spacing: .01em !important;
  text-transform: none !important;
}
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) .ag-hero h1 { line-height: 1.3; }

@media (max-width: 480px) {
  .gradio-container { padding: 0 14px 48px !important; }
  .ag-lang label { font-size: 14px !important; padding: 11px 2px !important; }
  .ag-hero { padding: 22px 0 16px; }
}
"""

# ── Example questions ─────────────────────────────────────────────────────────
# Tapping one asks it immediately. They follow the page language — a farmer who
# reads a little can recognise a question in their own script.
_TYPED_EXAMPLES = [
    "My wheat is 40 days old, which fertiliser should I apply?",
    "Will it rain in Nashik tomorrow? Should I irrigate my paddy?",
    "How do I apply for the PM-Kisan scheme?",
    "The leaves on my tomato plants are turning yellow.",
]


def _examples(lang: str) -> list[str]:
    lang = normalize_lang(lang)
    return list(SPOKEN_EXAMPLES[lang]) if lang != "en" else list(_TYPED_EXAMPLES)


def _help_html(lang: str) -> str:
    """What the assistant can help with — sets expectations before asking."""
    lines = "".join(f'<div class="ag-help-line">{t(key, lang)}</div>'
                    for key in ("help_crop", "help_weather", "help_scheme"))
    return f'<div class="ag-help">{lines}</div>'


# ── Localised fragments ───────────────────────────────────────────────────────

def _mode_info() -> str:
    """Technical build line (English — it's diagnostic), inside the fold."""
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


def _hero_html(lang: str) -> str:
    return (f'<div class="ag-hero"><h1>{t("hero_title", lang)}</h1>'
            f'<p>{t("hero_sub", lang)}</p></div>')


def _section(text: str) -> str:
    return f'<div class="ag-section">{text}</div>'


def _footer_html(lang: str) -> str:
    stack = "Whisper · Groq · LangChain · gTTS" if USE_GROQ else "Whisper · LangChain · FAISS · gTTS"
    return (f'<div class="ag-footer"><span>{t("footer_left", lang)}</span>'
            f'<span>{stack}</span></div>')


def _localized(lang, detected_key=None, tools_flags=None, heard=None) -> list:
    """An update for every language-dependent component, in the same order as
    the `localized` list in build_ui(). Runs whenever the language changes."""
    lang = normalize_lang(lang)
    return [
        gr.update(value=_brand_html(lang)),
        gr.update(value=_hero_html(lang)),
        gr.update(value=f'<div class="ag-cta">{t("mic_cta", lang)}</div>'),
        gr.update(value=_note(t("lite_note", lang))),
        gr.update(value=_section(t("eyebrow_response", lang))),
        gr.update(value=_note(t("answer_note", lang)), visible=lang != "en" and not REGIONAL_READY),
        gr.update(value=_heard_html(heard, lang)),
        gr.update(placeholder=t("answer_placeholder", lang)),
        gr.update(label=t("audio_label", lang)),
        gr.update(value=t("replay_button", lang)),
        gr.update(value=_tools_strip(lang, tools_flags)),
        gr.update(value=_section(t("examples_label", lang))),
        *[gr.update(value=e) for e in _examples(lang)],
        gr.update(label=t("typed_toggle", lang)),
        gr.update(placeholder=t("text_placeholder_native", lang)),
        gr.update(value=t("ask_button", lang)),
        gr.update(label=t("place_label", lang)),
        gr.update(placeholder=t("location_placeholder_native", lang)),
        gr.update(value=t("gps_button", lang)),
        gr.update(label=t("eyebrow_can_help", lang)),
        gr.update(value=_help_html(lang)),
        gr.update(label=t("diag", lang)),
        gr.update(label=t("lang_picker", lang), value=_detected_text(lang, detected_key)),
        gr.update(label=t("heard_label", lang)),
        gr.update(label=t("english_label", lang)),
        gr.update(label=t("intent_label", lang)),
        gr.update(label=t("trace_label", lang)),
        gr.update(value=_footer_html(lang)),
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
# Play the spoken answer again — one big button, instead of hunting for the
# little play control. The player draws its own waveform (there is no plain
# <audio> to drive), so this presses its button: once when it has finished
# (which restarts it), pause-then-play while it is still speaking.
_REPLAY_JS = """
() => {
  const box = document.querySelector(".ag-audio");
  const btn = box && box.querySelector("button.play-pause-button");
  if (!btn) { return; }
  const playing = (btn.getAttribute("aria-label") || "").toLowerCase().includes("pause");
  btn.click();
  if (playing) { setTimeout(() => btn.click(), 120); }
}
"""
# After a question is answered, bring the answer into view — on a phone it sits
# below the microphone.
_SCROLL_JS = """
() => { const el = document.querySelector(".ag-answer");
        if (el) { el.scrollIntoView({behavior: "smooth", block: "center"}); } }
"""


# ── UI builder ────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    lang = DEFAULT_LANG

    with gr.Blocks(title="Agri Assistant", fill_width=True) as demo:
        # Remembered so a language switch can re-render the last result's
        # readout, sources and "you asked" line in the new language.
        detected_state = gr.State(None)
        tools_state = gr.State(None)
        heard_state = gr.State(None)
        # The question waiting on a detail the farmer was asked for.
        pending_state = gr.State(None)

        # ── Top bar: brand + the four languages ──────────────────────────────
        with gr.Column(elem_classes=["ag-top"]):
            brand_html = gr.HTML(_brand_html(lang))
            lang_radio = gr.Radio(
                choices=LANG_CHOICES, value=lang, label=t("lang_picker", lang),
                show_label=False, container=False, elem_classes=["ag-lang"],
            )

        # ── Ask ──────────────────────────────────────────────────────────────
        hero_html = gr.HTML(_hero_html(lang))
        audio_input = gr.Audio(
            sources=["microphone"], type="filepath", show_label=False,
            editable=False, elem_classes=["ag-mic"], visible=VOICE_READY,
        )
        mic_cta = gr.HTML(f'<div class="ag-cta">{t("mic_cta", lang)}</div>',
                          visible=VOICE_READY)
        lite_note = gr.HTML(_note(t("lite_note", lang)), visible=not VOICE_READY)

        # ── Answer ───────────────────────────────────────────────────────────
        answer_section = gr.HTML(_section(t("eyebrow_response", lang)))
        answer_note = gr.HTML(_note(t("answer_note", lang)), visible=False)
        heard_html = gr.HTML("")
        answer_output = gr.Textbox(
            show_label=False, lines=7, max_lines=24, interactive=False,
            placeholder=t("answer_placeholder", lang), elem_classes=["ag-answer"],
        )
        audio_output = gr.Audio(label=t("audio_label", lang), autoplay=True,
                                interactive=False, elem_classes=["ag-audio"])
        replay_btn = gr.Button(t("replay_button", lang), size="lg",
                               elem_classes=["ag-replay"])
        tools_html_output = gr.HTML("")

        # ── Sample questions — tap one and it is asked ───────────────────────
        examples_section = gr.HTML(_section(t("examples_label", lang)))
        with gr.Column(elem_classes=["ag-examples"]):
            example_btns = [gr.Button(e, size="lg", elem_classes=["ag-example"])
                            for e in _examples(lang)]

        # ── Folded away: typing, location, help, diagnostics ─────────────────
        with gr.Accordion(t("typed_toggle", lang), open=not VOICE_READY,
                          elem_classes=["ag-fold"]) as typed_fold:
            text_input = gr.Textbox(placeholder=t("text_placeholder_native", lang),
                                    show_label=False, lines=2)
            submit_btn = gr.Button(t("ask_button", lang), variant="primary",
                                   size="lg", elem_classes=["ag-ask"])

        with gr.Accordion(t("place_label", lang), open=False,
                          elem_classes=["ag-fold"]) as place_fold:
            with gr.Row(equal_height=True, elem_classes=["ag-place"]):
                location_input = gr.Textbox(
                    placeholder=t("location_placeholder_native", lang),
                    show_label=False, scale=3,
                )
                gps_btn = gr.Button(t("gps_button", lang), size="lg", scale=2,
                                    elem_classes=["ag-gps"])

        with gr.Accordion(t("eyebrow_can_help", lang), open=False,
                          elem_classes=["ag-fold"]) as help_fold:
            help_html = gr.HTML(_help_html(lang))

        with gr.Accordion(t("diag", lang), open=False,
                          elem_classes=["ag-fold", "ag-diag"]) as diag_accordion:
            detected_lang_output = gr.Textbox(
                value=t("pending", lang), label=t("lang_picker", lang),
                interactive=False, lines=1, max_lines=1,
            )
            transcription_output = gr.Textbox(label=t("heard_label", lang), lines=2,
                                              interactive=False)
            english_output = gr.Textbox(label=t("english_label", lang), lines=2,
                                        interactive=False)
            intent_output = gr.Textbox(label=t("intent_label", lang), lines=7,
                                       interactive=False)
            trace_output = gr.Textbox(label=t("trace_label", lang), lines=14,
                                      interactive=False, visible=DEV_MODE)
            gr.HTML(f'<div class="ag-mode">{_mode_info()}</div>')

        footer_html = gr.HTML(_footer_html(lang))

        # ── Wiring ────────────────────────────────────────────────────────────
        # Order must match _localized().
        localized = [
            brand_html, hero_html, mic_cta, lite_note, answer_section, answer_note,
            heard_html, answer_output, audio_output, replay_btn, tools_html_output,
            examples_section, *example_btns, typed_fold, text_input, submit_btn,
            place_fold, location_input, gps_btn, help_fold, help_html,
            diag_accordion, detected_lang_output, transcription_output,
            english_output, intent_output, trace_output, footer_html,
        ]
        # Order must match _outputs().
        results = [
            detected_lang_output, transcription_output, english_output, answer_output,
            audio_output, intent_output, tools_html_output, trace_output, heard_html,
            detected_state, tools_state, pending_state, heard_state,
        ]

        # Voice-first: tapping stop sends the question — no extra button to find.
        # The recorder is then cleared, ready for the next question.
        audio_input.stop_recording(
            fn=_on_voice,
            inputs=[audio_input, location_input, lang_radio, pending_state],
            outputs=results + [audio_input],
        ).then(fn=None, js=_SCROLL_JS)
        submit_btn.click(
            fn=_on_ask,
            inputs=[audio_input, text_input, location_input, lang_radio, pending_state],
            outputs=results,
        ).then(fn=None, js=_SCROLL_JS)
        text_input.submit(
            fn=_on_ask,
            inputs=[audio_input, text_input, location_input, lang_radio, pending_state],
            outputs=results,
        ).then(fn=None, js=_SCROLL_JS)
        for btn in example_btns:
            btn.click(fn=_on_example, inputs=[btn, location_input, lang_radio],
                      outputs=results).then(fn=None, js=_SCROLL_JS)

        replay_btn.click(fn=None, inputs=None, outputs=None, js=_REPLAY_JS)
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
