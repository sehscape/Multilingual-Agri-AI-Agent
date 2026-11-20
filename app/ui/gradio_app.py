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
    DEFAULT_LANG, LANG_CHOICES, LANG_CODES, SPOKEN_EXAMPLES, lang_name, normalize_lang, t,
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
        if _MT_READY and not USE_GROQ:
            # Without Groq, every non-English answer goes through the local
            # translator: load it now rather than on the first question.
            translator = _get_translator()
            if hasattr(translator, "_load"):
                translator._load()
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
    from app.models.agri_glossary import HEADINGS
    labels = ["Important", "Source"]
    markers = [f"\n{label}:" for label in labels] + ["\nसूचना:"]
    markers += [f"\n{HEADINGS[label][code]}:" for label in labels for code in ("hi", "mr", "pa")]
    for marker in markers:
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


def _pipeline_iter(audio, text_query, location, lang, pending=None, speak=True):
    """Full pipeline: (typed text OR voice) → understanding → agent → answer → voice.

    Yields the reply twice: first the words, then the same reply with its
    recording attached. Making the speech takes a few seconds, and the farmer
    should not stare at an empty screen while it happens. With speak=False it
    stops after the words; result["speech"] holds (text, language) for the
    page to voice separately.

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
                  "tools_flags": None, "pending": keep, "heard": heard,
                  "speech": (message, lang), "cards": {}}
        yield result
        if not speak:
            return
        audio_path = _speak(message, lang, trace)
        trace.append(f"[Total] response time: {time.time()-started:.1f}s")
        yield {**result, "audio": audio_path, "trace": "\n".join(trace)}

    # ── 1. The farmer's words ────────────────────────────────────────────────
    english_hint = None
    if text_query:
        mode, q_lang, heard = "typed", _typed_language(text_query, lang), text_query
        if q_lang != "en" and not REGIONAL_READY:
            key = "err_type_english_lite" if LITE_MODE else "err_type_english"
            yield from reply_only(t(key, lang), keep=pending)
            return
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
    state = AgentState(source_language=q_lang, response_language=lang,
                       original_text=heard, english_text=u.english, location=plan.location)
    if q_lang != lang:
        trace.append(f"[Language] asked in {q_lang}, answering in the chosen {lang}")
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
              "pending": _pending(u, plan), "heard": heard,
              "speech": (speech, speech_lang), "cards": _cards(state, lang)}
    trace.append(f"[Answer] shown after {time.time()-started:.1f}s; now speaking")
    yield {**result, "trace": "\n".join(trace)}
    if not speak:
        return

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


# ── Conversation thread ───────────────────────────────────────────────────────
# The answer pane is a chat: the farmer on the right, the assistant on the
# left. While a reply is being worked out the assistant shows a typing bubble,
# so the page never piles loading spinners on top of the answer.

_TYPING = '<span class="ag-typing" aria-label="…"><i></i><i></i><i></i></span>'
_N_RESULTS = 13  # length of the `results` list in build_ui()


def _farmer_turn(words: str, mode: str) -> dict:
    """The farmer's bubble. Their words are escaped: shown, never rendered."""
    mic = "🎙 " if mode == "voice" else ""
    return {"role": "user", "content": mic + html.escape(words)}


def _assistant_turn(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _exchange(history, question, mode, lang, frames):
    """Stream one exchange into the thread.

    Yields (pipeline result, thread): first (None, question + typing bubble) at
    once, then one frame per pipeline step. A voice question shows as a mic
    bubble until Whisper has written down the words.
    """
    thread = list(history or [])
    if mode == "typed":
        thread.append(_farmer_turn(question, "typed"))
    elif mode == "voice":
        thread.append(_farmer_turn(t("voice_question", lang), "voice"))
    yield None, thread + [_assistant_turn(_TYPING)]
    for r in frames:
        turn = list(thread)
        if mode == "voice" and r["heard"]:
            turn[-1] = _farmer_turn(r["heard"], "voice")
        yield r, turn + [_assistant_turn(r["answer"])]


def _working(thread: list) -> tuple:
    """The frame shown while the assistant thinks: only the thread changes
    (and the last reply's recording is cleared so it stops playing). Nothing
    is left to speak until the new reply is in."""
    out = [gr.skip()] * _N_RESULTS
    out[3], out[4], out[12] = thread, None, None
    return tuple(out)


def _outputs(r: dict, thread: list, ticket: int) -> tuple:
    """Values for the page, in the order of the `results` list in build_ui()."""
    return (r["detected"], r["transcription"], r["english"], thread, r["audio"],
            r["intent"], r["tools_html"], r["trace"],
            r["detected_key"], r["tools_flags"], r["pending"], thread,
            (*r["speech"], ticket))


# A reply reaches the page in two events. The question handlers below stream
# the question, a typing bubble and then the words — and finish there, so the
# farmer can ask a follow-up straight away. _on_speak then makes the recording
# (a few seconds) from the `speech` the question handler left behind.
#
# Every question takes a ticket, numbered per browser session. A recording
# that finishes after a newer question was asked is dropped: it belongs to a
# reply the farmer has moved on from, and would play over the new one.
_latest_ticket: dict = {}


def _take_ticket(request) -> int:
    key = getattr(request, "session_hash", None)
    if len(_latest_ticket) > 5000:  # forget long-gone sessions
        _latest_ticket.clear()
    _latest_ticket[key] = _latest_ticket.get(key, 0) + 1
    return _latest_ticket[key]


def _on_ask(audio, text_query, location, lang_code, pending=None, history=None,
            request: gr.Request = None):
    """Ask button: the typed question if there is one, else the recording.
    The text box is emptied as the question goes out — only then, so a
    follow-up typed while the reply streams in is left alone."""
    ticket = _take_ticket(request)
    question = (text_query or "").strip()
    mode = "typed" if question else ("voice" if audio is not None else None)
    frames = _pipeline_iter(audio, question, location, lang_code, pending, speak=False)
    for r, thread in _exchange(history, question, mode, lang_code, frames):
        if r is None:
            yield _working(thread) + ("",)
        else:
            yield _outputs(r, thread, ticket) + (gr.skip(),)


def _on_voice(audio, location, lang_code, pending=None, history=None,
              request: gr.Request = None):
    """The farmer tapped stop — answer the recording straight away. If the
    recording hasn't reached the server, change nothing: the Ask button still
    sends it."""
    if audio is None:
        # Clear only the speech, so the follow-up voice step stays silent.
        yield tuple(gr.skip() for _ in range(_N_RESULTS - 1)) + (None, gr.skip())
        return
    ticket = _take_ticket(request)
    frames = _pipeline_iter(audio, "", location, lang_code, pending, speak=False)
    for r, thread in _exchange(history, "", "voice", lang_code, frames):
        if r is None:
            yield _working(thread) + (gr.skip(),)
        else:
            # The last value clears the recorder, ready for the next question.
            yield _outputs(r, thread, ticket) + (None,)


def _on_example(example, location, lang_code, history=None, request: gr.Request = None):
    """An example question was tapped — ask it as a fresh question."""
    ticket = _take_ticket(request)
    frames = _pipeline_iter(None, example, location, lang_code, None, speak=False)
    for r, thread in _exchange(history, example, "typed", lang_code, frames):
        yield _working(thread) if r is None else _outputs(r, thread, ticket)


def _on_speak(speech, trace_text, request: gr.Request = None):
    """The recording for the reply now on screen. Returns (audio path, trace)."""
    if not speech:
        return gr.skip(), gr.skip()
    text, lang, ticket = speech
    trace = (trace_text or "").splitlines()
    path = _speak(text, lang, trace)
    if _latest_ticket.get(getattr(request, "session_hash", None), ticket) != ticket:
        return gr.skip(), gr.skip()  # a newer question is already being answered
    return path, "\n".join(trace)


def _new_conversation(lang_code, request: gr.Request = None):
    """Start over: empty thread, nothing pending, tools back to standing by.
    Taking a ticket silences a recording still being made for the old thread."""
    _take_ticket(request)
    lang = normalize_lang(lang_code)
    return ([], [], None, None, None, _no_tools_html(lang), t("pending", lang), None, "")


def _detected_text(ui_lang: str, detected_key) -> str:
    """'Hindi · voice', written in the UI language — or the waiting message."""
    if not detected_key:
        return t("pending", ui_lang)
    q_lang, mode = detected_key
    return f"{lang_name(q_lang, ui_lang)} · {t('mode_' + mode, ui_lang)}"


# ══════════════════════════════════════════════════════════════════════════════
# Presentation layer
#
# Design language: farmer-first. Large type, plain words, numbered steps, one
# big microphone, and soft cards on a warm field-coloured canvas, with one
# accent (wheat gold). A full dark palette ships alongside — Gradio puts
# `dark` on <body> and follows the viewer's system setting, so every colour
# below is a token defined for both. Append `?__theme=dark` (or `light`) to
# the URL to pin one.
#
# Rule: never hardcode a colour in generated HTML — only token-backed classes,
# or it inverts badly in the other theme.
# ══════════════════════════════════════════════════════════════════════════════

_TOOL_SPECS = (  # (tool, label key, icon)
    ("crop", "tool_crop", "🌱"),
    ("weather", "tool_weather", "🌦"),
    ("scheme", "tool_scheme", "🏛"),
)


def _eyebrow(text: str, num: str = "") -> str:
    """A section heading: an optional step number in a circle, then the words."""
    index = f'<span class="ag-eyebrow-num">{num}</span>' if num else ""
    return (
        f'<div class="ag-eyebrow">{index}'
        f'<span class="ag-eyebrow-text">{text}</span>'
        f'<span class="ag-eyebrow-rule"></span></div>'
    )


def _note(text: str) -> str:
    return f'<div class="ag-field-note">{text}</div>'


def _tool_chip(label: str, active: bool, lang: str, icon: str = "") -> str:
    state = "on" if active else "off"
    note = t("chip_used" if active else "chip_idle", lang)
    return (
        f'<span class="ag-chip ag-chip--{state}">'
        f'<i class="ag-chip-icon">{icon}</i>'
        f'<span class="ag-chip-label">{label}</span>'
        f'<span class="ag-chip-note">{note}</span></span>'
    )


def _tools_strip(lang: str = DEFAULT_LANG, flags=None) -> str:
    """Status strip for the three knowledge sources. flags=None → standing by."""
    used = dict(zip(("crop", "weather", "scheme"), flags or (False, False, False)))
    chips = "".join(_tool_chip(t(key, lang), used[tool], lang, icon)
                    for tool, key, icon in _TOOL_SPECS)
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


def _cards(state, lang: str) -> dict:
    """The facts behind an answer as plain data, for the web app's cards:
    the forecast, the crop's growth stage, and the scheme documents used."""
    import re
    cards = {}
    weather = state.weather_data or {}
    if weather.get("raw"):
        from app.tools.weather_tool import forecast_card
        cards["weather"] = forecast_card(weather["raw"], weather.get("context", ""))
    if state.crop_data and state.crop and state.crop_stage_days is not None:
        from app.tools.crop_tool import stage_card
        crop = stage_card(state.crop, state.crop_stage_days, lang)
        if crop:
            cards["crop"] = crop
    if state.scheme_docs:
        names = re.findall(r"Source:\s*(.+?)\s*\(relevance", state.scheme_docs[0].get("context", ""))
        if names:
            from app.knowledge import scheme_title
            cards["schemes"] = list(dict.fromkeys(scheme_title(n) for n in names))
    return cards


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
        # Canvas — the same colours as --ag-bg in the CSS, edge to edge
        body_background_fill="#F5F3EC",
        body_background_fill_dark="#0B0C0D",
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
  --ag-bg:        #F5F3EC;
  --ag-surface:   #FFFFFF;
  --ag-sunk:      #F1EEE4;
  --ag-line:      #E4DFD2;
  --ag-line-2:    #CFC8B6;
  --ag-text:      #1C1D1A;
  --ag-dim:       #545953;
  --ag-faint:     #80857F;
  --ag-accent:    #8A6410;
  --ag-on-accent: #FFFFFF;
  --ag-accent-bg: rgba(138,100,16,.09);
  --ag-stop:      #B42318;
  --ag-shadow:    0 1px 2px rgba(28,29,26,.04), 0 10px 28px rgba(28,29,26,.06);
}
body.dark {
  --ag-bg:        #0B0C0D;
  --ag-surface:   #131518;
  --ag-sunk:      #181B1F;
  --ag-line:      #262A30;
  --ag-line-2:    #343A42;
  --ag-text:      #EDEFF0;
  --ag-dim:       #A6ADB3;
  --ag-faint:     #6F777E;
  --ag-accent:    #D9A441;
  --ag-on-accent: #0B0C0D;
  --ag-accent-bg: rgba(217,164,65,.12);
  --ag-stop:      #E5533F;
  --ag-shadow:    none;
}

/* ═══ Shell ═══ */
/* Gradio's page template paints <body> off prefers-color-scheme alone, which
   leaves a mismatched band below the app when the viewer pins a theme by hand
   (?__theme=…) against their OS setting. Repaint it from our own tokens. */
body { background: var(--ag-bg) !important; color: var(--ag-text); }

.gradio-container {
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding: 0 28px 56px !important;
  background: var(--ag-bg);
  color: var(--ag-text);
}
.gradio-container .prose :is(h1,h2,h3,h4) { color: var(--ag-text); }
footer { display: none !important; }
/* Gradio pads every HTML block; without it headings and cards line up with
   the input boxes and buttons around them. */
.gradio-container .html-container { padding: 0 !important; }

/* ═══ Top bar ═══ */
.ag-topbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 14px; flex-wrap: wrap;
  padding: 18px 0 16px;
  border-bottom: 1px solid var(--ag-line);
}
.ag-brand { display: flex; align-items: center; gap: 9px; }
.ag-brand-mark { display: inline-flex; width: 28px; height: 28px; flex: none; color: var(--ag-accent); }
.ag-brand-mark svg { width: 100%; height: 100%; }
/* Gradio gives every element inside an HTML block the text colour, so
   currentColor can't carry the accent down to the SVG — paint it directly. */
.ag-brand-mark svg g, .ag-brand-mark svg ellipse { fill: var(--ag-accent) !important; }
.ag-brand-mark svg path { fill: none !important; stroke: var(--ag-accent) !important; }
.ag-brand-name {
  font-size: 18px; font-weight: 700; letter-spacing: -.01em;
  color: var(--ag-text);
}
/* The top bar is a Gradio Row: stop its children stretching to equal widths */
.ag-topbar > * { flex: 0 1 auto !important; min-width: 0 !important; width: auto !important; }
.ag-topbar .block, .ag-topbar .form { padding: 0 !important; border: none !important;
  background: transparent !important; box-shadow: none !important; }

/* ═══ Language picker — big round buttons, each in its own script ═══ */
.ag-lang { background: transparent !important; }
.ag-lang .wrap { display: flex !important; flex-wrap: wrap; gap: 8px !important; }
.ag-lang label {
  display: inline-flex !important; align-items: center;
  margin: 0 !important;
  padding: 9px 16px !important;
  border: 1.5px solid var(--ag-line) !important;
  border-radius: 999px !important;
  background: var(--ag-surface) !important;
  box-shadow: none !important;
  font-size: 15px !important; font-weight: 500 !important;
  color: var(--ag-dim) !important;
  cursor: pointer;
  transition: border-color .16s ease, color .16s ease, background .16s ease;
}
.ag-lang label:hover { color: var(--ag-text) !important; border-color: var(--ag-line-2) !important; }
.ag-lang label.selected, .ag-lang label:has(input:checked) {
  border-color: var(--ag-accent) !important;
  background: var(--ag-accent-bg) !important;
  color: var(--ag-text) !important;
  font-weight: 700 !important;
}
/* Hide the radio dot but keep it focusable for keyboard users */
.ag-lang input[type="radio"] {
  position: absolute !important; opacity: 0 !important;
  width: 1px !important; height: 1px !important; margin: 0 !important;
}
.ag-lang label:has(input:focus-visible) { outline: 2px solid var(--ag-accent); outline-offset: 2px; }
.ag-lang label span { margin-left: 0 !important; }

/* ═══ Indic scripts ═══
   Tight negative tracking pulls Devanagari/Gurmukhi letters off their
   headline bar, and the scripts need more line height. The page carries
   lang="hi|mr|pa" once a language is picked. Gradio re-emits every rule
   behind a long `.gradio-container… .contain` prefix, which outranks a plain
   html[lang] selector; `:not(#ag-none)` adds ID-level weight so these win. */
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) :is(.ag-hero h1, .ag-brand-name) {
  letter-spacing: 0 !important;
}
html:is([lang="hi"], [lang="mr"], [lang="pa"]):not(#ag-none) .ag-hero h1 { line-height: 1.3; }

/* ═══ Hero ═══ */
.ag-hero { padding: 38px 0 22px; max-width: 760px; }
.ag-hero-eyebrow {
  display: inline-block;
  font-size: 13.5px; font-weight: 700;
  color: var(--ag-accent);
  background: var(--ag-accent-bg);
  padding: 5px 12px;
  border-radius: 999px;
  margin-bottom: 16px;
}
.ag-hero h1 {
  font-size: clamp(2.1rem, 4.6vw, 3.4rem);
  line-height: 1.06;
  letter-spacing: -.03em;
  font-weight: 700;
  margin: 0 0 14px;
  color: var(--ag-text);
}
.ag-hero h1 em { font-style: normal; color: var(--ag-accent); }
.ag-hero p {
  font-size: 18px;
  line-height: 1.6;
  color: var(--ag-dim);
  margin: 0;
  max-width: 56ch;
}

/* ═══ What I can help with — three cards ═══ */
.ag-cards {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin: 2px 0 26px;
}
.ag-card {
  background: var(--ag-surface);
  border: 1px solid var(--ag-line);
  border-radius: 16px;
  padding: 18px 18px 16px;
  box-shadow: var(--ag-shadow);
}
.ag-card-icon { font-size: 28px; line-height: 1; margin-bottom: 10px; }
.ag-card-title { font-size: 17px; font-weight: 700; color: var(--ag-text); margin-bottom: 4px; }
.ag-card-body { font-size: 14.5px; line-height: 1.55; color: var(--ag-dim); }

/* ═══ Section headings, with a step number in a circle ═══ */
.ag-eyebrow { display: flex; align-items: center; gap: 10px; margin: 4px 0 8px; }
.ag-eyebrow-num {
  width: 26px; height: 26px; flex: none;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--ag-accent); color: var(--ag-on-accent);
  font-size: 14px; font-weight: 700;
}
.ag-eyebrow-text { font-size: 17px; font-weight: 700; color: var(--ag-text); white-space: nowrap; }
.ag-eyebrow-rule { flex: 1; height: 1px; background: var(--ag-line); }

/* ═══ Console: the ask card and the answer card ═══ */
.ag-console { gap: 22px !important; align-items: stretch !important; }
.ag-panel {
  background: var(--ag-surface) !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 20px !important;
  padding: 22px 24px 26px !important;
  box-shadow: var(--ag-shadow);
  gap: 12px !important;
  min-width: 0 !important;
}
.ag-panel .block { padding: 0 !important; }
.ag-panel .gap { gap: 12px !important; }
/* Desktop: the ask card stays in view while a long conversation scrolls */
@media (min-width: 861px) {
  .ag-console { align-items: flex-start !important; }
  .ag-panel--ask { position: sticky; top: 16px; }
}
@media (max-width: 480px) {
  .ag-lang label { padding: 7px 12px !important; font-size: 14px !important; }
  .ag-hero h1 { font-size: 2.05rem; }
}
@media (max-width: 860px) {
  .ag-console { flex-direction: column !important; flex-wrap: nowrap !important; gap: 16px !important; }
  .ag-console > .ag-panel { width: 100% !important; flex: 1 1 auto !important; min-width: 0 !important; }
  .ag-panel { padding: 18px 16px 20px !important; border-radius: 18px !important; }
  .ag-hero { padding: 24px 0 16px; }
  .ag-hero p { font-size: 16.5px; }
  .ag-cards { grid-template-columns: 1fr; gap: 10px; margin: 16px 0 6px; }
  .ag-card { display: grid; grid-template-columns: 40px 1fr; column-gap: 10px; padding: 14px; }
  .ag-card-icon { grid-row: span 2; font-size: 26px; margin: 2px 0 0; }
  /* On a phone the microphone comes first; what-I-can-help-with follows the answer */
  .ag-help-block { order: 2; }
  .ag-diag { order: 3; }
  .ag-footer-block { order: 4; }
  .ag-examples { grid-template-columns: 1fr !important; }
  .ag-detected input, .ag-detected textarea { font-size: 16px !important; }
}
/* (The page gutters for phones live in _HEAD below: Gradio rewrites rules in
   media queries to sit inside .gradio-container, so they can't reach it.) */

/* ═══ Inputs ═══ */
.ag-panel textarea, .ag-panel input[type="text"] {
  font-size: 16px !important;
  line-height: 1.55 !important;
  padding: 13px 14px !important;
  border-radius: 12px !important;
  background: var(--ag-bg) !important;
  transition: border-color .16s ease;
}
.ag-field-note {
  font-size: 14px; line-height: 1.55;
  color: var(--ag-faint);
  margin: -2px 0 8px;
}

/* ═══ The microphone — one big button ═══ */
.ag-mic {
  background: var(--ag-accent-bg) !important;
  border: 2px dashed var(--ag-accent) !important;
  border-radius: 18px !important;
  padding: 14px !important;
}
.ag-mic .controls { flex-direction: column !important; align-items: stretch !important; gap: 8px !important; }
.ag-mic .controls .wrapper { width: 100%; justify-content: center !important; gap: 8px !important; }
.ag-mic :is(button.record-button, button.stop-button, button.stop-button-paused) {
  width: 100% !important;
  min-height: 62px !important;
  align-items: center !important; justify-content: center !important;
  border: none !important;
  border-radius: 999px !important;
  background: var(--ag-accent) !important;
  color: var(--ag-on-accent) !important;
  font-size: 0 !important;            /* Gradio's English label — the words come from ::after */
  box-shadow: 0 6px 18px rgba(138,100,16,.25);
  transition: transform .12s ease, filter .16s ease;
}
.ag-mic :is(button.record-button, button.stop-button, button.stop-button-paused):hover { filter: brightness(1.06); }
.ag-mic :is(button.record-button, button.stop-button, button.stop-button-paused):active { transform: scale(.98); }
.ag-mic :is(button.record-button, button.stop-button, button.stop-button-paused)::after {
  font-size: 18px; font-weight: 700; letter-spacing: .01em;
}
.ag-mic button.record-button::before {
  content: ""; width: 24px; height: 24px; margin-right: 10px; flex: none;
  border: none !important; border-radius: 0 !important;
  background: currentColor !important;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 15a3.5 3.5 0 0 0 3.5-3.5v-6a3.5 3.5 0 1 0-7 0v6A3.5 3.5 0 0 0 12 15zm6-3.5a1 1 0 1 1 2 0 8 8 0 0 1-7 7.94V21h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-1.56A8 8 0 0 1 4 11.5a1 1 0 1 1 2 0 6 6 0 0 0 12 0z'/%3E%3C/svg%3E") center / contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 15a3.5 3.5 0 0 0 3.5-3.5v-6a3.5 3.5 0 1 0-7 0v6A3.5 3.5 0 0 0 12 15zm6-3.5a1 1 0 1 1 2 0 8 8 0 0 1-7 7.94V21h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-1.56A8 8 0 0 1 4 11.5a1 1 0 1 1 2 0 6 6 0 0 0 12 0z'/%3E%3C/svg%3E") center / contain no-repeat;
}
/* Recording: the button turns red and breathes, so it's obvious it's listening */
.ag-mic :is(button.stop-button, button.stop-button-paused) {
  background: var(--ag-stop) !important; color: #FFFFFF !important;
  animation: ag-listening 1.6s ease-in-out infinite;
}
.ag-mic :is(button.stop-button, button.stop-button-paused)::before {
  content: ""; width: 16px; height: 16px; margin-right: 12px; flex: none;
  border: none !important; border-radius: 3px !important; background: currentColor !important;
}
@keyframes ag-listening {
  0%, 100% { box-shadow: 0 0 0 0 rgba(180,35,24,.35); }
  50%      { box-shadow: 0 0 0 10px rgba(180,35,24,0); }
}
@media (prefers-reduced-motion: reduce) { .ag-mic button { animation: none !important; } }
.ag-mic select.mic-select {
  align-self: center;
  max-width: 100%;
  font-size: 12.5px !important;
  color: var(--ag-faint) !important;
  background: transparent !important;
  border: none !important;
  text-align: center;
}

/* ═══ Location + 📍 on one line ═══ */
.ag-place { gap: 8px !important; align-items: stretch !important; flex-wrap: nowrap !important; }
.ag-place > * { min-width: 0 !important; }
button.ag-gps {
  white-space: nowrap !important;
  font-size: 14.5px !important;
  border-radius: 12px !important;
  padding: 0 14px !important;
}
/* Small phones: the 📍 button drops under the field instead of squeezing it */
@media (max-width: 480px) {
  .ag-place { flex-wrap: wrap !important; }
  .ag-place > * { flex: 1 1 100% !important; }
  button.ag-gps { padding: 12px 14px !important; }
}

/* ═══ Ask button ═══ */
.ag-ask button, button.ag-ask {
  width: 100%;
  margin-top: 4px;
  border-radius: 14px !important;
  font-size: 17px !important;
  font-weight: 700 !important;
  letter-spacing: .01em !important;
  padding: 16px 20px !important;
  transition: transform .12s ease, background .16s ease;
}
.ag-ask button:active, button.ag-ask:active { transform: scale(.99); }

/* ═══ Where the answer came from ═══ */
.ag-tools { margin: 0 0 2px; }
.ag-tools-caption { font-size: 14px; color: var(--ag-faint); margin-bottom: 8px; }
.ag-tools-row { display: flex; flex-wrap: wrap; gap: 8px; }
.ag-chip {
  display: inline-flex; align-items: center; gap: 7px;
  padding: 7px 13px;
  border: 1px solid var(--ag-line);
  border-radius: 999px;
  background: var(--ag-bg);
  font-size: 14px;
  line-height: 1.2;
  transition: border-color .2s ease, background .2s ease;
}
.ag-chip-icon { font-style: normal; font-size: 15px; filter: grayscale(1); opacity: .5; }
.ag-chip-label { color: var(--ag-faint); font-weight: 500; }
.ag-chip-note { display: none; }
.ag-chip--on { border-color: var(--ag-accent); background: var(--ag-accent-bg); }
.ag-chip--on .ag-chip-icon { filter: none; opacity: 1; }
.ag-chip--on .ag-chip-label { color: var(--ag-text); font-weight: 700; }
.ag-chip--on .ag-chip-note { display: inline; font-size: 12.5px; font-weight: 700; color: var(--ag-accent); }
.ag-chip--on .ag-chip-note::before { content: "✓ "; }

/* ═══ Conversation thread ═══ */
.ag-chat {
  background: var(--ag-bg) !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 16px !important;
}
.ag-chat .bubble-wrap { background: transparent !important; padding: 16px 16px 10px !important; }
/* Gradio's share / clear / copy-all strip: the page has its own "new
   conversation" button, and a clear here would leave the thread state behind. */
.ag-chat .top-panel { display: none !important; }
.ag-chat .placeholder-content, .ag-chat .placeholder {
  color: var(--ag-faint) !important; font-size: 16px;
}
/* Width is capped on the row: the bubble itself shrink-wraps its text, so a
   percentage on the bubble would squeeze a short reply like "40 days". */
.ag-chat .message-row { margin: 4px 0 !important; max-width: 88% !important; }
.ag-chat div.message.user, .ag-chat div.message.bot {
  border-radius: 16px !important;
  padding: 11px 15px !important;
  font-size: 16px !important;
  line-height: 1.65 !important;
  box-shadow: none !important;
  max-width: none !important;
}
.ag-chat div.message.user {
  background: var(--ag-accent-bg) !important;
  border: 1px solid var(--ag-accent) !important;
  border-bottom-right-radius: 4px !important;
  color: var(--ag-text) !important;
}
.ag-chat div.message.bot {
  background: var(--ag-surface) !important;
  border: 1px solid var(--ag-line) !important;
  border-bottom-left-radius: 4px !important;
  color: var(--ag-text) !important;
}
.ag-chat .message :is(p, li) { color: var(--ag-text) !important; }
.ag-chat .message p { margin: 0 0 .55em !important; }
.ag-chat .message p:last-child { margin-bottom: 0 !important; }
.ag-chat .message :is(ol, ul) { margin: .3em 0 .55em !important; padding-left: 1.3em !important; }
/* Copy is useful on advice, not on the farmer's own words or a typing bubble */
.ag-chat .message-buttons-right,
.ag-chat .message-row:has(.ag-typing) + .message-buttons-left { display: none !important; }
.ag-chat .message-buttons-left { opacity: .55; transition: opacity .16s ease; }
.ag-chat .message-buttons-left:hover { opacity: 1; }

/* Typing bubble while the reply is worked out */
.ag-typing { display: inline-flex; gap: 5px; align-items: center; height: 1.2em; padding: 0 2px; }
.ag-typing i {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--ag-accent);
  opacity: .35;
  animation: ag-typing 1.2s infinite ease-in-out;
}
.ag-typing i:nth-child(2) { animation-delay: .15s; }
.ag-typing i:nth-child(3) { animation-delay: .3s; }
@keyframes ag-typing {
  0%, 60%, 100% { opacity: .3; transform: translateY(0); }
  30%           { opacity: 1;  transform: translateY(-3px); }
}
@media (prefers-reduced-motion: reduce) { .ag-typing i { animation: none; opacity: .7; } }

/* ═══ The spoken answer ═══ */
.ag-audio { margin-top: 4px !important; }
/* The waveform is drawn at a fixed number of pixels per second, so a long
   reply would otherwise widen the whole page on a phone. Neither the player
   nor the thread may decide the page width — they fit the column. */
.ag-audio, .ag-chat { contain: inline-size; min-width: 0 !important; max-width: 100%; }
.ag-audio .waveform-container, .ag-audio #waveform { overflow-x: hidden !important; }
button.ag-new-chat {
  align-self: flex-end !important;
  width: auto !important; min-width: 0 !important;
  padding: 8px 16px !important;
  font-size: 14px !important;
  border-radius: 999px !important;
  color: var(--ag-dim) !important;
}
button.ag-new-chat:hover { color: var(--ag-text) !important; border-color: var(--ag-line-2) !important; }

/* ═══ Sample questions — tappable cards ═══ */
.ag-panel--answer .ag-eyebrow { margin-top: 10px; }
.ag-examples {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px !important;
}
button.ag-example {
  justify-content: flex-start !important;
  align-items: flex-start !important;
  text-align: left !important;
  font-size: 15px !important;
  font-weight: 500 !important;
  line-height: 1.45 !important;
  min-height: 62px;
  padding: 13px 14px 13px 46px !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 14px !important;
  background: var(--ag-bg) !important;
  color: var(--ag-text) !important;
  white-space: normal !important;
  height: auto !important;
  position: relative;
  transition: border-color .16s ease, transform .12s ease;
}
button.ag-example::before { content: "🌾"; position: absolute; left: 14px; top: 12px; font-size: 20px; line-height: 1.2; }
button.ag-example:nth-of-type(2)::before { content: "🌦"; }
button.ag-example:nth-of-type(3)::before { content: "🏛"; }
button.ag-example:nth-of-type(4)::before { content: "🍂"; }  /* leaves turning yellow */
button.ag-example:hover { border-color: var(--ag-accent) !important; transform: translateY(-1px); }

/* ═══ How this answer was made ═══ */
.ag-diag {
  margin-top: 24px !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 16px !important;
  background: var(--ag-surface) !important;
  padding: 0 18px !important;
}
.ag-diag .label-wrap {
  padding: 16px 0 !important;
  font-size: 15px !important; font-weight: 600 !important;
  color: var(--ag-dim) !important;
}
.ag-diag .label-wrap:hover { color: var(--ag-text) !important; }
.ag-diag textarea {
  font-family: var(--font-mono) !important;
  font-size: 12.5px !important;
  line-height: 1.65 !important;
  background: var(--ag-sunk) !important;
  border: 1px solid var(--ag-line) !important;
  border-radius: 10px !important;
  color: var(--ag-dim) !important;
}

/* Question-language readout (inside the drawer). Gradio wraps the field in
   label.container.show_textbox_border, and that wrapper — not the input —
   draws the box: strip every layer back to plain text. */
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
.ag-detected input, .ag-detected textarea {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  padding: 0 !important;
  font-size: 17px !important;
  font-weight: 700 !important;
  color: var(--ag-accent) !important;
  resize: none !important;
  cursor: default;
  text-overflow: ellipsis;
}

/* ═══ Footer ═══ */
.ag-footer { margin-top: 22px; }
.ag-footer-note {
  font-size: 14.5px; line-height: 1.6;
  color: var(--ag-dim);
  background: var(--ag-accent-bg);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.ag-footer-row {
  display: flex; justify-content: space-between; gap: 10px 16px; flex-wrap: wrap;
  padding-top: 14px;
  border-top: 1px solid var(--ag-line);
  font-size: 13.5px;
  color: var(--ag-faint);
}
.ag-mode { font-family: var(--font-mono); font-size: 11.5px; color: var(--ag-faint); word-break: break-word; }
"""

# Rules that must reach Gradio's outer wrapper on phones. Gradio only keeps a
# `.gradio-container …`-prefixed copy of media-query rules from `css`, which
# can never match the container itself — so these go into <head> untouched.
# Without them Gradio's own 32px gutters leave a phone ~270px of its 390.
_HEAD = """
<style>
@media (max-width: 860px) {
  html body .gradio-container { padding: 0 16px 56px !important; }
  html body .gradio-container > .main { padding-left: 0 !important; padding-right: 0 !important; }
}
</style>
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
    """What the assistant can help with, as three cards — sets expectations
    before the farmer asks. Each message reads "🌾 Title — details"."""
    cards = []
    for key in ("help_crop", "help_weather", "help_scheme"):
        head, _, body = t(key, lang).partition(" — ")
        icon, _, title = head.partition(" ")
        body = body[:1].upper() + body[1:]  # "fertilizer, …" → "Fertilizer, …"
        cards.append(f'<div class="ag-card"><div class="ag-card-icon">{icon}</div>'
                     f'<div class="ag-card-title">{title}</div>'
                     f'<div class="ag-card-body">{body}</div></div>')
    return f'<div class="ag-cards">{"".join(cards)}</div>'


# ── Localised fragments ───────────────────────────────────────────────────────

def _mode_info() -> str:
    """Technical build line in the footer (kept in English — it's diagnostic)."""
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


# A wheat ear: the brand mark, drawn in the accent colour (the span sets the
# colour; the SVG paints with currentColor).
_WHEAT_SVG = (
    '<span class="ag-brand-mark"><svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M12 22V9" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'
    '<g fill="currentColor">'
    '<ellipse cx="12" cy="4.6" rx="1.9" ry="3"/>'
    '<ellipse cx="8.9" cy="9" rx="1.8" ry="3" transform="rotate(-35 8.9 9)"/>'
    '<ellipse cx="15.1" cy="9" rx="1.8" ry="3" transform="rotate(35 15.1 9)"/>'
    '<ellipse cx="8.9" cy="14" rx="1.8" ry="3" transform="rotate(-35 8.9 14)"/>'
    '<ellipse cx="15.1" cy="14" rx="1.8" ry="3" transform="rotate(35 15.1 14)"/>'
    '</g></svg></span>'
)


def _brand_html(lang: str) -> str:
    return (f'<div class="ag-brand">{_WHEAT_SVG}'
            f'<span class="ag-brand-name">{t("brand", lang)}</span></div>')


def _hero_body_key() -> str:
    if VOICE_READY and REGIONAL_READY:
        return "hero_body_voice"
    return "hero_body_full" if VOICE_READY else "hero_body_lite"


def _hero_html(lang: str) -> str:
    return (f'<div class="ag-hero">'
            f'<div class="ag-hero-eyebrow">{t("hero_eyebrow", lang)}</div>'
            f'<h1>{t("hero_title", lang)}</h1><p>{t(_hero_body_key(), lang)}</p></div>')


def _footer_html(lang: str) -> str:
    """The KVK reminder for the farmer; the build line for whoever deploys it."""
    return (f'<div class="ag-footer">'
            f'<div class="ag-footer-note">ⓘ {t("kvk_note", lang)}</div>'
            f'<div class="ag-footer-row"><span>{t("footer_left", lang)}</span>'
            f'<span class="ag-mode">{_mode_info()}</span></div></div>')


def _mic_note(lang: str) -> str:
    return _note(t("mic_note_auto", lang, language=lang_name(lang, lang)))


def _mic_css() -> str:
    """Labels for the big microphone button, in the page's language.

    Gradio's recorder writes "Record" / "Stop" in English, and its buttons
    can't be relabelled from Python — so the words come from CSS, keyed on the
    lang attribute the page carries (see _SAVE_LANG_JS), and are generated
    from the same messages as the rest of the screen."""
    def quoted(text: str) -> str:
        return '"' + text.replace('"', r'\"') + '"'
    rules = []
    for code in LANG_CODES:
        page = ":root" if code == DEFAULT_LANG else f'html[lang="{code}"]'
        rules.append(f"{page} .ag-mic button.record-button::after "
                     f"{{ content: {quoted(t('mic_tap', code))}; }}")
        rules.append(f"{page} .ag-mic :is(button.stop-button, button.stop-button-paused)::after "
                     f"{{ content: {quoted(t('mic_stop', code))}; }}")
    return "\n".join(rules)


_CSS += "\n/* ═══ Microphone labels, one per language (generated) ═══ */\n" + _mic_css() + "\n"


def _localized(lang, detected_key=None, tools_flags=None) -> list:
    """An update for every language-dependent component, in the same order as
    the `localized` list in build_ui(). Runs whenever the language changes."""
    lang = normalize_lang(lang)
    regional = REGIONAL_READY
    return [
        gr.update(value=_brand_html(lang)),
        gr.update(value=_hero_html(lang)),
        gr.update(value=_eyebrow(t("eyebrow_speak", lang), "1")),
        gr.update(value=_mic_note(lang)),
        gr.update(value=_eyebrow(t("eyebrow_or_type_any" if regional else "eyebrow_or_type",
                                   lang), "2")),
        gr.update(value=_eyebrow(t("eyebrow_question", lang), "1")),
        gr.update(value=_note(t("lite_note", lang))),
        gr.update(placeholder=t("text_placeholder_native" if regional else "text_placeholder",
                                lang)),
        gr.update(value=_eyebrow(t("eyebrow_location", lang), "3" if VOICE_READY else "2")),
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
        gr.update(value=t("new_chat", lang)),
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
# Keep the newest turn in view. Gradio only follows the thread when the reader
# is already near the bottom, and a long answer can push them past that — so
# watch the thread and scroll whenever a bubble arrives or grows.
_FOLLOW_THREAD_JS = """
() => {
  const chat = document.querySelector(".ag-chat");
  if (!chat || chat.dataset.follow) { return; }
  chat.dataset.follow = "1";
  let queued = false;
  new MutationObserver(() => {
    if (queued) { return; }
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      // Which box scrolls depends on the layout: the bubble list, or the block.
      for (const box of [chat, chat.querySelector(".bubble-wrap")]) {
        if (box) { box.scrollTop = box.scrollHeight; }
      }
    });
  }).observe(chat, {childList: true, subtree: true, characterData: true});
}
"""
# Narrow screens stack the panels, so scroll the conversation into view.
_SHOW_THREAD_JS = """
() => {
  if (window.innerWidth > 860) { return; }
  const thread = document.querySelector(".ag-panel--answer");
  if (thread) { setTimeout(() => thread.scrollIntoView({behavior: "smooth", block: "start"}), 60); }
}
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

    with gr.Blocks(title="Agri Assistant · Multilingual Agri AI Agent", fill_width=True) as demo:
        # Remembered so a language switch can re-render the last result's
        # language readout, tool chips and "you asked" line in the new language.
        detected_state = gr.State(None)
        tools_state = gr.State(None)
        # The question waiting on a detail the farmer was asked for.
        pending_state = gr.State(None)
        # The conversation so far, as {"role", "content"} turns.
        chat_state = gr.State([])
        # (text, language) of the latest reply, for the voice step to read out.
        speech_state = gr.State(None)

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

        # ── Hero + what it can help with ──────────────────────────────────────
        hero_html = gr.HTML(_hero_html(lang))
        help_eyebrow = gr.HTML(_eyebrow(t("eyebrow_can_help", lang)), visible=False)
        help_html = gr.HTML(_help_html(lang), elem_classes=["ag-help-block"])

        # ── Console ───────────────────────────────────────────────────────────
        with gr.Row(equal_height=False, elem_classes=["ag-console"]):

            # ── LEFT: the ask ────────────────────────────────────────────────
            with gr.Column(scale=5, min_width=300,
                           elem_classes=["ag-panel", "ag-panel--ask"]):
                # Voice — whenever a speech-to-text engine is available.
                speak_eyebrow = gr.HTML(_eyebrow(t("eyebrow_speak", lang), "1"),
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
                               lang), "2"),
                    visible=VOICE_READY)
                # Typed-only build (LITE without a Groq key)
                question_eyebrow = gr.HTML(_eyebrow(t("eyebrow_question", lang), "1"),
                                           visible=not VOICE_READY)
                lite_note = gr.HTML(_note(t("lite_note", lang)), visible=not VOICE_READY)

                text_input = gr.Textbox(
                    placeholder=t("text_placeholder_native" if regional
                                  else "text_placeholder", lang),
                    show_label=False,
                    lines=3,
                )

                location_eyebrow = gr.HTML(
                    _eyebrow(t("eyebrow_location", lang), "3" if VOICE_READY else "2"))
                location_note = gr.HTML(_note(t("location_note_voice" if VOICE_READY
                                                else "location_note", lang)))
                with gr.Row(equal_height=True, elem_classes=["ag-place"]):
                    location_input = gr.Textbox(
                        placeholder=t("location_placeholder_native" if regional
                                      else "location_placeholder", lang),
                        show_label=False,
                        max_lines=1,
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

            # ── RIGHT: the answer ────────────────────────────────────────────
            with gr.Column(scale=7, min_width=340,
                           elem_classes=["ag-panel", "ag-panel--answer"]):

                response_eyebrow = gr.HTML(_eyebrow(t("eyebrow_response", lang)))
                answer_note = gr.HTML(_note(t("answer_note", lang)), visible=False)

                tools_html_output = gr.HTML(_no_tools_html(lang))

                chatbot = gr.Chatbot(
                    value=[],
                    show_label=False,
                    layout="bubble",
                    height=None,
                    min_height=340,
                    max_height=560,
                    autoscroll=True,
                    feedback_options=None,
                    placeholder=t("answer_placeholder", lang),
                    elem_classes=["ag-chat"],
                )

                audio_output = gr.Audio(
                    label=t("audio_label", lang),
                    autoplay=True,
                    interactive=False,
                    elem_classes=["ag-audio"],
                )
                new_chat_btn = gr.Button(t("new_chat", lang), size="sm",
                                         elem_classes=["ag-new-chat"])

                # Sample questions — tapping one asks it.
                try_eyebrow = gr.HTML(_eyebrow(t("eyebrow_try", lang)))
                with gr.Column(elem_classes=["ag-examples"]):
                    example_btns = [gr.Button(e, size="sm", elem_classes=["ag-example"])
                                    for e in _examples(lang)]

        # ── How the answer was made (for the curious, and for debugging) ──────
        with gr.Accordion(t("diag", lang), open=False,
                          elem_classes=["ag-diag"]) as diag_accordion:
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
        footer_html = gr.HTML(_footer_html(lang), elem_classes=["ag-footer-block"])

        # ── Wiring ────────────────────────────────────────────────────────────
        # Order must match _localized().
        localized = [
            brand_html, hero_html, speak_eyebrow, mic_note, or_type_eyebrow,
            question_eyebrow, lite_note, text_input, location_eyebrow, location_note,
            location_input, submit_btn, detected_eyebrow, detected_lang_output,
            try_eyebrow, response_eyebrow, answer_note, tools_html_output,
            chatbot, audio_output, help_eyebrow, help_html, diag_accordion,
            transcription_output, english_output, intent_output, trace_output,
            footer_html, gps_btn, new_chat_btn, *example_btns,
        ]
        # Order must match _outputs().
        results = [
            detected_lang_output, transcription_output, english_output, chatbot,
            audio_output, intent_output, tools_html_output, trace_output,
            detected_state, tools_state, pending_state, chat_state, speech_state,
        ]

        # Each way of asking: (trigger, handler, inputs, extra outputs). The
        # thread shows its own typing bubble, so Gradio's per-component loading
        # overlays are switched off.
        ask_inputs = [audio_input, text_input, location_input, lang_radio, pending_state,
                      chat_state]
        routes = [
            (submit_btn.click, _on_ask, ask_inputs, [text_input]),
            (text_input.submit, _on_ask, ask_inputs, [text_input]),
            # Voice-first: tapping stop sends the question — no extra button to
            # find. The recorder is then cleared, ready for the next question.
            (audio_input.stop_recording, _on_voice,
             [audio_input, location_input, lang_radio, pending_state, chat_state],
             [audio_input]),
            *[(btn.click, _on_example, [btn, location_input, lang_radio, chat_state], [])
              for btn in example_btns],
        ]
        for trigger, handler, inputs, extra in routes:
            # always_last: a question asked while a reply is still streaming is
            # answered next, instead of being dropped.
            asked = trigger(fn=handler, inputs=inputs, outputs=results + extra,
                            show_progress="hidden", trigger_mode="always_last")
            asked.then(fn=_on_speak, inputs=[speech_state, trace_output],
                       outputs=[audio_output, trace_output], show_progress="hidden")
            # On a phone the thread sits below the question panel: bring it
            # into view, so the reply isn't missed.
            trigger(fn=None, js=_SHOW_THREAD_JS)

        new_chat_btn.click(
            fn=_new_conversation,
            inputs=lang_radio,
            outputs=[chatbot, chat_state, pending_state, detected_state, tools_state,
                     tools_html_output, detected_lang_output, audio_output, text_input],
            show_progress="hidden",
        )

        gps_btn.click(fn=None, inputs=location_input, outputs=location_input, js=_GPS_JS)
        location_input.change(fn=None, inputs=location_input, js=_SAVE_PLACE_JS)

        lang_radio.change(
            fn=_localized,
            inputs=[lang_radio, detected_state, tools_state],
            outputs=localized,
        )
        # Tag the page with the language (the CSS relaxes the letterspacing that
        # would break Devanagari / Gurmukhi) and remember it on this phone.
        lang_radio.change(fn=None, inputs=lang_radio, js=_SAVE_LANG_JS)
        demo.load(fn=None, inputs=None, outputs=[lang_radio, location_input], js=_RESTORE_JS)
        demo.load(fn=None, js=_FOLLOW_THREAD_JS)

    return demo
