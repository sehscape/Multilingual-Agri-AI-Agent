"""LLM provider abstraction (Phase 4).

The LLM always receives and returns English text.
Regional language handling is done by IndicTrans2 at the pipeline boundaries.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

from app.config import (
    LLM_MODEL_ID, LOCAL_LLM_MODEL_ID, MAX_NEW_TOKENS, TEMPERATURE,
    HF_TOKEN, USE_HF_INFERENCE_API, USE_STUB_LLM,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)

_LLM_SYSTEM_PROMPT = (
    "You are a helpful agricultural assistant for Indian farmers. Use ONLY the "
    "information provided in the user's message. Never invent scheme names, "
    "subsidies, weather readings, or pesticide dosages. Be concise, practical, "
    "and follow the requested answer format exactly."
)


class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for the given English prompt."""


class HuggingFaceLocalLLM(BaseLLM):
    """Runs a small open-source instruct model locally via transformers.

    Designed to work on a CPU-only laptop (no GPU): the default model is a small
    ungated model (see LOCAL_LLM_MODEL_ID). Generation is slower on CPU (a few
    seconds per answer) but fully offline after the one-time model download.
    On a GPU it automatically uses float16.
    """

    def __init__(self, model_id: str = LOCAL_LLM_MODEL_ID, device: str = "cpu") -> None:
        self.model_id = model_id
        self.device = device
        self._model = None
        self._tokenizer = None

    def _load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype = torch.float16 if self.device == "cuda" else torch.float32
        logger.info("Loading local LLM: %s on %s (%s)", self.model_id, self.device, dtype)
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_id, torch_dtype=dtype, low_cpu_mem_usage=True,
        ).to(self.device)
        logger.info("Local LLM loaded.")

    def generate(self, prompt: str) -> str:
        import torch

        t0 = time.time()
        self._load()
        messages = [
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        # Render the chat template to text, then tokenize — robust across
        # transformers versions (apply_chat_template's return type varies).
        chat_text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
        inputs = self._tokenizer(chat_text, return_tensors="pt").to(self.device)

        # Cap new tokens so CPU generation stays responsive.
        max_new = min(MAX_NEW_TOKENS, 400)
        with torch.no_grad():
            output = self._model.generate(
                **inputs,
                max_new_tokens=max_new,
                do_sample=False,  # greedy — faster and stable on CPU
                pad_token_id=self._tokenizer.eos_token_id,
            )
        gen_tokens = output[0][inputs["input_ids"].shape[-1]:]
        text = self._tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()
        logger.info("Local LLM | %s | %.1fs | %d chars", self.model_id, time.time() - t0, len(text))
        return text


class HuggingFaceInferenceAPILLM(BaseLLM):
    """
    Calls the HF Inference API – no local GPU needed.
    Used during local development (USE_HF_INFERENCE_API=true).
    """

    def __init__(self, model_id: str = LLM_MODEL_ID, token: str = HF_TOKEN) -> None:
        self.model_id = model_id
        self.token = token

    def generate(self, prompt: str) -> str:
        import requests

        t0 = time.time()
        api_url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": MAX_NEW_TOKENS,
                "temperature": TEMPERATURE,
                "return_full_text": False,
            },
        }
        resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        text = result[0]["generated_text"] if isinstance(result, list) else str(result)
        logger.info("HF Inference API LLM | %.2fs", time.time() - t0)
        return text.strip()


class StubLLM(BaseLLM):
    """Returns context-aware responses for local dev without an HF token.

    It simulates two LLM roles:
      1. Intent extraction  → returns a JSON object (see INTENT_EXTRACTION_PROMPT)
      2. Answer generation  → composes a grounded answer from the crop / weather /
         scheme context blocks injected into FINAL_ANSWER_PROMPT.

    The answer composer only uses information actually present in the prompt —
    it never invents crops, weather readings, or scheme facts.
    """

    # Crops the knowledge base recognises (keep in sync with crop_tool._CROP_FILES).
    _KNOWN_CROPS = ("wheat", "rice", "paddy", "onion", "tomato", "cotton", "maize", "corn")

    # Cities used to resolve a location in dev/stub mode (real LLM handles this properly).
    _KNOWN_CITIES = (
        "pune", "mumbai", "nashik", "nagpur", "nanded", "aurangabad", "kolhapur",
        "ludhiana", "amritsar", "jalandhar", "patiala", "bathinda", "chandigarh",
        "varanasi", "kanpur", "lucknow", "agra", "meerut", "gorakhpur",
        "delhi", "jaipur", "bhopal", "indore", "patna", "hyderabad", "bengaluru",
    )

    # Keyword groups used by the stub intent classifier.
    _WEATHER_KW = ("rain", "weather", "temperature", "forecast", "flood",
                   "drought", "humid", "spray", "storm", "climate", "hail")
    _SCHEME_KW = ("scheme", "subsidy", "government", "loan", "credit", "insurance",
                  "pm-kisan", "pm kisan", "kisan", "kcc", "yojana", "pmfby", "benefit")
    _FERT_KW = ("fertilizer", "fertiliser", "urea", "dap", "npk", "nutrient", "manure", "compost")
    _PEST_KW = ("pest", "insect", "disease", "fungus", "fungal", "mildew", "aphid",
                "borer", "blight", "rust", "yellow", "spot", "rot", "wilt")
    _IRRIG_KW = ("irrigat", "watering", "water requirement", "how much water")
    # Any of these (or a known crop name) means crop knowledge is needed.
    # NB: the bare word "crop" is intentionally excluded — it also appears in
    # scheme queries like "crop insurance" / "crop loan", where it must NOT pull
    # in the crop-knowledge tool. A named crop or a specific topic word triggers it.
    _CROP_TOPIC_KW = (("sowing", "harvest", "yield", "leaf", "leaves",
                       "plant", "seedling", "spacing") + _FERT_KW + _PEST_KW + _IRRIG_KW)

    def generate(self, prompt: str) -> str:
        logger.warning("StubLLM: building response from injected context.")
        if '"intent"' in prompt:
            return self._extract_intent(prompt)
        return self._compose_answer(prompt)

    # ── Intent extraction ────────────────────────────────────────────────────
    def _extract_intent(self, prompt: str) -> str:
        import re

        # Capture only the rest of the "Query:" line (not the template that follows),
        # so an empty query does not accidentally match the prompt's instructions.
        m = re.search(r"Query:[ \t]*(.*)", prompt)
        query = (m.group(1).strip() if m else "").lower()

        crop = next((c for c in self._KNOWN_CROPS if c in query), None)

        days_match = re.search(r"(\d+)\s*day", query)
        days = int(days_match.group(1)) if days_match else None

        location = next((c.title() for c in self._KNOWN_CITIES if c in query), None)

        needs_weather = any(k in query for k in self._WEATHER_KW)
        needs_scheme = any(k in query for k in self._SCHEME_KW)
        needs_crop_info = crop is not None or any(k in query for k in self._CROP_TOPIC_KW)

        # Choose the single best intent label; "multiple" when >1 category applies.
        categories = sum([needs_weather, needs_scheme, needs_crop_info])
        if categories > 1:
            intent = "multiple"
        elif needs_scheme:
            intent = "government_scheme"
        elif needs_crop_info:
            if any(k in query for k in self._PEST_KW):
                intent = "pest_or_disease"
            elif any(k in query for k in self._FERT_KW):
                intent = "fertilizer"
            elif any(k in query for k in self._IRRIG_KW):
                intent = "irrigation"
            else:
                intent = "crop_advice"
        elif needs_weather:
            intent = "weather"
        else:
            intent = "unknown" if not query else "general_farming"

        crop_json = f'"{crop}"' if crop else "null"
        loc_json = f'"{location}"' if location else "null"
        days_json = str(days) if days is not None else "null"
        return (
            f'{{"intent": "{intent}", "crop": {crop_json}, "crop_stage_days": {days_json}, '
            f'"location": {loc_json}, "needs_weather": {str(needs_weather).lower()}, '
            f'"needs_scheme": {str(needs_scheme).lower()}, '
            f'"needs_crop_info": {str(needs_crop_info).lower()}}}'
        )

    # ── Answer generation ──────────────────────────────────────────────────────
    def _compose_answer(self, prompt: str) -> str:
        crop_blk = _section(prompt, "--- Crop Knowledge ---", "--- Government Scheme")
        weather_blk = _section(prompt, "--- Weather Data ---", "--- Crop Knowledge ---")
        scheme_blk = _section(prompt, "--- Government Scheme Information (from official documents) ---", "Instructions:")

        crop = _parse_crop(crop_blk)
        weather = _parse_weather(weather_blk)
        scheme = _parse_scheme(scheme_blk)

        # ── Situation ─────────────────────────────────────────────────────────
        situation_parts = []
        if crop:
            if crop["stage"]:
                situation_parts.append(
                    f"Your {crop['name']} crop is currently in the {crop['stage']} stage."
                )
            else:
                situation_parts.append(f"Regarding your {crop['name']} crop.")
        if weather:
            cond = weather.get("condition") or "current conditions"
            temp = f" ({weather['temp']})" if weather.get("temp") else ""
            situation_parts.append(f"Weather for {weather['location']}: {cond}{temp}.")
        if scheme and not crop and not weather:
            situation_parts.append("You asked about government agricultural support.")
        if not situation_parts:
            situation_parts.append(
                "I could not find specific crop, weather, or scheme data for this question."
            )

        # ── Action steps ──────────────────────────────────────────────────────
        steps = []
        if crop:
            if crop["irrigation"]:
                steps.append(f"Irrigation: {crop['irrigation']}")
            if crop["fertilizer"]:
                steps.append(f"Fertilizer: {crop['fertilizer']}")
            if crop["watch_for"]:
                steps.append(f"Watch for: {crop['watch_for']}")
            if crop["tips"]:
                steps.append(f"Tips: {crop['tips']}")
        if weather:
            for adv in weather["advisories"]:
                steps.append(f"Weather advisory: {adv}")
        if not steps:
            if scheme:
                steps.append(
                    "Review the government scheme information below and check whether you "
                    "meet the eligibility conditions."
                )
            else:
                steps.append(
                    "Please share your crop, its age in days, and your location so I can "
                    "give specific advice."
                )

        # ── Assemble ──────────────────────────────────────────────────────────
        lines = ["Situation:", " ".join(situation_parts), "", "What you should do:"]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")

        if scheme:
            lines += ["", "Government scheme information:", scheme["summary"]]

        cautions = []
        if crop or weather:
            cautions.append(
                "This is general guidance from the crop knowledge base and live weather. "
                "Confirm pesticide or fertilizer dosage with your local Krishi Vigyan Kendra (KVK)."
            )
        if scheme:
            cautions.append(
                "Scheme details are retrieved from official documents; verify current "
                "eligibility and deadlines on the official government portal."
            )
        if cautions:
            lines += ["", "Important:"] + cautions

        if scheme and scheme["sources"]:
            lines += ["", "Source:", ", ".join(scheme["sources"])]

        return "\n".join(lines)


# ── Context-block parsers for StubLLM answer composition ──────────────────────
# These read ONLY what the tools injected into the prompt. If a block is a
# placeholder ("No weather data available.", etc.) the parser returns None so the
# stub never presents missing data as fact.

def _section(prompt: str, start_marker: str, end_marker: str) -> str:
    """Return the text between two markers in the prompt (empty if not found)."""
    start = prompt.find(start_marker)
    if start == -1:
        return ""
    start += len(start_marker)
    end = prompt.find(end_marker, start)
    return prompt[start:end if end != -1 else None].strip()


def _parse_crop(block: str) -> Optional[dict]:
    import re

    m = re.search(r"Crop\s+:\s+(.+)", block)
    if not m:  # placeholder / crop-not-found → nothing usable
        return None

    def grab(label: str) -> str:
        mm = re.search(rf"{label}\s+:\s+(.+)", block)
        return mm.group(1).strip() if mm else ""

    stage = ""
    ms = re.search(r"=== Current Stage:\s*(.+?)\s*===", block)
    if ms:
        stage = ms.group(1).strip()

    return {
        "name": m.group(1).strip(),
        "stage": stage,
        "irrigation": grab("Irrigation"),
        "fertilizer": grab("Fertilizer"),
        "watch_for": grab("Watch for"),
        "tips": grab("Tips"),
    }


def _parse_weather(block: str) -> Optional[dict]:
    import re

    if "Weather for " not in block:  # placeholder / unavailable → nothing usable
        return None

    loc = ""
    ml = re.search(r"Weather for (.+)", block)
    if ml:
        loc = ml.group(1).strip()

    temp = ""
    mt = re.search(r"Temperature\s*:\s*([\d.]+°C)", block)
    if mt:
        temp = mt.group(1)

    condition = ""
    mc = re.search(r"Condition\s*:\s*(.+)", block)
    if mc:
        condition = mc.group(1).strip()

    advisories = re.findall(r"•\s*(.+)", block)

    return {"location": loc, "temp": temp, "condition": condition, "advisories": advisories}


def _parse_scheme(block: str) -> Optional[dict]:
    import re

    if "(relevance:" not in block:  # placeholder / insufficient info → nothing usable
        return None

    sources: list[str] = []
    for name in re.findall(r"Source:\s*(.+?)\s*\(relevance", block):
        name = name.strip()
        if name and name not in sources:
            sources.append(name)

    m = re.search(r"\[1\] Source:.*?\)\n(.*?)(?:\n\n\[\d+\] Source:|\Z)", block, re.DOTALL)
    summary = (m.group(1).strip() if m else block).strip()
    if len(summary) > 700:
        summary = summary[:700].rsplit(" ", 1)[0] + " …"

    return {"sources": sources, "summary": summary}


def get_llm(device: str = "cpu", use_stub: bool = False) -> BaseLLM:
    if use_stub or USE_STUB_LLM:
        return StubLLM()
    if USE_HF_INFERENCE_API:
        return HuggingFaceInferenceAPILLM()
    return HuggingFaceLocalLLM(device=device)
