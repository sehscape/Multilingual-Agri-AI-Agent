"""Intent extraction — Phase 4.

Calls the LLM with INTENT_EXTRACTION_PROMPT and parses the JSON response
into AgentState fields. Gracefully falls back to intent="unknown" on
parse failure so the pipeline always continues.
"""
from __future__ import annotations

import json
import re

from app.agents.prompts import INTENT_EXTRACTION_PROMPT
from app.agents.state import AgentState
from app.models.llm import BaseLLM
from app.utils.logging import get_logger

logger = get_logger(__name__)


def extract_intent(state: AgentState, llm: BaseLLM) -> AgentState:
    """Populate intent fields on state by calling the LLM. Returns mutated state."""
    prompt = INTENT_EXTRACTION_PROMPT.format(english_query=state.english_text)

    try:
        raw = llm.generate(prompt)
        logger.info("Intent raw response: %.300s", raw)

        # Strip markdown code fences if LLM wraps the JSON
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in LLM response")

        data = json.loads(json_match.group())

        state.intent = data.get("intent", "unknown")
        state.crop = data.get("crop") or None
        state.crop_stage_days = data.get("crop_stage_days") or None
        # Only fill location from LLM if the user didn't supply one via the UI
        if not state.location:
            state.location = data.get("location") or None
        state.needs_weather = bool(data.get("needs_weather", False))
        state.needs_scheme = bool(data.get("needs_scheme", False))
        state.needs_crop_info = bool(data.get("needs_crop_info", False))

        state.add_trace(
            f"Intent: {state.intent} | crop: {state.crop} | "
            f"stage: {state.crop_stage_days}d | "
            f"weather={state.needs_weather} scheme={state.needs_scheme} crop_info={state.needs_crop_info}"
        )

    except Exception as e:
        logger.warning("Intent extraction failed (%s) — defaulting to unknown.", e)
        state.intent = "unknown"
        state.add_trace(f"Intent extraction failed: {e}")

    return state
