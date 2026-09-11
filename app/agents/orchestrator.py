"""Agent orchestrator — Phase 8.

Takes an AgentState with intent fields already populated (by Phase 4 intent extraction)
and decides which tools to call, runs them, then generates the final English answer.

Tool call order:
  1. Crop knowledge tool  (if needs_crop_info and crop name known)
  2. Weather tool         (if needs_weather and location provided)
  3. Scheme RAG tool      (if needs_scheme)
  4. LLM answer generation (always — using whatever tool outputs are available)

The orchestrator is intentionally sequential (not ReAct-loop) because:
  - Intent extraction already determined which tools are needed.
  - Sequential order is deterministic, fast, and avoids hallucination from loop.
  - Multi-intent queries ("weather + crop advice") are handled naturally.
"""
from __future__ import annotations

import time

from app.agents.answering import generate_answer
from app.agents.state import AgentState
from app.models.llm import BaseLLM
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    def __init__(self, llm: BaseLLM) -> None:
        self.llm = llm

    def run(self, state: AgentState) -> AgentState:
        """Run all required tools then generate the final English answer."""
        state = self._run_tools(state)
        state = generate_answer(state, self.llm)
        return state

    # ── Private tool runners ────────────────────────────────────────────────────

    def _run_tools(self, state: AgentState) -> AgentState:
        # Always try crop tool if any crop or stage info is present
        if state.needs_crop_info or state.crop or state.crop_stage_days:
            state = self._run_crop_tool(state)

        if state.needs_weather:
            state = self._run_weather_tool(state)

        if state.needs_scheme:
            state = self._run_scheme_tool(state)

        return state

    def _run_crop_tool(self, state: AgentState) -> AgentState:
        from app.tools.crop_tool import get_crop_context
        t0 = time.time()
        try:
            context = get_crop_context(state.crop, state.crop_stage_days)
            state.crop_data = {"context": context}
            state.add_trace(
                f"Crop tool: {state.crop or '?'} @ {state.crop_stage_days or '?'}d "
                f"→ {len(context)} chars ({time.time()-t0:.1f}s)"
            )
        except Exception as exc:
            logger.error("Crop tool error: %s", exc)
            state.crop_data = {"context": f"Crop tool error: {exc}"}
            state.add_trace(f"Crop tool failed: {exc}")
        return state

    def _run_weather_tool(self, state: AgentState) -> AgentState:
        from app.tools.weather_tool import get_weather_context
        t0 = time.time()
        if not state.location:
            state.weather_data = {
                "context": (
                    "Weather data not available: no location was provided. "
                    "Please ask the farmer to specify their village, city, or district."
                )
            }
            state.add_trace("Weather tool: skipped — no location in state")
            return state
        try:
            raw, summary = get_weather_context(state.location)
            state.weather_data = {"raw": raw, "context": summary}
            state.add_trace(
                f"Weather tool: {state.location} → {len(summary)} chars ({time.time()-t0:.1f}s)"
            )
        except Exception as exc:
            logger.error("Weather tool error: %s", exc)
            state.weather_data = {"context": f"Weather tool error: {exc}"}
            state.add_trace(f"Weather tool failed: {exc}")
        return state

    def _run_scheme_tool(self, state: AgentState) -> AgentState:
        from app.tools.scheme_tool import get_scheme_context
        t0 = time.time()
        query = (state.scheme_query or state.english_text
                 or "government agricultural scheme information")
        try:
            context = get_scheme_context(query)
            state.scheme_docs = [{"context": context}]
            state.add_trace(
                f"Scheme RAG: query='{query[:60]}' → {len(context)} chars ({time.time()-t0:.1f}s)"
            )
        except Exception as exc:
            logger.error("Scheme tool error: %s", exc)
            state.scheme_docs = [{"context": f"Scheme tool error: {exc}"}]
            state.add_trace(f"Scheme tool failed: {exc}")
        return state


def get_orchestrator(llm: BaseLLM) -> AgentOrchestrator:
    return AgentOrchestrator(llm)
