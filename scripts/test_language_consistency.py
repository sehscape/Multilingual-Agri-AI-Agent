"""Language consistency test — the chosen language wins, without a Groq key.

Runs the real local build (no Groq): rule-based understanding, the LangChain
agent, and the NLLB translator for answers. Text-to-speech is replaced by a
recorder, so the test checks what the farmer would read AND hear.

  1. Translator: glossary stages and headings, number ranges kept intact.
  2. Hindi / Marathi / English chosen → the answer is in that language.
  3. Asked in another language than the chosen one → still answered in the
     chosen language (English→Hindi, Hindi→English, Marathi→Hindi).
  4. The language holds across a follow-up (ask-back "how many days?" → "40").
  5. The spoken reply uses the chosen language.

Run (from project root, venv active):
    python scripts/test_language_consistency.py
Needs internet for live weather; downloads NLLB (~2.5 GB) on the first run.
"""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["GROQ_API_KEY"] = ""
os.environ["USE_STUB_TRANSLATION"] = "false"
os.environ["TRANSLATION_ENGINE"] = "nllb"
os.environ["TTS_ENGINE"] = "stub"

from app.utils.logging import enable_utf8_console

enable_utf8_console()
logging.disable(logging.WARNING)

_failures = 0
_total = 0

_DEVANAGARI = (0x0900, 0x097F)


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures, _total
    _total += 1
    _failures += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail[:300]})" if detail and not ok else ""))


def section(title: str) -> None:
    print("\n" + "=" * 68 + f"\n{title}\n" + "=" * 68)


def devanagari_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(_DEVANAGARI[0] <= ord(ch) <= _DEVANAGARI[1] for ch in letters) / len(letters)


def is_lang(text: str, lang: str) -> bool:
    share = devanagari_share(text)
    return share > 0.6 if lang in ("hi", "mr") else share < 0.05


def main() -> int:
    import app.ui.gradio_app as ga
    from app.models.translation import NLLBTranslator, _plan_line

    spoken: list[tuple[str, str]] = []

    class RecorderTTS:
        def generate(self, text, language):
            spoken.append((language, text))
            return None

    ga._tts = RecorderTTS()

    section("1. Translator guards")
    pieces = _plan_line("Your Wheat crop is currently in the Tillering (days 26–50) stage.", "hi")
    check("stage sentence comes from the glossary, not the model",
          pieces == [("fixed", "आपकी गेहूं की फसल अभी कल्ले निकलना (26–50 दिन) की अवस्था में है।")],
          str(pieces))
    pieces = _plan_line("1. Irrigation: Maintain 3–5 cm standing water continuously.", "mr")
    check("heading fixed, range spelled out before translation",
          pieces[1] == ("fixed", "पाणी देणे: ") and "3 to 5" in pieces[2][1], str(pieces))
    out = NLLBTranslator().translate_from_english("Maintain 3–5 cm standing water continuously.", "hi")
    check("'3–5 cm' survives translation as 3 … 5, never '35'", "35" not in out and "3" in out and "5" in out, out)

    def ask(text, lang, pending=None):
        spoken.clear()
        r = ga._pipeline(None, text, "Nashik", lang, pending)
        return r

    section("2. Chosen language → answer language")
    for lang, question in (("hi", "My wheat is 40 days old, which fertiliser should I apply?"),
                           ("mr", "My wheat is 40 days old, which fertiliser should I apply?"),
                           ("en", "My wheat is 40 days old, which fertiliser should I apply?")):
        r = ask(question, lang)
        check(f"[{lang}] answer written in {lang}", is_lang(r["answer"], lang), r["answer"])
        check(f"[{lang}] reply spoken in {lang}",
              bool(spoken) and spoken[-1][0] == lang and is_lang(spoken[-1][1], lang), str(spoken))

    section("3. Question in another language → still the chosen language")
    r = ask("मेरी गेहूं 40 दिन की है, कौन सी खाद डालूं?", "en")
    check("Hindi question, English chosen → English answer", is_lang(r["answer"], "en"), r["answer"])
    check("…crop tool still used", bool(r["tools_flags"] and r["tools_flags"][0]), str(r["tools_flags"]))
    r = ask("माझा गहू 40 दिवसांचा आहे, कोणते खत द्यावे?", "hi")
    check("Marathi question, Hindi chosen → Devanagari answer", is_lang(r["answer"], "hi"), r["answer"])
    r = ask("Will it rain in Nashik tomorrow?", "mr")
    check("English weather question, Marathi chosen → Marathi answer", is_lang(r["answer"], "mr"), r["answer"])

    section("4. Language holds across a follow-up")
    first = ask("When should I apply fertilizer to wheat?", "hi")
    check("ask-back is in Hindi", is_lang(first["answer"], "hi"), first["answer"])
    check("…and waits for the missing detail", bool(first["pending"]), str(first["pending"]))
    second = ask("40 days", "hi", first["pending"])
    check("follow-up '40 days' (typed in English) → Hindi answer",
          is_lang(second["answer"], "hi") and "कल्ले" in second["answer"],
          second["answer"])

    section("Summary")
    print(f"Result: {_total - _failures}/{_total} checks passed"
          + (" — ALL PASSED" if not _failures else f" — {_failures} FAILED"))
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())
