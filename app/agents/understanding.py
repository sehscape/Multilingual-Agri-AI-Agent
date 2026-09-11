"""Understanding — what did the farmer ask, and what is still missing?

Turns the farmer's words (typed, or a voice transcript; English, Hindi,
Punjabi or Marathi) into one structured `Understanding`: an English version of
the question, its topic, the crop, the crop's age, the place, and which of
crop care / weather / government schemes the farmer wants.

Two engines:
  • Groq LLM (GROQ_API_KEY set) — reads all four languages directly, copes
    with speech-recognition spelling mistakes, and folds a short follow-up
    reply ("40 days", "Nashik") into the question it completes.
  • Rules (no key, or the LLM is unreachable) — the keyword router in
    StubLLM._classify, which also knows common Hindi/Marathi/Punjabi farm words.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Optional

from app.models.llm import StubLLM
from app.utils.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_CROPS = ("wheat", "rice", "onion", "tomato", "cotton", "maize")
_CROP_SYNONYMS = {"paddy": "rice", "corn": "maize"}
SCHEMES = ("pm_kisan", "pmfby", "kcc", "soil_health_card")
_TOPICS = ("farming", "greeting", "off_topic", "unclear")
_ADVICE_TOPICS = ("fertilizer", "irrigation", "pest_disease", "sowing", "harvest", "general")

# Search words that steer the scheme search to the right official document.
SCHEME_SEARCH_TERMS = {
    "pm_kisan": "PM-KISAN Pradhan Mantri Kisan Samman Nidhi",
    "pmfby": "Pradhan Mantri Fasal Bima Yojana PMFBY crop insurance",
    "kcc": "Kisan Credit Card KCC loan",
    "soil_health_card": "Soil Health Card soil testing",
}

# ── Rule-engine vocabulary ────────────────────────────────────────────────────
# Crops the knowledge base does not cover, recognised so the farmer is told so
# plainly instead of being asked "which crop?" again. Matched at word starts
# only: "ऊस" (sugarcane) must not fire inside "पाऊस" (rain).
_OTHER_CROPS = {
    "sugarcane": ("sugarcane", "गन्ना", "गन्ने", "ऊस", "ਗੰਨਾ", "ਗੰਨੇ"),
    "soybean": ("soybean", "soyabean", "सोयाबीन", "ਸੋਇਆਬੀਨ"),
    "potato": ("potato", "आलू", "बटाटा", "ਆਲੂ"),
    "chickpea": ("chickpea", "चना", "हरभरा", "ਛੋਲੇ"),
    "mustard": ("mustard", "सरसों", "मोहरी", "ਸਰ੍ਹੋਂ"),
    "groundnut": ("groundnut", "peanut", "मूंगफली", "भुईमूग", "ਮੂੰਗਫਲੀ"),
    "banana": ("banana", "केला", "केळी", "ਕੇਲਾ"),
    "grapes": ("grape", "अंगूर", "द्राक्ष", "ਅੰਗੂਰ"),
    "chilli": ("chilli", "chili", "मिर्च", "मिरची", "ਮਿਰਚ"),
    "millet": ("bajra", "jowar", "millet", "बाजरा", "बाजरी", "ज्वार", "ਬਾਜਰਾ"),
}
_SCHEME_WORDS = (  # order matters: "kisan credit" before "pm kisan"
    ("kcc", ("kisan credit", "credit card", "kcc", "क्रेडिट कार्ड", "ਕ੍ਰੈਡਿਟ ਕਾਰਡ")),
    ("pmfby", ("fasal bima", "insurance", "pmfby", "बीमा", "विमा", "ਬੀਮਾ")),
    ("soil_health_card", ("soil health", "soil card", "soil test", "मृदा", "मिट्टी",
                          "माती", "ਮਿੱਟੀ")),
    ("pm_kisan", ("pm-kisan", "pm kisan", "pmkisan", "samman nidhi", "पीएम किसान",
                  "पीएम-किसान", "सम्मान निधि", "ਪੀਐਮ ਕਿਸਾਨ", "6000", "6,000")),
)
_SOW_KW = ("sow", "sowing", "seed rate", "बुवाई", "बुआई", "बोवाई", "पेरणी", "ਬਿਜਾਈ")
_HARVEST_KW = ("harvest", "कटाई", "काढणी", "ਵਾਢੀ")
_GREETINGS = ("hello", "hi", "hey", "namaste", "namaskar", "thank", "thanks", "bye",
              "नमस्ते", "नमस्कार", "धन्यवाद", "शुक्रिया", "राम राम",
              "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "ਧੰਨਵਾਦ")
# Capitalised words after "in"/"at"/"near"/"for" that are not places.
_NOT_PLACES = {"january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december", "english", "hindi",
               "marathi", "punjabi", "summer", "winter", "rabi", "kharif", "my", "the",
               "kisan", "pradhan", "fasal", "soil", "credit", "crop", "government", "scheme",
               "wheat", "rice", "paddy", "onion", "tomato", "cotton", "maize", "this", "next"}
_COORDS = re.compile(r"^\s*-?\d{1,2}(?:\.\d+)?\s*,\s*-?\d{1,3}(?:\.\d+)?\s*$")


def is_coordinates(text: Optional[str]) -> bool:
    return bool(text and _COORDS.match(text))


@dataclass
class Understanding:
    english: str = ""
    topic: str = "unclear"                 # farming | greeting | off_topic | unclear
    crop: Optional[str] = None             # a SUPPORTED_CROPS name, or "other:<name>"
    crop_words: Optional[str] = None       # the crop as the farmer said it
    crop_age_days: Optional[int] = None
    location: Optional[str] = None         # place named in the question (English)
    place_words: Optional[str] = None      # that place as the farmer said it
    saved_location: Optional[str] = None   # the location box / GPS, in English
    wants_weather: bool = False
    wants_scheme: bool = False
    scheme: Optional[str] = None
    wants_crop_advice: bool = False
    advice_topic: Optional[str] = None
    engine: str = "rules"                  # which engine understood it

    @property
    def wants_anything(self) -> bool:
        return self.wants_weather or self.wants_scheme or self.wants_crop_advice

    @property
    def supported_crop(self) -> Optional[str]:
        return self.crop if self.crop in SUPPORTED_CROPS else None

    @property
    def other_crop(self) -> Optional[str]:
        if self.crop and self.crop.startswith("other:"):
            return self.crop.split(":", 1)[1].strip() or "that crop"
        return None

    @property
    def weather_place(self) -> Optional[str]:
        """A place named in the question wins over the saved one."""
        return self.location or self.saved_location

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Understanding":
        return cls(**{k: v for k, v in (data or {}).items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        wants = [w for w, on in (("crop", self.wants_crop_advice), ("weather", self.wants_weather),
                                 ("scheme", self.wants_scheme)) if on]
        return (f"{self.engine}: topic={self.topic} crop={self.crop or '—'} "
                f"age={self.crop_age_days if self.crop_age_days is not None else '—'} "
                f"place={self.weather_place or '—'} wants={'+'.join(wants) or '—'}"
                f"{f' scheme={self.scheme}' if self.scheme else ''}"
                f"{f' advice={self.advice_topic}' if self.advice_topic else ''}")


# ══════════════════════════════════════════════════════════════════════════════
# Rules engine
# ══════════════════════════════════════════════════════════════════════════════

def _word_starts(text: str, words) -> bool:
    return any(re.search(rf"(?<![\wऀ-੿]){re.escape(w)}", text) for w in words)


def _find_other_crop(text: str) -> Optional[str]:
    low = text.lower()
    return next((name for name, words in _OTHER_CROPS.items() if _word_starts(low, words)), None)


def _find_scheme(text: str) -> Optional[str]:
    low = text.lower()
    return next((key for key, words in _SCHEME_WORDS if any(w in low for w in words)), "other")


def _advice_topic(text: str) -> str:
    q = StubLLM._normalize(text)
    has = lambda kws: any(k in q for k in kws)  # noqa: E731
    if has(StubLLM._PEST_KW) or has(StubLLM._REG_PEST_KW):
        return "pest_disease"
    if has(StubLLM._FERT_KW) or has(StubLLM._REG_FERT_KW):
        return "fertilizer"
    if has(StubLLM._IRRIG_KW) or has(StubLLM._REG_IRRIG_KW):
        return "irrigation"
    if has(_SOW_KW):
        return "sowing"
    if has(_HARVEST_KW):
        return "harvest"
    return "general"


def _english_place(text: str) -> Optional[str]:
    """'…rain in Shirur tomorrow' → 'Shirur' (English text only)."""
    # A place name is Capitalised ("Shirur"), not an acronym ("PM", "KCC").
    for m in re.finditer(r"\b(?:in|at|near|for)\s+([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b", text):
        place = m.group(1)
        if place.split()[0].lower() not in _NOT_PLACES:
            return place
    return None


def _english_city(name: Optional[str]) -> Optional[str]:
    """A saved location in English spelling (regional city names mapped)."""
    name = (name or "").strip()
    if not name or is_coordinates(name) or name.isascii():
        return name or None
    return next((city for city, names in StubLLM._REG_CITIES.items()
                 if any(n in name for n in names)), name)


def understand_with_rules(text: str, english: Optional[str] = None,
                          saved_location: Optional[str] = None) -> Understanding:
    text = (text or "").strip()
    english = (english or text).strip()
    routing = english if english == text else f"{english} (original: {text})"
    c = StubLLM()._classify(routing)

    u = Understanding(
        english=english,
        crop=_CROP_SYNONYMS.get(c["crop"], c["crop"]),
        crop_age_days=c["days"],
        location=c["location"] or _english_place(english),
        saved_location=_english_city(saved_location),
        wants_weather=c["needs_weather"],
        wants_scheme=c["needs_scheme"],
        wants_crop_advice=c["needs_crop_info"],
        engine="rules",
    )
    if not u.crop and (other := _find_other_crop(routing)):
        u.crop, u.wants_crop_advice = f"other:{other}", True
    if u.location and not (u.wants_weather or u.wants_scheme or u.wants_crop_advice):
        u.wants_weather = True
    if u.wants_crop_advice:
        u.advice_topic = _advice_topic(routing)
    if u.wants_scheme:
        u.scheme = _find_scheme(routing)
    words = re.findall(r"[\wऀ-੿]+", text.lower())
    if u.wants_anything:
        u.topic = "farming"
    elif words and len(words) <= 6 and _word_starts(" ".join(words), _GREETINGS):
        u.topic = "greeting"
    else:
        u.topic = "unclear"
    return u


def merge_followup(prev: Understanding, new: Understanding, missing: list[str],
                   new_text: str = "") -> Understanding:
    """Fold a short reply ("40 days", "Nashik", "wheat") into the question the
    assistant asked it about. A reply that supplies none of the missing
    details is treated as a new question."""
    words = re.findall(r"[\wऀ-੿]+", new_text)
    if ("location" in missing and not new.location and not new.wants_anything
            and 0 < len(words) <= 3 and new.crop_age_days is None):
        new.location = new_text.strip(" .,!?।")        # a bare place name
    supplies = {"age": new.crop_age_days is not None, "location": bool(new.location),
                "crop": bool(new.crop)}
    if not any(supplies.get(m) for m in missing):
        return new
    if new.crop and prev.crop and new.crop != prev.crop:
        return new                                     # a different crop → new question
    merged = Understanding.from_dict(prev.to_dict())
    merged.crop = merged.crop or new.crop
    merged.crop_words = merged.crop_words or new.crop_words
    if new.crop_age_days is not None:
        merged.crop_age_days = new.crop_age_days
    if new.location:
        merged.location, merged.place_words = new.location, new.place_words
    merged.wants_weather |= new.wants_weather
    merged.wants_scheme |= new.wants_scheme
    merged.scheme = merged.scheme or new.scheme
    merged.topic = "farming"
    merged.english = f"{prev.english} {new.english}".strip()
    merged.engine = f"{new.engine}+follow-up"
    return merged


# ══════════════════════════════════════════════════════════════════════════════
# LLM engine (Groq)
# ══════════════════════════════════════════════════════════════════════════════

_LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "pa": "Punjabi"}
_ASKED_FOR = {"age": "the crop's age in days", "location": "their village or town",
              "crop": "the crop's name"}

_SYSTEM_PROMPT = """You turn an Indian farmer's question into JSON for a farm advice assistant.

The words may come from speech recognition, so expect spelling mistakes, missing punctuation and a mix of Hindi, Marathi, Punjabi and English words. Work out what the farmer most likely meant. Never add details the farmer did not say.

The assistant knows these crops: wheat, rice (paddy), onion, tomato, cotton, maize (corn).
It knows these government schemes: pm_kisan (PM-KISAN income support), pmfby (PM Fasal Bima Yojana crop insurance), kcc (Kisan Credit Card), soil_health_card (Soil Health Card).

Return ONLY a JSON object with these keys:
"english": the question in clear, simple English, keeping every detail. Numbers as digits. Crop age in days (6 weeks = 42 days, 2 months = 60 days). Places in their usual English spelling.
"topic": "farming" (crops, farm work, weather, rain, farm schemes or loans), "greeting" (only hello, thanks or goodbye), "off_topic" (not about farming), or "unclear" (the words make no sense).
"crop": "wheat", "rice", "onion", "tomato", "cotton" or "maize"; "other:<english name>" for any other crop; null if no crop is named.
"crop_words": the crop exactly as the farmer said it, or null.
"crop_age_days": whole number of days since sowing or transplanting, or null if not said.
"location": the village, town or district named in the question, in English spelling, or null.
"place_words": that place exactly as the farmer said it, or null.
"saved_location": the saved location given below, in English spelling, or null.
"wants_weather": true if they ask about rain, weather, temperature, wind or storms, or whether to irrigate or spray given the weather.
"wants_scheme": true if they ask about a government scheme, subsidy, loan, insurance or money support.
"scheme": "pm_kisan", "pmfby", "kcc", "soil_health_card", "other" or null.
"wants_crop_advice": true if they ask how to grow or look after a crop: fertilizer, water, pests, disease, weeds, yellow leaves, sowing or harvest.
"advice_topic": "fertilizer", "irrigation", "pest_disease", "sowing", "harvest", "general" or null."""


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def _as_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in ("", "null", "none", "unknown", "n/a") else text


def _as_days(value) -> Optional[int]:
    try:
        days = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return days if -1 < days < 5000 else None


def _parse_llm_json(raw: str, fallback_english: str) -> Understanding:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in the LLM reply")
    data = json.loads(match.group())

    crop = (_as_text(data.get("crop")) or "").lower()
    crop = _CROP_SYNONYMS.get(crop, crop)
    if crop and crop not in SUPPORTED_CROPS and not crop.startswith("other:"):
        crop = f"other:{crop}"
    if crop.startswith("other:") and _CROP_SYNONYMS.get(crop[6:].strip(), crop[6:].strip()) \
            in SUPPORTED_CROPS:
        crop = _CROP_SYNONYMS.get(crop[6:].strip(), crop[6:].strip())

    topic = _as_text(data.get("topic")) or ""
    scheme = _as_text(data.get("scheme"))
    advice = _as_text(data.get("advice_topic"))
    u = Understanding(
        english=_as_text(data.get("english")) or fallback_english,
        topic=topic if topic in _TOPICS else "unclear",
        crop=crop or None,
        crop_words=_as_text(data.get("crop_words")),
        crop_age_days=_as_days(data.get("crop_age_days")),
        location=_as_text(data.get("location")),
        place_words=_as_text(data.get("place_words")),
        saved_location=_as_text(data.get("saved_location")),
        wants_weather=_as_bool(data.get("wants_weather")),
        wants_scheme=_as_bool(data.get("wants_scheme")),
        scheme=scheme if scheme in SCHEMES + ("other",) else None,
        wants_crop_advice=_as_bool(data.get("wants_crop_advice")),
        advice_topic=advice if advice in _ADVICE_TOPICS else None,
        engine="llm",
    )
    if u.wants_anything:
        u.topic = "farming"
    if u.crop and u.topic == "farming" and not u.wants_anything:
        u.wants_crop_advice = True
    if u.wants_crop_advice and not u.advice_topic:
        u.advice_topic = "general"
    if u.wants_scheme and not u.scheme:
        u.scheme = "other"
    return u


def understand_with_llm(client, text: str, lang: str, saved_location: Optional[str] = None,
                        pending: Optional[dict] = None) -> Understanding:
    saved = saved_location if saved_location and not is_coordinates(saved_location) else None
    lines = [f"Farmer's language: {_LANG_NAMES.get(lang, 'English')}",
             f"Saved location: {saved or 'none'}"]
    if pending:
        asked = " and ".join(_ASKED_FOR.get(m, m) for m in pending.get("missing", []))
        lines.append(
            f'Earlier the farmer asked: "{pending.get("english", "")}". The assistant then '
            f"asked for {asked}. The new words below may be that answer: if so, combine both "
            "into ONE complete question and fill every field for it. If the new words are a "
            "different question, ignore the earlier one.")
    lines.append(f'Farmer\'s words: "{text}"')
    raw = client.chat(
        [{"role": "system", "content": _SYSTEM_PROMPT},
         {"role": "user", "content": "\n".join(lines)}],
        json_mode=True, max_tokens=700, temperature=0.0,
    )
    logger.info("Understanding (LLM) raw: %.400s", raw)
    return _parse_llm_json(raw, fallback_english=text)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def understand(text: str, lang: str, saved_location: Optional[str] = None,
               pending: Optional[dict] = None, client=None,
               english: Optional[str] = None) -> Understanding:
    """Understand the farmer's words. `client` is a GroqClient (LLM engine) or
    None (rules). `pending` is the earlier question when the assistant asked
    for a missing detail; `english` is an English translation, if one exists."""
    rules = understand_with_rules(text, english, saved_location)
    missing = list((pending or {}).get("missing") or [])

    if client is not None:
        try:
            u = understand_with_llm(client, text, lang, saved_location, pending)
            # The rules still catch what the model left empty.
            if u.topic == "farming":
                u.crop = u.crop or rules.crop
                if u.crop_age_days is None:
                    u.crop_age_days = rules.crop_age_days
                u.location = u.location or rules.location
            u.saved_location = u.saved_location or _english_city(saved_location)
            if pending and u.topic != "farming":
                # The model didn't connect the reply to the earlier question.
                prev = Understanding.from_dict(pending.get("understanding") or {})
                merged = merge_followup(prev, rules, missing, text)
                if merged is not rules:
                    u = merged
            return u
        except Exception as exc:  # network, quota, bad JSON → rules
            logger.warning("LLM understanding failed (%s) — using rules.", exc)

    if pending:
        prev = Understanding.from_dict(pending.get("understanding") or {})
        return merge_followup(prev, rules, missing, text)
    return rules
