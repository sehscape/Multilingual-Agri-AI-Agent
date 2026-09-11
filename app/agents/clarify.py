"""Is the question complete? Decide what can be answered and what to ask back.

Every message here is shown and spoken to the farmer in their own language,
so an incomplete or unclear question never ends in a wrong answer or silence:

  • nothing farm-related             → what I can help with, plus an example
  • crop care, but which crop?       → "which crop is this about?"
  • a crop the knowledge base lacks  → say so, and list the crops I know
  • stage-based advice, no age       → "how many days old is your crop?"
  • an impossible age (wheat, 300 d) → "please check the crop's age"
  • weather, but where?              → "which village or town?" (or 📍)
  • place not found / scheme unknown → found out after the tools run

When part of a question can be answered, it is answered and the missing part
becomes a short note after the answer. Only when nothing can be answered is
the reply just the question back. Either way the missing detail is
remembered, so the farmer can reply with only "40 days" or "Nashik".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.agents.understanding import SCHEME_SEARCH_TERMS, Understanding, is_coordinates
from app.ui.i18n import SPOKEN_EXAMPLES, crop_label, normalize_lang, t

# Advice that depends on the growth stage, so the crop's age is needed.
_AGE_NEEDED = {"fertilizer", "irrigation", "general", None}
# Days past a crop's usual duration before the stated age is queried.
_AGE_SLACK = 30


def crop_duration(crop: str) -> Optional[int]:
    from app.tools.crop_tool import _load_crop
    data = _load_crop(crop) or {}
    return data.get("total_duration_days")


@dataclass
class Issue:
    key: str                              # i18n key of the question / notice
    kwargs: dict = field(default_factory=dict)
    missing: Optional[str] = None         # detail to remember: age | location | crop
    note_key: Optional[str] = None        # wording to use when it is a side note

    def text(self, lang: str, as_note: bool = False) -> str:
        return t(self.note_key if as_note and self.note_key else self.key, lang, **self.kwargs)


@dataclass
class RequestPlan:
    run_crop: bool = False
    run_weather: bool = False
    run_scheme: bool = False
    crop_general: bool = False            # crop tool runs without a stage (age unknown)
    crop: Optional[str] = None
    days: Optional[int] = None
    location: Optional[str] = None
    scheme_query: str = ""
    issues: list = field(default_factory=list)
    reply: Optional[str] = None           # set when the whole reply is a message

    @property
    def answerable(self) -> bool:
        return self.run_weather or self.run_scheme or (self.run_crop and not self.crop_general)

    @property
    def missing(self) -> list[str]:
        return list(dict.fromkeys(i.missing for i in self.issues if i.missing))

    def notes(self, lang: str) -> str:
        return " ".join(i.text(lang, as_note=True) for i in self.issues)

    def tool_plan(self) -> dict:
        """The plan in the shape the LangChain ReAct policy reads."""
        return {"needs_crop_info": self.run_crop, "crop": self.crop,
                "needs_weather": self.run_weather, "location": self.location,
                "needs_scheme": self.run_scheme, "scheme_query": self.scheme_query}

    def _finish(self, lang: str) -> None:
        if not self.answerable:
            self.reply = " ".join(i.text(lang) for i in self.issues)


def plan_request(u: Understanding, lang: str) -> RequestPlan:
    """What to look up for this question, and what to ask the farmer."""
    lang = normalize_lang(lang)
    p = RequestPlan()
    if not u.wants_anything:
        key = {"greeting": "msg_greeting", "off_topic": "ask_offtopic"}.get(u.topic, "ask_unclear")
        p.reply = t(key, lang, example=SPOKEN_EXAMPLES[lang][0])
        return p

    if u.wants_crop_advice:
        crop = u.supported_crop
        if u.other_crop:
            p.issues.append(Issue("ask_unsupported_crop",
                                  {"crop": u.crop_words or u.other_crop}))
        elif not crop:
            p.issues.append(Issue("ask_crop", missing="crop"))
        else:
            name, days, total = crop_label(crop, lang), u.crop_age_days, crop_duration(crop)
            if days is not None and (days <= 0 or (total and days > total + _AGE_SLACK)):
                p.issues.append(Issue("ask_age_check",
                                      {"crop": name, "days": days, "total": total},
                                      missing="age"))
            elif days is None and u.advice_topic in _AGE_NEEDED:
                p.issues.append(Issue("ask_age", {"crop": name}, missing="age",
                                      note_key="note_age_for_exact"))
                p.run_crop, p.crop, p.crop_general = True, crop, True
            else:
                p.run_crop, p.crop, p.days = True, crop, days

    if u.wants_weather:
        if u.weather_place:
            p.run_weather, p.location = True, u.weather_place
        else:
            p.issues.append(Issue("ask_location", missing="location"))

    if u.wants_scheme:
        p.run_scheme = True
        p.scheme_query = " ".join(filter(None, [u.english,
                                               SCHEME_SEARCH_TERMS.get(u.scheme or "")]))
    p._finish(lang)
    if p.reply:
        p.run_crop = p.run_weather = p.run_scheme = False
    return p


def check_results(p: RequestPlan, state, u: Understanding, lang: str) -> None:
    """After the tools ran: a place the map could not find, a weather outage,
    or a scheme the documents don't cover becomes a notice for the farmer."""
    lang = normalize_lang(lang)
    weather = (state.weather_data or {}).get("context", "") if p.run_weather else ""
    if weather.startswith("Could not find location"):
        place = u.place_words or u.location or p.location
        if is_coordinates(place):
            place = t("your_location", lang)
        p.issues.append(Issue("ask_place_not_found", {"place": place}, missing="location"))
        p.run_weather, state.weather_data = False, None
    elif weather and ("temporarily unavailable" in weather or weather.startswith("Weather tool error")):
        p.issues.append(Issue("note_weather_down"))
        p.run_weather, state.weather_data = False, None

    if p.run_scheme:
        found = state.scheme_docs and "(relevance:" in state.scheme_docs[0].get("context", "")
        if not found:
            p.issues.append(Issue("ask_scheme_unknown"))
            p.run_scheme, state.scheme_docs = False, []
    p._finish(lang)
