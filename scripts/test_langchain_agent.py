"""LangChain agent test — the default agent engine (AGENT_BACKEND=langchain).

Checks that the LangChain ReAct AgentExecutor:
  1. calls exactly the right tools for all 9 intent types (spec §22 — no
     unnecessary tool calls), driven by the rule-based ReAct policy;
  2. produces an answer for every question;
  3. falls back to the deterministic orchestrator when the model can't follow
     the ReAct format, or loops without finishing — never a broken reply;
  4. is the engine the UI actually uses by default.

Usage (from project root, venv active):
    python scripts/test_langchain_agent.py

Weather cases need internet (Open-Meteo); scheme cases need the FAISS index.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

import logging
logging.disable(logging.WARNING)

from app.agents.intent import extract_intent
from app.agents.langchain_agent import LangChainAgent, get_langchain_agent
from app.agents.state import AgentState
from app.models.llm import BaseLLM, StubLLM

CROP, WEATHER, SCHEME = "crop_knowledge", "weather_forecast", "government_schemes"

CASES = [
    ("crop_advice", "My wheat crop is 40 days old, what should I do now?", {CROP}),
    ("weather", "What is the weather in Nashik today?", {WEATHER}),
    ("government_scheme", "How do I apply for PM-KISAN?", {SCHEME}),
    ("fertilizer", "What fertilizer should I apply to my wheat crop at 40 days?", {CROP}),
    ("irrigation", "How should I schedule irrigation for my onion crop at 45 days?", {CROP}),
    ("pest_or_disease", "My tomato leaves have yellow spots and insects, what should I do?", {CROP}),
    ("multiple", "My wheat is 40 days old, will it rain in Pune, and is there any "
                 "irrigation scheme?", {CROP, WEATHER, SCHEME}),
    ("general_farming", "How do I begin organic farming as a beginner?", set()),
    ("unknown", "", set()),
]

_failures = 0
_total = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global _failures, _total
    _total += 1
    _failures += 0 if ok else 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail and not ok else ""))


def tools_called(state: AgentState) -> set:
    return {m.group(1) for line in state.trace
            if (m := re.search(r"LangChain → (\w+)\(", line))}


def run_agent(question: str, llm: BaseLLM) -> AgentState:
    state = extract_intent(AgentState(source_language="en", english_text=question), StubLLM())
    return LangChainAgent(llm).run(state)


class NoReActLLM(StubLLM):
    """Writes answers fine but never follows the ReAct format."""
    def generate(self, prompt: str) -> str:
        if "Action Input:" in prompt:
            return "I think the farmer should water the crop."
        return super().generate(prompt)


class LoopingLLM(StubLLM):
    """Keeps calling a tool and never finishes."""
    def generate(self, prompt: str) -> str:
        if "Action Input:" in prompt:
            return " Let me check again.\nAction: crop_knowledge\nAction Input: wheat"
        return super().generate(prompt)


def main() -> None:
    llm = StubLLM()

    print("=" * 64 + "\n1. Tool selection for every intent (LangChain ReAct loop)\n" + "=" * 64)
    for intent, question, expected in CASES:
        state = run_agent(question, llm)
        called = tools_called(state)
        check(f"{intent:18s} → {sorted(called) or 'no tools'}", called == expected,
              f"expected {sorted(expected)}")
        check(f"{intent:18s} answered", len(state.english_answer) > 20)
        check(f"{intent:18s} ran through LangChain",
              any("LangChain ReAct agent" in line for line in state.trace))

    print("\n" + "=" * 64 + "\n2. Resilience — falls back instead of failing\n" + "=" * 64)
    state = run_agent("My wheat crop is 40 days old, what fertilizer?", NoReActLLM())
    check("model ignores ReAct format → fallback", any("fell back" in l for l in state.trace))
    check("model ignores ReAct format → still answers", len(state.english_answer) > 20)

    state = run_agent("My wheat crop is 40 days old, what fertilizer?", LoopingLLM())
    check("model loops forever → fallback", any("fell back" in l for l in state.trace))
    check("model loops forever → still answers", len(state.english_answer) > 20)

    print("\n" + "=" * 64 + "\n3. The UI uses the LangChain agent by default\n" + "=" * 64)
    from app.config import AGENT_BACKEND
    from app.ui.gradio_app import _get_orchestrator
    check("AGENT_BACKEND defaults to 'langchain'", AGENT_BACKEND == "langchain", AGENT_BACKEND)
    check("UI engine is LangChainAgent", isinstance(_get_orchestrator(), LangChainAgent),
          type(_get_orchestrator()).__name__)
    check("factory returns LangChainAgent", isinstance(get_langchain_agent(llm), LangChainAgent))

    print("\n" + "=" * 64)
    passed = _total - _failures
    print(f"Result: {passed}/{_total} checks passed — "
          f"{'ALL PASSED' if _failures == 0 else f'{_failures} FAILED'}")
    sys.exit(0 if _failures == 0 else 1)


if __name__ == "__main__":
    main()
