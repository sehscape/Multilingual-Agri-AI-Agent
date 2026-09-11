"""Live check with your real Groq key — voice questions in all four languages.

For each language, a farmer's question is spoken with gTTS, sent through the
real app pipeline (Groq Whisper → understanding → LangChain agent → Groq
answer writer → gTTS), and checked: the right tools ran, and the answer is in
the right script. Also checks a follow-up ("40 days") and an off-topic question.

Needs GROQ_API_KEY in .env (or the environment) and internet. It uses a few
of your free daily Groq requests (~25). The key is never printed.

    python scripts/test_groq_live.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("LITE_MODE", "true")      # the Render build
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console  # noqa: E402
enable_utf8_console()

import logging  # noqa: E402
logging.disable(logging.WARNING)

from app.config import GROQ_API_KEY, USE_GROQ  # noqa: E402

CASES = [  # (language, spoken question, tools that must run, script of the answer)
    ("hi", "मेरी गेहूं की फसल 40 दिन की है, कौन सी खाद डालूं?", {"crop"}, "Devanagari"),
    ("pa", "ਕੀ ਕੱਲ੍ਹ ਲੁਧਿਆਣਾ ਵਿੱਚ ਮੀਂਹ ਪਵੇਗਾ?", {"weather"}, "Gurmukhi"),
    ("mr", "पीएम किसान योजनेसाठी कोणती कागदपत्रे लागतात?", {"scheme"}, "Devanagari"),
    ("en", "My cotton plants have white insects under the leaves. What should I do?",
     {"crop"}, "Latin"),
]


def script_of(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    deva = sum(0x0900 <= ord(c) <= 0x097F for c in letters) / max(len(letters), 1)
    guru = sum(0x0A00 <= ord(c) <= 0x0A7F for c in letters) / max(len(letters), 1)
    return "Gurmukhi" if guru > .5 else "Devanagari" if deva > .5 else "Latin"


def speak(text: str, lang: str) -> str:
    from gtts import gTTS
    path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
    gTTS(text=text, lang=lang).save(path)
    return path


def main() -> int:
    if not (GROQ_API_KEY and USE_GROQ):
        print("[SKIP] No GROQ_API_KEY found. Add it to .env (see DEPLOY.md) and run again.")
        return 0
    from app.ui import gradio_app as ga
    failures = 0

    def report(label, ok, r=None):
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if r is not None:
            print(f"        heard : {r['transcription']}")
            print(f"        answer: {r['answer'][:220].replace(chr(10), ' ')}")
            if not ok:
                print("        trace :\n          " + r["trace"].replace("\n", "\n          "))

    for lang, question, tools, script in CASES:
        r = ga._pipeline(speak(question, lang), "", "", lang)
        used = {n for n, on in zip(("crop", "weather", "scheme"), r["tools_flags"] or ()) if on}
        ok = tools <= used and script_of(r["answer"]) == script and bool(r["audio"])
        report(f"[{lang}] voice → {'+'.join(sorted(tools))} → {script} answer + voice", ok, r)

    r = ga._pipeline(speak("गेहूं में खाद कब डालें?", "hi"), "", "", "hi")
    asked = bool(r["pending"]) and "age" in r["pending"]["missing"]
    report("[hi] crop age missing → asked back", asked, r)
    if asked:
        r = ga._pipeline(speak("चालीस दिन", "hi"), "", "", "hi", r["pending"])
        report("[hi] reply 'चालीस दिन' → full answer",
               r["tools_flags"] and r["tools_flags"][0] and script_of(r["answer"]) == "Devanagari", r)

    r = ga._pipeline(None, "ਅੱਜ ਕ੍ਰਿਕਟ ਮੈਚ ਕੌਣ ਜਿੱਤੇਗਾ?", "", "pa")
    report("[pa] off-topic → told what it can help with, in Punjabi",
           r["tools_flags"] is None and script_of(r["answer"]) == "Gurmukhi", r)

    print("\n" + ("ALL PASSED" if not failures else f"{failures} FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
