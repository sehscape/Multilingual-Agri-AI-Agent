"""LangChain tool-calling agent — the default agent engine (AGENT_BACKEND=langchain).

Implements the brief's "LangChain agents with tool-calling". The three farm
tools are registered as LangChain `Tool`s and a ReAct `AgentExecutor` runs a
reasoning loop: at every step the model picks which tool to call next (or that
it is done), LangChain executes the tool, and the observation is fed back.

Who makes the decisions:
  • StubLLM (CPU / free hosting) — a deterministic rule-based policy that speaks
    LangChain's ReAct protocol (see StubLLM._react_step). The AgentExecutor,
    tool calls and parsing are the real LangChain machinery.
  • A real LLM (local Qwen / Llama-3.1-8B / Gemma on a GPU) — the same agent is
    driven by the model's own reasoning, no code change.

ReAct (text protocol) is used rather than native function-calling so any text
LLM can drive it. `.run(state)` matches AgentOrchestrator, so the UI can switch
engines freely. If the loop errors or stalls (a small model may not follow the
format), it falls back to the deterministic orchestrator — never a broken reply.
"""
from __future__ import annotations

import time

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import Tool

from app.agents.answering import generate_answer
from app.agents.orchestrator import AgentOrchestrator
from app.agents.state import AgentState
from app.models.langchain_llm import LangChainLLMAdapter
from app.models.llm import BaseLLM, StubLLM
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REACT_PROMPT = PromptTemplate.from_template(
    """You are an agricultural assistant for Indian farmers. Answer the question by
using the tools below. Use a tool only when it adds real information.

{tools}

Use EXACTLY this format:

Question: the farmer's question
Thought: what you need and which tool helps
Action: one of [{tool_names}]
Action Input: the input to the tool
Observation: the tool's result
... (Thought/Action/Action Input/Observation may repeat)
Thought: I now have the information I need
Final Answer: the advice for the farmer

Begin.

Question: {input}
Thought:{agent_scratchpad}"""
)


def _build_tools(state: AgentState) -> list[Tool]:
    """Wrap the farm tools as LangChain Tools. Each closes over the request state
    so entities already extracted (crop, stage, location) are reused, and each
    records its result on the state for the answer step and the UI."""
    from app.tools.crop_tool import get_crop_context
    from app.tools.scheme_tool import get_scheme_context
    from app.tools.weather_tool import get_weather_context

    def crop_tool(tool_input: str) -> str:
        out = get_crop_context(state.crop or tool_input.strip() or None,
                               state.crop_stage_days)
        state.crop_data = {"context": out}
        return out

    def weather_tool(tool_input: str) -> str:
        location = state.location or tool_input.strip()
        if not location:
            out = ("Weather data not available: no location was provided. "
                   "Please ask the farmer to specify their village, city, or district.")
            state.weather_data = {"context": out}
            return out
        raw, summary = get_weather_context(location)
        state.weather_data = {"raw": raw, "context": summary}
        return summary

    def scheme_tool(tool_input: str) -> str:
        out = get_scheme_context(tool_input.strip() or state.english_text)
        state.scheme_docs = [{"context": out}]
        return out

    return [
        Tool(
            name="crop_knowledge",
            func=crop_tool,
            description=("Stage-by-stage advice for a crop: irrigation, fertiliser, "
                         "pests. Input: the crop name, e.g. 'wheat'."),
        ),
        Tool(
            name="weather_forecast",
            func=weather_tool,
            description=("Live weather and 3-day forecast with farming advisories. "
                         "Input: a place name, e.g. 'Pune'."),
        ),
        Tool(
            name="government_schemes",
            func=scheme_tool,
            description=("Searches official government agricultural scheme documents "
                         "(PM-KISAN, crop insurance, Kisan Credit Card, Soil Health "
                         "Card). Input: the farmer's question."),
        ),
    ]


class LangChainAgent:
    def __init__(self, llm: BaseLLM, max_iterations: int = 6) -> None:
        self.llm = llm
        self.max_iterations = max_iterations
        self._fallback = AgentOrchestrator(llm)

    def run(self, state: AgentState) -> AgentState:
        brain = ("rule-based ReAct policy" if isinstance(self.llm, StubLLM)
                 else getattr(self.llm, "model_id", type(self.llm).__name__))
        state.add_trace(f"LangChain ReAct agent (decisions: {brain})")
        tools = _build_tools(state)

        try:
            executor = AgentExecutor(
                agent=create_react_agent(LangChainLLMAdapter(inner=self.llm),
                                         tools, _REACT_PROMPT),
                tools=tools,
                max_iterations=self.max_iterations,
                handle_parsing_errors=True,
                return_intermediate_steps=True,
                verbose=False,
            )
            t0 = time.time()
            result = executor.invoke({"input": state.routing_text()})
            steps = result.get("intermediate_steps", [])
            for action, observation in steps:
                if action.tool == "_Exception":
                    state.add_trace("  LangChain: model output could not be parsed — retrying")
                    continue
                state.add_trace(f"  LangChain → {action.tool}('{str(action.tool_input)[:40]}') "
                                f"→ {len(str(observation))} chars")
            if "Agent stopped" in str(result.get("output", "")):
                raise RuntimeError("agent hit the iteration limit")
            state.add_trace(f"LangChain agent: {sum(a.tool != '_Exception' for a, _ in steps)} "
                            f"tool call(s) in {time.time() - t0:.1f}s")
        except Exception as exc:
            logger.warning("LangChain agent failed (%s) — using the sequential orchestrator.", exc)
            state.add_trace(f"LangChain agent stopped ({exc}); fell back to sequential orchestrator")
            return self._fallback.run(state)

        # Write the final structured answer from what the agent gathered, so the
        # output format is identical whichever engine ran.
        return generate_answer(state, self.llm)


def get_langchain_agent(llm: BaseLLM) -> LangChainAgent:
    return LangChainAgent(llm)
