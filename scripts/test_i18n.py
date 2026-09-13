"""Language test — the 4-language UI and spoken questions in each language.

  1. Every UI string exists, non-empty, in English/Hindi/Punjabi/Marathi, with
     the same {placeholders} in each.
  2. The picker shows exactly the 4 required labels.
  3. Switching language re-renders every language-dependent component.
  4. Messages and errors appear in the chosen language.
  5. Hindi/Punjabi/Marathi farm questions route to the right tools from the
     native words alone (as a Whisper transcript would deliver them) — including
     real garbled Whisper output.
  6. Voice (default on, needs internet + the whisper-small model): a spoken
     question in each language is synthesised with gTTS, transcribed by Whisper
     in that language, and routed to the right tools. Skip with --no-voice.

Usage (from project root, venv active):
    python scripts/test_i18n.py            # everything (~2 min)
    python scripts/test_i18n.py --no-voice # skip the Whisper section
"""
import os
import re
import string
import sys
import tempfile
from pathlib import Path

# This checks the build without a Groq key (local Whisper, English answers).
# The Groq build — answers in every language — is scripts/test_voice_languages.py.
os.environ["GROQ_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

import logging
logging.disable(logging.WARNING)

from app.agents.intent import extract_intent
from app.agents.state import AgentState
from app.models.llm import StubLLM
from app.ui.i18n import LANG_CHOICES, LANG_CODES, LANG_NAMES, SPOKEN_EXAMPLES, STRINGS, t

_failures = 0
_total = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures, _total
    _total += 1
    _failures += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail and not ok else ""))


def fields(s: str) -> set:
    return {f for _, f, _, _ in string.Formatter().parse(s) if f}


def route(native: str, english: str = "") -> AgentState:
    """Run the intent router on a native transcript (+ optional English)."""
    state = AgentState(source_language="hi", original_text=native, english_text=english)
    return extract_intent(state, StubLLM())


# (native question, expected needs, expected crop, expected location)
ROUTING_CASES = [
    ("मेरी गेहूं 40 दिन की है, क्या खाद डालूं?", {"crop"}, "wheat", None),
    ("पुणे में कल बारिश होगी क्या? धान की सिंचाई करूं?", {"crop", "weather"}, "rice", "Pune"),
    ("PM किसान योजना के लिए कैसे आवेदन करें?", {"scheme"}, None, None),
    ("मेरे टमाटर की पत्तियां पीली हो रही हैं, क्या करूं?", {"crop"}, "tomato", None),
    ("ਮੇਰੀ ਕਣਕ 40 ਦਿਨ ਦੀ ਹੈ, ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?", {"crop"}, "wheat", None),
    ("ਲੁਧਿਆਣਾ ਵਿੱਚ ਕੱਲ੍ਹ ਮੀਂਹ ਪਵੇਗਾ ਕੀ?", {"weather"}, None, "Ludhiana"),
    ("ਕਿਸਾਨ ਕ੍ਰੈਡਿਟ ਕਾਰਡ ਲਈ ਕਿਵੇਂ ਅਪਲਾਈ ਕਰਨਾ ਹੈ?", {"scheme"}, None, None),
    ("ਮੇਰੇ ਝੋਨੇ ਵਿੱਚ ਕੀੜੇ ਲੱਗ ਗਏ ਹਨ।", {"crop"}, "rice", None),
    ("माझ्या कापसाला 40 दिवस झाले, कोणते खत द्यावे?", {"crop"}, "cotton", None),
    ("नाशिकमध्ये उद्या पाऊस येईल का?", {"weather"}, None, "Nashik"),
    ("पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?", {"scheme"}, None, None),
    ("माझ्या कांद्याची पाने पिवळी पडत आहेत.", {"crop"}, "onion", None),
]

# Real whisper-small output for gTTS clips — garbled, with weak English
# translations; routing must still succeed from the native words.
GARBLED_CASES = [
    ("अगर पूने में बारश होगी? मुझे संचाई करनी चाहीए?",
     "Should I think about the rain in Pune?", {"weather"}, "Pune"),
    ("नाशिक मदे उदेः पाउस्याल का?", "Nashi Kamade Udaya Poush Yail Ka", {"weather"}, "Nashik"),
    ("नाशिक मदे उदेः पावुस्याल का?", "Nashi Kamade Udaya Poush Yail Ka", {"weather"}, "Nashik"),
    ("मेरी कनक چाली दिन्दी है कि हरी काद पामा",
     "My wife is 40 days old. She is very hungry.", {"crop"}, None),
]

VOICE_CASES = [
    ("hi", "क्या कल पुणे में बारिश होगी? मुझे सिंचाई करनी चाहिए?", "weather_forecast"),
    ("mr", "नाशिकमध्ये उद्या पाऊस येईल का?", "weather_forecast"),
    ("pa", "ਮੇਰੀ ਕਣਕ ਚਾਲੀ ਦਿਨ ਦੀ ਹੈ, ਕਿਹੜੀ ਖਾਦ ਪਾਵਾਂ?", "crop_knowledge"),
    ("en", "Will it rain in Ludhiana tomorrow?", "weather_forecast"),
]


def needs(state: AgentState) -> set:
    return {n for n, on in (("crop", state.needs_crop_info), ("weather", state.needs_weather),
                            ("scheme", state.needs_scheme)) if on}


def main(voice: bool) -> None:
    print("=" * 64 + "\n1. Every string in all 4 languages\n" + "=" * 64)
    for key, entry in STRINGS.items():
        missing = [c for c in LANG_CODES if not entry.get(c, "").strip()]
        same_fields = all(fields(entry[c]) == fields(entry["en"]) for c in LANG_CODES if c in entry)
        if missing or not same_fields:
            check(f"string '{key}'", False, f"missing={missing} fields_match={same_fields}")
    check(f"all {len(STRINGS)} strings complete with matching placeholders",
          all(all(e.get(c, "").strip() for c in LANG_CODES) for e in STRINGS.values()))
    check("language names complete", all(set(LANG_NAMES[c]) == set(LANG_CODES) for c in LANG_CODES))
    check("spoken examples for every language", all(len(SPOKEN_EXAMPLES[c]) == 4 for c in LANG_CODES))

    print("\n" + "=" * 64 + "\n2. Language picker\n" + "=" * 64)
    labels = [label for label, _ in LANG_CHOICES]
    check("picker labels exactly as specified",
          labels == ["🇬🇧 English", "🇮🇳 Hindi", "ਪੰਜਾਬੀ Punjabi", "मराठी Marathi"], str(labels))

    print("\n" + "=" * 64 + "\n3. Switching language re-renders the page\n" + "=" * 64)
    from app.ui import gradio_app as ga
    cfg = ga.build_ui().get_config_file()
    radio = next(c for c in cfg["components"]
                 if "ag-lang" in (c.get("props", {}).get("elem_classes") or []))
    dep = next(d for d in cfg["dependencies"]
               if radio["id"] in [tgt[0] for tgt in d["targets"]] and d.get("outputs"))
    check("change handler updates as many components as _localized() returns",
          len(dep["outputs"]) == len(ga._localized("hi")),
          f"{len(dep['outputs'])} vs {len(ga._localized('hi'))}")
    button_texts = {lang: ga._localized(lang)[11]["value"] for lang in LANG_CODES}
    check("ask button differs per language", len(set(button_texts.values())) == 4, str(button_texts))

    print("\n" + "=" * 64 + "\n4. Messages in the chosen language\n" + "=" * 64)
    for lang in LANG_CODES:
        msg = ga._run_pipeline(None, "", "", lang)[3]
        check(f"no-question message [{lang}]", msg == t("err_no_input", lang), msg)
    msg = ga._run_pipeline(None, "मेरी गेहूं 40 दिन की है", "", "hi")[3]
    check("typed Hindi → Hindi 'please type in English'", msg == t("err_type_english", "hi"), msg)
    detected, *_rest = ga._run_pipeline(None, "My wheat is 40 days old, what fertilizer?", "", "mr")
    check("typed English in Marathi UI → Marathi readout",
          detected == f"{LANG_NAMES['mr']['en']} · {t('mode_typed', 'mr')}", detected)
    strip = ga._tools_strip("pa", (True, False, False))
    check("tool chips in Punjabi", t("tool_crop", "pa") in strip and t("chip_used", "pa") in strip)

    print("\n" + "=" * 64 + "\n5. Regional farm questions route from native words\n" + "=" * 64)
    for native, want, crop, loc in ROUTING_CASES:
        s = route(native)
        ok = needs(s) == want and s.crop == crop and s.location == loc
        check(f"{native[:34]}", ok,
              f"needs={sorted(needs(s))} crop={s.crop} loc={s.location}")
    for native, english, want, loc in GARBLED_CASES:
        s = route(native, english)
        ok = want <= needs(s) and (loc is None or s.location == loc)
        check(f"garbled Whisper: {native[:28]}", ok,
              f"needs={sorted(needs(s))} loc={s.location}")

    if voice:
        print("\n" + "=" * 64 + "\n6. Voice: speech in each language → Whisper → tools\n" + "=" * 64)
        try:
            from gtts import gTTS
            from app.agents.langchain_agent import LangChainAgent
            from app.config import WHISPER_MODEL_ID
            from app.models.stt import WhisperSTT
            stt = WhisperSTT(model_id=WHISPER_MODEL_ID, device="cpu")
        except Exception as exc:  # no Whisper on this host (e.g. LITE)
            print(f"[SKIP] voice section — {exc}")
            stt = None
        for lang, text, tool in VOICE_CASES if stt else []:
            mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            gTTS(text=text, lang=lang).save(mp3)
            r = stt.transcribe(mp3, language=lang, translate=lang != "en")
            state = AgentState(source_language=lang, original_text=r["text"],
                               english_text=r.get("english_text") or r["text"])
            state = LangChainAgent(StubLLM()).run(extract_intent(state, StubLLM()))
            called = {m.group(1) for line in state.trace
                      if (m := re.search(r"LangChain → (\w+)\(", line))}
            check(f"voice [{lang}] → {tool}", tool in called,
                  f"heard={r['text']!r} english={r.get('english_text')!r} called={sorted(called)}")

    print("\n" + "=" * 64)
    passed = _total - _failures
    print(f"Result: {passed}/{_total} checks passed — "
          f"{'ALL PASSED' if _failures == 0 else f'{_failures} FAILED'}")
    sys.exit(0 if _failures == 0 else 1)


if __name__ == "__main__":
    main(voice="--no-voice" not in sys.argv)
