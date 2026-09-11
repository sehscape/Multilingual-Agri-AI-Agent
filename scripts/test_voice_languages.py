"""Voice + 4-language test — the farmer's journey on the Render (LITE) host.

Simulates the free Render deploy WITH a Groq key: heavy ML libraries are
blocked, LITE_MODE is on, and Groq is replaced by a scripted fake (no network,
no real key). Text-to-speech is replaced by a recorder, so the test checks
exactly what the farmer would hear, and in which language.

  1. Groq client: model fallback, rate limits, JSON retry, key never logged.
  2. Speech-to-text: silence, noise and prompt echoes are treated as "no speech".
  3. Understanding: LLM JSON parsing, rule fallback, follow-up merging.
  4. The page on a Groq-enabled LITE host: microphone on, auto-send on stop.
  5. Full journeys in Hindi, Punjabi, Marathi, English — voice and typed:
     the answer and the spoken reply are in the chosen language, and every
     incomplete / unclear / unsupported question is answered with a question
     or notice in that language.
  6. Failure paths: Groq busy, Groq down, wrong-script replies.

Run (from project root, venv active):
    python scripts/test_voice_languages.py
Weather lookups use the real Open-Meteo API (needs internet), like the other tests.
"""
import builtins
import json
import logging
import os
import re
import sys
import tempfile
import wave
from pathlib import Path

_BLOCKED = {"torch", "torchaudio", "transformers", "sentence_transformers",
            "faiss", "whisper", "accelerate"}
_failures = 0
_total = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures, _total
    _total += 1
    _failures += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail and not ok else ""))


def section(title: str) -> None:
    print("\n" + "=" * 68 + f"\n{title}\n" + "=" * 68)


def _simulate_render_with_groq() -> None:
    os.environ["LITE_MODE"] = "true"
    os.environ["GROQ_API_KEY"] = "test-key-not-real"
    os.environ["USE_GROQ"] = "true"
    os.environ["STT_BACKEND"] = "auto"
    real_import = builtins.__import__

    def no_heavy_import(name, *args, **kwargs):
        if name.split(".")[0] in _BLOCKED:
            raise ImportError(f"{name} is not installed on the LITE host (blocked by test)")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = no_heavy_import


def script_of(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "none"
    deva = sum(0x0900 <= ord(c) <= 0x097F for c in letters) / len(letters)
    guru = sum(0x0A00 <= ord(c) <= 0x0A7F for c in letters) / len(letters)
    return "Gurmukhi" if guru > .5 else "Devanagari" if deva > .5 else "Latin"


# ══════════════════════════════════════════════════════════════════════════════
# Fakes
# ══════════════════════════════════════════════════════════════════════════════

W = {  # scripted understanding for the farmer's exact words
    # complete questions
    "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?": dict(
        english="My wheat is 40 days old, which fertilizer should I apply?", crop="wheat",
        crop_words="गेहूं", crop_age_days=40, wants_crop_advice=True, advice_topic="fertilizer"),
    "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?": dict(
        english="Will it rain in Ludhiana tomorrow?", location="Ludhiana",
        place_words="ਲੁਧਿਆਣਾ", wants_weather=True),
    "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?": dict(
        english="Which documents are needed for the PM Kisan scheme?", wants_scheme=True,
        scheme="pm_kisan"),
    "My wheat is 40 days old, will it rain in Pune, any scheme for irrigation?": dict(
        english="My wheat is 40 days old, will it rain in Pune, any scheme for irrigation?",
        crop="wheat", crop_age_days=40, location="Pune", wants_weather=True,
        wants_scheme=True, scheme="other", wants_crop_advice=True, advice_topic="irrigation"),
    # incomplete / unclear / unsupported
    "गेहूं में खाद कब डालें?": dict(
        english="When should I apply fertilizer to wheat?", crop="wheat", crop_words="गेहूं",
        wants_crop_advice=True, advice_topic="fertilizer"),
    "कल बारिश होगी क्या?": dict(english="Will it rain tomorrow?", wants_weather=True),
    "ਮੇਰੇ ਗੰਨੇ ਨੂੰ ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?": dict(
        english="Which fertilizer should I give my sugarcane?", crop="other:sugarcane",
        crop_words="ਗੰਨੇ", wants_crop_advice=True, advice_topic="fertilizer"),
    "माझ्या गव्हाला 300 दिवस झाले, पाणी कधी द्यावे?": dict(
        english="My wheat is 300 days old, when should I water it?", crop="wheat",
        crop_words="गव्हाला", crop_age_days=300, wants_crop_advice=True,
        advice_topic="irrigation"),
    "मेरी फसल की पत्तियां पीली हो रही हैं": dict(
        english="The leaves of my crop are turning yellow", wants_crop_advice=True,
        advice_topic="pest_disease"),
    "क्रिकेट का स्कोर क्या है?": dict(english="What is the cricket score?", topic="off_topic"),
    "नमस्ते": dict(english="Hello", topic="greeting"),
    "Will it rain in Xyzabcville tomorrow?": dict(
        english="Will it rain in Xyzabcville tomorrow?", location="Xyzabcville",
        place_words="Xyzabcville", wants_weather=True),
    "गेहूं में खाद कब डालें और पुणे में बारिश होगी क्या?": dict(
        english="When should I apply fertilizer to wheat, and will it rain in Pune?",
        crop="wheat", location="Pune", wants_crop_advice=True, advice_topic="fertilizer",
        wants_weather=True),
    "सोलर पंप योजना क्या है?": dict(
        english="What is the solar pump scheme?", wants_scheme=True, scheme="other"),
}
# follow-ups: (earlier English question, farmer's reply) → merged question
FOLLOW = {
    ("When should I apply fertilizer to wheat?", "40 दिन"): dict(
        english="My wheat is 40 days old, when should I apply fertilizer?", crop="wheat",
        crop_age_days=40, wants_crop_advice=True, advice_topic="fertilizer"),
    ("Will it rain tomorrow?", "नाशिक"): dict(
        english="Will it rain in Nashik tomorrow?", location="Nashik", place_words="नाशिक",
        wants_weather=True),
}
REPLIES = {
    "Hindi": "आपके सवाल का जवाब यह है। 🌾 **ध्यान दें:** सलाह मानिए।",
    "Punjabi": "ਤੁਹਾਡੇ ਸਵਾਲ ਦਾ ਜਵਾਬ ਇਹ ਹੈ। ਸਲਾਹ ਮੰਨੋ।",
    "Marathi": "तुमच्या प्रश्नाचे उत्तर हे आहे. सल्ला पाळा.",
    "English": "Here is the answer to your question. Follow the advice.",
}


class FakeGroq:
    stt_model = "whisper-large-v3"

    def __init__(self):
        self.transcripts = {}
        self.writer = "ok"          # ok | fail | wrong_script
        self.understander = "ok"    # ok | fail
        self.stt = "ok"             # ok | rate_limit | down
        self.last_model = "fake/gpt-oss-120b"
        self.facts = ""
        self.calls = []

    def transcribe(self, path, language=None, prompt=None):
        from app.models.groq_client import GroqError
        self.calls.append(("stt", language))
        if self.stt == "rate_limit":
            raise GroqError("rate_limit", "Groq 429 (whisper-large-v3): slow down")
        if self.stt == "down":
            raise GroqError("server", "Groq 503 (whisper-large-v3): unavailable")
        text = self.transcripts.get(Path(path).name, "")
        return {"text": text, "duration": 3.0,
                "no_speech_prob": 0.02 if text else 0.95, "avg_logprob": -0.3}

    def chat(self, messages, json_mode=False, max_tokens=800, temperature=0.2):
        from app.models.groq_client import GroqError
        user = messages[-1]["content"] if json_mode else messages[1]["content"]
        if json_mode:
            self.calls.append(("understand",))
            if self.understander == "fail":
                raise GroqError("server", "Groq 503: over capacity")
            words = re.search(r'Farmer\'s words: "(.*)"', user).group(1)
            earlier = re.search(r'Earlier the farmer asked: "(.*?)"\.', user)
            fields = (FOLLOW.get((earlier.group(1), words)) if earlier else None) or W.get(words)
            base = dict(english=words, topic="unclear", crop=None, crop_words=None,
                        crop_age_days=None, location=None, place_words=None,
                        saved_location=None, wants_weather=False, wants_scheme=False,
                        scheme=None, wants_crop_advice=False, advice_topic=None)
            if fields:
                base.update(topic="farming")
                base.update(fields)
            saved = re.search(r"Saved location: (.*)", user).group(1).strip()
            base["saved_location"] = None if saved == "none" else saved
            return "```json\n" + json.dumps(base, ensure_ascii=False) + "\n```"
        self.calls.append(("write",))
        if self.writer == "fail":
            raise GroqError("rate_limit", "Groq 429: too many tokens")
        self.facts = user
        lang = re.search(r"Write the reply in (\w+)", user).group(1)
        if self.writer == "wrong_script":
            return "आपके सवाल का जवाब यह है।"  # Devanagari, whatever was asked
        return REPLIES[lang]


class FakeTTS:
    def __init__(self):
        self.said = []

    def generate(self, text, language):
        self.said.append((text, language))
        return f"/tmp/fake-{len(self.said)}.mp3"


class FakeResponse:
    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = json.dumps(self._body)

    def json(self):
        return self._body


class FakeSession:
    """Plays back scripted HTTP responses, recording each request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, headers=None, timeout=None, **kwargs):
        self.requests.append({"url": url, "headers": headers, **kwargs})
        return self.responses.pop(0)


def _ok_chat(text):
    return FakeResponse(200, {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]})


def make_wav(folder: str, name: str) -> str:
    path = os.path.join(folder, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# Tests
# ══════════════════════════════════════════════════════════════════════════════

def test_groq_client():
    section("1. Groq client")
    from app.models.groq_client import GroqClient, GroqError

    c = GroqClient(api_key="sk-secret-123", models=["m1", "m2", "m3"])
    c._session = FakeSession([
        FakeResponse(404, {"error": {"message": "The model `m1` does not exist",
                                     "code": "model_not_found"}}),
        FakeResponse(429, {"error": {"message": "Rate limit reached"}}, {"retry-after": "30"}),
        _ok_chat("namaste"),
    ])
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record.getMessage())
    logging.getLogger("app.models.groq_client").addHandler(handler)
    logging.disable(logging.NOTSET)
    out = c.chat([{"role": "user", "content": "hi"}])
    logging.disable(logging.WARNING)
    check("unavailable model skipped, rate-limited model skipped, next answers",
          out == "namaste" and c.last_model == "m3", f"{out!r} {c.last_model}")
    check("unavailable model remembered", "m1" in c._dead and "m2" not in c._dead)
    check("key sent only as a Bearer header",
          c._session.requests[0]["headers"]["Authorization"] == "Bearer sk-secret-123")
    check("key never written to the log", not any("sk-secret" in r for r in records),
          str(records))
    from app.models.groq_client import _reasoning_params
    check("gpt-oss asked for short, hidden reasoning",
          _reasoning_params("openai/gpt-oss-120b")
          == {"reasoning_effort": "low", "include_reasoning": False})

    c = GroqClient(api_key="k", models=["m1"])
    c._session = FakeSession([
        FakeResponse(400, {"error": {"message": "json_validate_failed", "code": "json_validate_failed"}}),
        _ok_chat('{"a": 1}'),
    ])
    check("JSON-mode failure retried without strict JSON",
          c.chat([{"role": "user", "content": "x"}], json_mode=True) == '{"a": 1}'
          and "response_format" not in c._session.requests[1]["json"])

    c = GroqClient(api_key="bad", models=["m1", "m2"])
    c._session = FakeSession([FakeResponse(401, {"error": {"message": "Invalid API Key"}})])
    try:
        c.chat([{"role": "user", "content": "x"}])
        check("bad key raises auth error", False)
    except GroqError as e:
        check("bad key raises auth error (no pointless retries)",
              e.kind == "auth" and len(c._session.requests) == 1)

    check("no key → auth error before any request",
          _raises_kind(lambda: GroqClient(api_key="").chat([{"role": "user", "content": "x"}]),
                       "auth"))

    with tempfile.TemporaryDirectory() as d:
        wav = make_wav(d, "q.wav")
        c = GroqClient(api_key="k")
        c._session = FakeSession([FakeResponse(200, {
            "text": " मेरी गेहूं 40 दिन की है", "duration": 2.5,
            "segments": [{"start": 0, "end": 2.5, "no_speech_prob": 0.01, "avg_logprob": -0.2}]})])
        r = c.transcribe(wav, language="hi", prompt="किसान")
        req = c._session.requests[0]
        check("transcription: text, language and prompt sent; verbose_json parsed",
              r["text"] == "मेरी गेहूं 40 दिन की है" and req["data"]["language"] == "hi"
              and req["data"]["response_format"] == "verbose_json" and r["no_speech_prob"] < .1)


def _raises_kind(fn, kind):
    from app.models.groq_client import GroqError
    try:
        fn()
    except GroqError as e:
        return e.kind == kind
    return False


def test_stt_silence():
    section("2. Speech-to-text: silence and echoes")
    from app.models.stt import _GROQ_STT_PROMPTS, _is_silence
    check("empty transcript = no speech", _is_silence("", 0.1, None))
    check("'धन्यवाद' on a quiet clip = no speech", _is_silence("धन्यवाद", 0.5, None))
    check("high no-speech probability = no speech", _is_silence("कुछ", 0.9, None))
    check("Whisper repeating its priming sentence = no speech",
          _is_silence(_GROQ_STT_PROMPTS["hi"], 0.3, _GROQ_STT_PROMPTS["hi"]))
    check("a real short reply is kept ('40 दिन')", not _is_silence("40 दिन", 0.05, _GROQ_STT_PROMPTS["hi"]))
    check("a real question is kept",
          not _is_silence("मेरी गेहूं 40 दिन की है, क्या खाद डालूं?", 0.03, _GROQ_STT_PROMPTS["hi"]))


def test_understanding():
    section("3. Understanding")
    from app.agents.understanding import (Understanding, _parse_llm_json, merge_followup,
                                          understand_with_rules)

    u = _parse_llm_json('```json\n{"english": "Paddy care", "topic": "farming", "crop": "paddy", '
                        '"crop_age_days": "35", "wants_crop_advice": "true"}\n```', "x")
    check("LLM JSON: fences, string numbers/booleans, 'paddy' → rice",
          u.crop == "rice" and u.crop_age_days == 35 and u.wants_crop_advice
          and u.advice_topic == "general")
    u = _parse_llm_json('{"english": "x", "topic": "farming", "crop": "sugarcane", '
                        '"wants_crop_advice": true}', "x")
    check("LLM JSON: crop outside the knowledge base → other:sugarcane", u.other_crop == "sugarcane")
    u = _parse_llm_json('{"english": "x", "topic": "weird", "wants_weather": true}', "x")
    check("LLM JSON: a request for weather is 'farming' whatever the topic says",
          u.topic == "farming" and u.wants_weather)

    r = understand_with_rules("नाशिकमध्ये उद्या पाऊस येईल का?")
    check("rules: 'पाऊस' (rain) is not read as 'ऊस' (sugarcane)",
          r.crop is None and r.wants_weather and r.location == "Nashik", r.summary())
    r = understand_with_rules("Will it rain in Shirur tomorrow?")
    check("rules: any English place after 'in' is found", r.location == "Shirur", r.summary())
    r = understand_with_rules("ਮੇਰੇ ਗੰਨੇ ਨੂੰ ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?")
    check("rules: Punjabi sugarcane recognised as unsupported", r.other_crop == "sugarcane",
          r.summary())
    r = understand_with_rules("Hello")
    check("rules: greeting", r.topic == "greeting")

    prev = understand_with_rules("When should I apply fertilizer to wheat?")
    merged = merge_followup(prev, understand_with_rules("40 days"), ["age"], "40 days")
    check("rules follow-up: '40 days' completes the wheat question",
          merged.crop == "wheat" and merged.crop_age_days == 40 and merged.wants_crop_advice)
    prev = understand_with_rules("Will it rain tomorrow?")
    merged = merge_followup(prev, understand_with_rules("Shirur"), ["location"], "Shirur")
    check("rules follow-up: a bare place name completes the weather question",
          merged.location == "Shirur" and merged.wants_weather)
    fresh = understand_with_rules("How do I apply for PM-Kisan?")
    check("rules follow-up: a new question is not merged",
          merge_followup(prev, fresh, ["location"], "How do I apply for PM-Kisan?") is fresh)
    check("understanding survives the gr.State round trip",
          Understanding.from_dict(merged.to_dict()) == merged)


def test_page():
    section("4. The page on a Groq-enabled LITE host")
    from app.config import LITE_MODE, REGIONAL_READY, STT_ENGINE, VOICE_READY
    from app.ui import gradio_app as ga
    check("LITE host with a key: voice via Groq, answers in 4 languages",
          LITE_MODE and STT_ENGINE == "groq" and VOICE_READY and REGIONAL_READY)
    cfg = ga.build_ui().get_config_file()
    comps = {c["id"]: c for c in cfg["components"]}
    mic = next(c for c in comps.values() if "ag-mic" in (c.get("props", {}).get("elem_classes") or []))
    check("microphone shown", mic["props"].get("visible") is not False)
    lite = next((c for c in comps.values() if c.get("type") == "html"
                 and "lightweight demo" in str(c["props"].get("value", ""))), None)
    check("'typed English only' note hidden", lite is None or lite["props"].get("visible") is False)
    triggers = {(tgt[0], tgt[1]) for d in cfg["dependencies"] for tgt in d["targets"]}
    check("tapping stop sends the question", (mic["id"], "stop_recording") in triggers)
    radio = next(c for c in comps.values() if "ag-lang" in (c.get("props", {}).get("elem_classes") or []))
    dep = next(d for d in cfg["dependencies"]
               if radio["id"] in [tgt[0] for tgt in d["targets"]] and d.get("outputs"))
    check("language switch re-renders every localized component",
          len(dep["outputs"]) == len(ga._localized("hi")))
    check("examples follow the page language",
          ga._examples("pa")[0].startswith("ਮੇਰੀ") and ga._examples("en")[0].startswith("My"))
    check("GPS button labelled in Marathi", ga._localized("mr")[28]["value"] == "📍 माझे ठिकाण वापरा")
    check("'you asked' line escapes the farmer's words",
          "&lt;script&gt;" in ga._heard_html("<script>x</script>", "en"))


def run_journeys():
    section("5. Journeys — voice and typed, all four languages")
    from app.models.groq_client import set_groq_client
    from app.tools import weather_tool
    from app.ui import gradio_app as ga
    from app.ui.i18n import SPOKEN_EXAMPLES, t

    fake, tts = FakeGroq(), FakeTTS()
    set_groq_client(fake)
    ga._tts = tts
    real_geocode = weather_tool._geocode
    weather_tool._geocode = lambda place: None if place == "Xyzabcville" else real_geocode(place)
    tmp = tempfile.mkdtemp()

    def voice(lang, words, pending=None, location=""):
        name = f"q{len(fake.transcripts)}.wav"
        fake.transcripts[name] = words
        return ga._pipeline(make_wav(tmp, name), "", location, lang, pending)

    def typed(lang, words, pending=None, location=""):
        return ga._pipeline(None, words, location, lang, pending)

    def spoken():
        return tts.said[-1] if tts.said else ("", "")

    # ── Complete questions, one per language ─────────────────────────────────
    r = voice("hi", "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?")
    text, lang = spoken()
    check("Hindi voice: answer written in Hindi", r["answer"].startswith(REPLIES["Hindi"][:10]))
    check("Hindi voice: spoken in Hindi, markdown and emoji removed",
          lang == "hi" and "**" not in text and "🌾" not in text, f"{lang} {text!r}")
    check("Hindi voice: crop stage facts reached the writer",
          "CROP KNOWLEDGE" in fake.facts and "Tillering" in fake.facts)
    check("Hindi voice: heard in Hindi, readout says Hindi · voice",
          ("stt", "hi") in fake.calls and r["detected_key"] == ("hi", "voice"))
    check("Hindi voice: nothing left pending", r["pending"] is None)

    r = voice("pa", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?")
    check("Punjabi voice: live weather for Ludhiana, answer + voice in Punjabi",
          "LIVE WEATHER" in fake.facts and "Ludhiana" in fake.facts
          and script_of(r["answer"]) == "Gurmukhi" and spoken()[1] == "pa", r["trace"][-400:])

    r = typed("mr", "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?")
    check("Marathi typed: PM-KISAN documents found, answer + voice in Marathi",
          "Pm Kisan" in fake.facts and "Aadhaar" in fake.facts
          and r["answer"].startswith(REPLIES["Marathi"][:10]) and spoken()[1] == "mr")

    r = typed("en", "My wheat is 40 days old, will it rain in Pune, any scheme for irrigation?")
    check("English typed: crop + weather + scheme tools all used",
          r["tools_flags"] == (True, True, True) and spoken()[1] == "en", str(r["tools_flags"]))

    r = typed("hi", "My wheat is 40 days old, which fertilizer should I apply?")
    check("typed in English on the Hindi page → answered in Hindi",
          script_of(r["answer"]) == "Devanagari" and spoken()[1] == "hi")

    # ── Incomplete questions → asked back, then completed ────────────────────
    r = voice("hi", "गेहूं में खाद कब डालें?")
    check("missing crop age → asked (in Hindi, spoken)",
          r["answer"] == t("ask_age", "hi", crop="गेहूं") and spoken()[1] == "hi"
          and r["pending"]["missing"] == ["age"], r["answer"])
    r = voice("hi", "40 दिन", pending=r["pending"])
    check("reply '40 दिन' completes it → full Hindi answer",
          r["answer"].startswith(REPLIES["Hindi"][:10]) and "Tillering" in fake.facts
          and r["pending"] is None, r["answer"])

    r = voice("hi", "कल बारिश होगी क्या?")
    check("weather without a place → 'which village or town?'",
          r["answer"] == t("ask_location", "hi") and r["pending"]["missing"] == ["location"])
    r = voice("hi", "नाशिक", pending=r["pending"])
    check("reply 'नाशिक' completes it → Nashik weather in Hindi",
          "Nashik" in fake.facts and script_of(r["answer"]) == "Devanagari", r["trace"][-300:])
    r = voice("hi", "कल बारिश होगी क्या?", location="Pune")
    check("saved location is used when the question names no place",
          "LIVE WEATHER" in fake.facts and "Pune" in fake.facts and r["pending"] is None)

    r = voice("pa", "ਮੇਰੇ ਗੰਨੇ ਨੂੰ ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?")
    check("unsupported crop → told in Punjabi, with the crops it knows",
          r["answer"] == t("ask_unsupported_crop", "pa", crop="ਗੰਨੇ") and spoken()[1] == "pa",
          r["answer"])
    r = typed("mr", "माझ्या गव्हाला 300 दिवस झाले, पाणी कधी द्यावे?")
    check("impossible age (wheat, 300 days) → asked to check, in Marathi",
          r["answer"] == t("ask_age_check", "mr", crop="गहू", days=300, total=120), r["answer"])
    r = voice("hi", "मेरी फसल की पत्तियां पीली हो रही हैं")
    check("crop problem without a crop name → 'which crop?'",
          r["answer"] == t("ask_crop", "hi") and r["pending"]["missing"] == ["crop"])
    r = voice("hi", "क्रिकेट का स्कोर क्या है?")
    check("off-topic → what I can help with, plus a Hindi example",
          r["answer"] == t("ask_offtopic", "hi", example=SPOKEN_EXAMPLES["hi"][0]))
    r = voice("hi", "नमस्ते")
    check("greeting → greeted back with an example",
          r["answer"] == t("msg_greeting", "hi", example=SPOKEN_EXAMPLES["hi"][0]))
    r = typed("en", "Will it rain in Xyzabcville tomorrow?")
    check("place the map can't find → asked for a nearby town",
          r["answer"] == t("ask_place_not_found", "en", place="Xyzabcville")
          and r["pending"]["missing"] == ["location"], r["answer"])
    r = typed("hi", "सोलर पंप योजना क्या है?")
    check("scheme not in the documents → the 4 schemes it knows",
          r["answer"] == t("ask_scheme_unknown", "hi"), r["answer"][:120])
    r = voice("hi", "गेहूं में खाद कब डालें और पुणे में बारिश होगी क्या?")
    check("part answerable: weather answered, age asked for in a note",
          "LIVE WEATHER" in fake.facts
          and r["answer"].endswith(t("note_age_for_exact", "hi", crop="गेहूं"))
          and t("note_age_for_exact", "hi", crop="गेहूं") in spoken()[0]
          and r["pending"]["missing"] == ["age"], r["answer"])

    # ── Voice problems ───────────────────────────────────────────────────────
    r = voice("mr", "")
    check("silence → 'I could not hear you' in Marathi, spoken",
          r["answer"] == t("err_no_speech", "mr") and spoken()[1] == "mr")
    r = ga._pipeline(None, "", "", "pa")
    check("nothing asked → prompt in Punjabi", r["answer"] == t("err_no_input", "pa"))
    import gradio as gr
    out = ga._on_voice(None, "", "hi", None)
    check("stop event before the recording arrives changes nothing (Ask still works)",
          len(out) == 14 and all(o == gr.skip() for o in out))
    fake.transcripts["stop.wav"] = "नमस्ते"
    out = ga._on_voice(make_wav(tmp, "stop.wav"), "", "hi", None)
    check("stop event answers, then clears the recorder for the next question",
          len(out) == 14 and out[-1] is None
          and out[3] == t("msg_greeting", "hi", example=SPOKEN_EXAMPLES["hi"][0]))

    section("6. Failure paths")
    fake.stt = "rate_limit"
    r = voice("hi", "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?")
    check("speech service busy → 'wait a minute' in Hindi", r["answer"] == t("err_busy", "hi"))
    fake.stt = "down"
    r = voice("pa", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?")
    check("speech service down → 'try again later' in Punjabi", r["answer"] == t("err_service", "pa"))
    fake.stt = "ok"

    fake.understander = "fail"
    r = voice("hi", "मेरी गेहूं 40 दिन की है, क्या खाद डालूं?")
    check("LLM understanding down → keyword rules still route the Hindi question",
          "CROP KNOWLEDGE" in fake.facts and script_of(r["answer"]) == "Devanagari",
          r["trace"][-300:])
    fake.understander = "ok"

    fake.writer = "fail"
    r = voice("pa", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?")
    note = t("note_english_fallback", "pa", language="ਪੰਜਾਬੀ")
    check("answer writer down → English answer on screen, Punjabi notice spoken",
          r["answer"].startswith(note) and "Weather for Ludhiana" in r["answer"]
          and spoken()[1] == "pa" and note in spoken()[0],
          f"{r['answer'][:160]!r} {spoken()!r}")
    fake.writer = "wrong_script"
    r = voice("pa", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?")
    check("reply in the wrong script twice → never shown as Punjabi; notice instead",
          r["answer"].startswith(note), r["answer"][:120])
    fake.writer = "ok"

    weather_tool._geocode = real_geocode
    heavy = [m for m in _BLOCKED if m in sys.modules]
    check(f"ran with heavy ML libs unavailable (loaded: {heavy or 'none'})", not heavy)


if __name__ == "__main__":
    _simulate_render_with_groq()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.utils.logging import enable_utf8_console
    enable_utf8_console()
    logging.disable(logging.WARNING)

    test_groq_client()
    test_stt_silence()
    test_understanding()
    test_page()
    run_journeys()

    print("\n" + "=" * 68)
    print(f"Result: {_total - _failures}/{_total} checks passed — "
          f"{'ALL PASSED' if _failures == 0 else f'{_failures} FAILED'}")
    sys.exit(0 if _failures == 0 else 1)
