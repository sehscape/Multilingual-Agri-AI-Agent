"""Reply writer — the answer, in the farmer's own language, from the tool facts only.

The agent gathers facts in English (crop stage advice, live weather, scheme
documents). This step asks the Groq LLM to answer the farmer's actual
question from those facts — in Hindi, Punjabi, Marathi or English, in short
spoken sentences, because the reply is read aloud to a farmer who may not
read. It must not add any dose, date, amount or rule that is not in the facts.

If the reply comes back in the wrong script (e.g. Punjabi in Devanagari), it
is asked for once more; if the LLM is unavailable the caller falls back to
the rule-based English answer.
"""
from __future__ import annotations

import re
from datetime import date

from app.utils.logging import get_logger

logger = get_logger(__name__)

# (language name, script, Unicode range of the script's letters)
_LANGS = {
    "en": ("English", "Latin", (0x0041, 0x024F)),
    "hi": ("Hindi", "Devanagari", (0x0900, 0x097F)),
    "mr": ("Marathi", "Devanagari", (0x0900, 0x097F)),
    "pa": ("Punjabi", "Gurmukhi", (0x0A00, 0x0A7F)),
}
_BLOCK_LIMIT = 2200   # characters of each fact block sent to the model

_SYSTEM_PROMPT = """You are Kisan Mitra, a kind farm advisor for Indian farmers. Many farmers cannot read, so your reply will be read aloud to them.

Rules:
- Reply ONLY in {language}, written in {script} script. Common farm product names like urea or DAP are fine.
- Use ONLY the facts given. Never add a dose, amount, price, date, eligibility rule or weather number that is not in the facts. If the facts do not cover something the farmer asked, say so simply and suggest the local Krishi Vigyan Kendra (KVK) or agriculture officer.
- First answer exactly what the farmer asked in one or two sentences. Then give at most 4 short, practical steps.
- Short, simple, spoken sentences. No markdown, no bullet symbols, no emojis, no headings.
- Write numbers as digits. Say temperatures as "<number> degrees". Today is {today}; say "today", "tomorrow" or the weekday instead of dates.
- Stay under {max_words} words."""


def _script_share(text: str, lang: str) -> float:
    lo, hi = _LANGS.get(lang, _LANGS["en"])[2]
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(lo <= ord(ch) <= hi for ch in letters) / len(letters)


def clean_for_speech(text: str) -> str:
    """Strip markdown, bullets and emoji so the text reads and speaks cleanly."""
    text = re.sub(r"[*_#`>|]+", "", text or "")
    text = re.sub(r"^\s*[-•●▪]\s*", "", text, flags=re.M)
    text = "".join(ch for ch in text if not (0x1F000 <= ord(ch) <= 0x1FAFF
                                             or 0x2600 <= ord(ch) <= 0x27BF))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _facts(state) -> str:
    blocks = []
    if state.crop_data and state.crop_data.get("context"):
        blocks.append("CROP KNOWLEDGE\n" + state.crop_data["context"][:_BLOCK_LIMIT])
    if state.weather_data and state.weather_data.get("context"):
        blocks.append("LIVE WEATHER\n" + state.weather_data["context"][:_BLOCK_LIMIT])
    if state.scheme_docs and state.scheme_docs[0].get("context"):
        blocks.append("GOVERNMENT SCHEME DOCUMENTS\n"
                      + state.scheme_docs[0]["context"][:_BLOCK_LIMIT])
    return "\n\n".join(blocks) or "No facts were found."


def write_reply(client, state, lang: str, max_words: int = 110) -> str:
    """The farmer-facing answer in `lang`, written by the LLM from the facts."""
    name, script, _ = _LANGS.get(lang, _LANGS["en"])
    system = _SYSTEM_PROMPT.format(language=name, script=script, max_words=max_words,
                                   today=date.today().strftime("%A %d %B %Y"))
    asked = state.original_text or state.english_text
    user = (f"The farmer asked (in {name}): \"{asked}\"\n"
            f"In English: \"{state.english_text}\"\n\n"
            f"FACTS\n{_facts(state)}\n\n"
            f"Write the reply in {name} ({script} script).")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    reply = clean_for_speech(client.chat(messages, max_tokens=1200, temperature=0.3))
    if _script_share(reply, lang) < 0.6:
        logger.warning("Reply not in %s script (%.0f%%) — asking again.",
                       script, 100 * _script_share(reply, lang))
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": f"Please write the same reply again, "
                                                 f"only in {name} using {script} script."}]
        reply = clean_for_speech(client.chat(messages, max_tokens=1200, temperature=0.2))
        if _script_share(reply, lang) < 0.6:
            raise ValueError(f"the model did not write {name} in {script} script")
    return reply
