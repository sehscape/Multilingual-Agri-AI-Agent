"""English answer generation — Phase 4.

Builds the FINAL_ANSWER_PROMPT from AgentState context (weather, crop,
scheme docs) and calls the LLM to produce an English answer.

In Phase 4, tool outputs are empty stubs — Phases 5-8 populate them.
"""
from __future__ import annotations

from app.agents.prompts import FINAL_ANSWER_PROMPT, NO_INFO_RESPONSE_EN
from app.agents.state import AgentState
from app.models.llm import BaseLLM
from app.utils.logging import get_logger

logger = get_logger(__name__)


def generate_answer(state: AgentState, llm: BaseLLM) -> AgentState:
    """Generate an English answer and store it in state.english_answer."""
    prompt = FINAL_ANSWER_PROMPT.format(
        english_query=state.english_text,
        weather_context=_fmt_weather(state),
        crop_context=_fmt_crop(state),
        scheme_context=_fmt_scheme(state),
    )

    try:
        state.english_answer = llm.generate(prompt).strip()
        state.add_trace("LLM answer generated.")
    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        state.english_answer = NO_INFO_RESPONSE_EN
        state.add_trace(f"LLM failed ({e}) — fallback response used.")

    return state


def _fmt_weather(state: AgentState) -> str:
    if not state.weather_data:
        return "Not available — Weather tool will be added in Phase 6."
    return str(state.weather_data)


def _fmt_crop(state: AgentState) -> str:
    if state.crop_data:
        return str(state.crop_data)
    # Fall back to live crop tool lookup if crop_data not pre-populated
    if state.crop or state.crop_stage_days:
        try:
            from app.tools.crop_tool import get_crop_context
            return get_crop_context(state.crop, state.crop_stage_days)
        except Exception as e:
            return f"Crop tool error: {e}"
    return "No crop information requested."


def _fmt_scheme(state: AgentState) -> str:
    if not state.scheme_docs:
        return "Not available — Government scheme RAG will be added in Phase 7."
    return "\n\n".join(str(d) for d in state.scheme_docs)
