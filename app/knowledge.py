"""The crops and schemes the assistant knows, in one place.

Crops come from data/crops/*.json and schemes from data/schemes/schemes.json.
Adding a crop means adding one file: its name in four languages, the other
words farmers use for it, and its growth stages. The rule router, the LLM
prompt, the quick-reply chips and the help text all read from here, so
nothing else has to change.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.config import CROPS_DIR, DATA_DIR

LANGS = ("en", "hi", "pa", "mr")
_INDIC = "ऀ-੿"   # Devanagari, Bengali and Gurmukhi blocks
_WORD_END = rf"[\w{_INDIC}]*"

# Crops the knowledge base does not cover, recognised so the farmer is told so
# plainly instead of being asked "which crop?" again. Short local words that
# are also everyday words are left out: आम (mango, but also "common"),
# आले (ginger, but also "came" in Marathi).
OTHER_CROPS: dict[str, tuple[str, ...]] = {
    "grapes": ("grape", "grapes", "अंगूर", "द्राक्ष", "ਅੰਗੂਰ"),
    "coconut": ("coconut", "नारियल", "नारळ", "ਨਾਰੀਅਲ"),
    "turmeric": ("turmeric", "haldi", "हल्दी", "हळद", "ਹਲਦੀ"),
    "pomegranate": ("pomegranate", "अनार", "डाळिंब", "ਅਨਾਰ"),
    "brinjal": ("brinjal", "eggplant", "baingan", "बैंगन", "वांगी", "वांगे", "ਬੈਂਗਣ"),
    "cauliflower": ("cauliflower", "फूलगोभी", "फूल गोभी", "फ्लॉवर", "ਫੁੱਲ ਗੋਭੀ"),
    "cabbage": ("cabbage", "पत्तागोभी", "पत्ता गोभी", "बंद गोभी", "कोबी", "ਬੰਦ ਗੋਭੀ"),
    "garlic": ("garlic", "लहसुन", "लसूण", "लसुण", "ਲਸਣ"),
    "ginger": ("ginger", "अदरक", "ਅਦਰਕ"),
    "mango": ("mango", "mangoes", "आंबा", "आंब्या", "ਅੰਬ"),
    "apple": ("apple", "apples", "सेब", "सफरचंद", "ਸੇਬ"),
    "black gram": ("black gram", "urad", "उड़द", "उडद", "उडीद", "ਮਾਂਹ"),
    "lentil": ("lentil", "lentils", "masoor", "मसूर", "ਮਸਰ"),
    "black pepper": ("black pepper", "काली मिर्च", "काळी मिरी", "ਕਾਲੀ ਮਿਰਚ"),
    "capsicum": ("capsicum", "shimla mirch", "शिमला मिर्च", "ढोबळी मिरची", "ਸ਼ਿਮਲਾ ਮਿਰਚ"),
    "sunflower": ("sunflower", "सूरजमुखी", "सूर्यफूल", "ਸੂਰਜਮੁਖੀ"),
    "peas": ("green peas", "मटर", "वाटाणा", "ਮਟਰ"),
    "barley": ("barley", "ਜੌਂ"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Crops
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def crops() -> dict[str, dict]:
    """Every crop guide, keyed by its English name, in display order."""
    found = []
    for path in Path(CROPS_DIR).glob("*.json"):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        found.append((data.get("order", 99), data["name"], data))
    return {name: data for _, name, data in sorted(found, key=lambda x: (x[0], x[1]))}


def crop(name: Optional[str]) -> Optional[dict]:
    return crops().get(name or "")


def crop_names() -> dict[str, dict[str, str]]:
    """{"wheat": {"en": "wheat", "hi": "गेहूं", …}, …} — what the farmer calls each crop."""
    return {name: dict(data["names"]) for name, data in crops().items()}


def crop_duration(name: str) -> Optional[int]:
    return (crop(name) or {}).get("total_duration_days")


def crop_age_limit(name: str) -> Optional[int]:
    """The oldest a crop of this kind usually gets (an 18-month adsali
    sugarcane, a ratoon banana); a farmer quoting more has likely misspoken."""
    data = crop(name) or {}
    return data.get("longest_duration_days") or data.get("total_duration_days")


def crop_words(name: str, langs=LANGS) -> list[str]:
    """Every word for a crop in the given languages: its names and aliases."""
    data = crop(name)
    if not data:
        return []
    words = [data["name"]] + [data["names"][lang] for lang in langs if lang in data["names"]]
    for lang in langs:
        words += data.get("aliases", {}).get(lang, [])
    return list(dict.fromkeys(w.lower() for w in words if w))


def _languages_for(lang: Optional[str]) -> tuple[str, ...]:
    """Which languages' crop words to look for. Hindi words are skipped for
    Marathi — "केला" (banana in Hindi) is "did" in Marathi — but kept for
    Punjabi, which speech recognition often writes in Devanagari."""
    if lang == "mr":
        return ("en", "mr")
    if lang == "pa":
        return ("en", "pa", "hi")
    if lang == "hi":
        return ("en", "hi")
    return LANGS


@lru_cache(maxsize=8)
def _crop_patterns(lang: Optional[str]) -> list[tuple[re.Pattern, int, str, bool]]:
    patterns = []
    entries = [(name, crop_words(name, _languages_for(lang)), True) for name in crops()]
    entries += [(name, words, False) for name, words in OTHER_CROPS.items()]
    for name, words, known in entries:
        for word in words:
            if word.isascii():   # whole English words: "rice" must not fire inside "price"
                rx = rf"(?<![a-z]){re.escape(word)}(?:e?s)?(?![a-z])"
            else:                # word starts: "कापस" also matches "कापसाला"; "ऊस" not "पाऊस"
                rx = rf"(?<![\w{_INDIC}]){re.escape(word)}{_WORD_END}"
            patterns.append((re.compile(rx), len(word), name, known))
    return patterns


@dataclass(frozen=True)
class CropMention:
    crop: str      # a knowledge-base crop, or the English name of another crop
    words: str     # the crop as it was written
    known: bool    # True if the knowledge base has a guide for it

    @property
    def label(self) -> str:
        """`crop` for a known crop, "other:<name>" for any other."""
        return self.crop if self.known else f"other:{self.crop}"


def find_crop(text: str, lang: Optional[str] = None) -> Optional[CropMention]:
    """The crop a question is about. A longer name beats a shorter one inside
    it ("मूंगफली" groundnut over "मूंग" moong, "black gram" over "gram"), and
    a crop the guide covers beats one it does not."""
    text = text or ""
    low = text.lower()
    hits = []   # (start, end, length of the crop word, crop, known)
    for rx, size, name, known in _crop_patterns(lang):
        for m in rx.finditer(low):
            hits.append((m.start(), m.end(), size, name, known))
    if not hits:
        return None
    hits = [h for h in hits
            if not any(o[0] <= h[0] and h[1] <= o[1] and o[2] > h[2] for o in hits)]
    best = min(hits, key=lambda h: (not h[4], h[0], -h[2]))
    return CropMention(crop=best[3], words=text[best[0]:best[1]], known=best[4])


def resolve_crop(name: Optional[str]) -> Optional[str]:
    """A single crop name in any language or spelling ("paddy", "tur",
    "ਝੋਨਾ", "chickpeas") → the knowledge-base crop, or None."""
    key = (name or "").strip().lower()
    if not key:
        return None
    if key in crops():
        return key
    mention = find_crop(key)
    if mention and mention.known and mention.words.strip().lower() == key:
        return mention.crop
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Government schemes
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def schemes() -> dict[str, dict]:
    """Every scheme, keyed by id, in the order they are checked."""
    with (DATA_DIR / "schemes" / "schemes.json").open(encoding="utf-8") as f:
        return {s["id"]: s for s in json.load(f)}


def scheme_ids() -> tuple[str, ...]:
    return tuple(schemes())


def scheme_names(lang: str) -> list[str]:
    """Every scheme as a farmer would name it, best known first."""
    shown = sorted(schemes().values(), key=lambda s: s.get("order", 99))
    return [s["names"].get(lang) or s["names"]["en"] for s in shown]


def search_terms() -> dict[str, str]:
    """Words that steer the scheme search to the right official document."""
    return {sid: s["search"] for sid, s in schemes().items()}


def find_scheme(text: str) -> Optional[str]:
    """Which scheme a question names. A scheme's own name ("PM Kisan
    Maandhan", "solar pump") wins over a general word ("pension", "drip")."""
    low = (text or "").lower()
    for field in ("names", "words"):
        for sid, s in schemes().items():
            if any(w.lower() in low for w in s["match"][field]):
                return sid
    return None


def names_a_scheme(text: str) -> bool:
    """True if the text names a scheme outright ("PM-KUSUM", "सोलर पंप")."""
    low = (text or "").lower()
    return any(w.lower() in low for s in schemes().values() for w in s["match"]["names"])


def scheme_title(source: str) -> str:
    """A scheme document's file name ("pm_kisan", "Pm Kisan") → its title ("PM-KISAN")."""
    low = (source or "").strip().lower()
    key = re.sub(r"[\s-]+", "_", low)
    for s in schemes().values():
        if key == s["file"] or low == s["title"].lower():
            return s["title"]
    return (source or "").replace("_", " ").title()
