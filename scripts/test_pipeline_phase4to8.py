"""Phase 4→8 integration test: intent extraction → orchestrator → answer.

Unlike test_agent_phase8.py (which sets intent fields directly), this drives the
FULL dev-mode pipeline from an English query through StubLLM intent extraction
and on through the orchestrator, so it validates the spec's core agent contract:

  * §19-21  location + tool flags are extracted from the query
  * §22     the agent does NOT call unnecessary tools
            (a weather question must not trigger crop / RAG, etc.)
  * §12/§35 answers are grounded — scheme text always comes from retrieval,
            never fabricated

Note on spec §33 TEST 5 ("a scheme that does not exist yet"): retrieval scores
that query as highly on-topic (~0.50, similar to real scheme queries), so a
relevance threshold alone cannot reject it. Refusing a *topically related but
unanswerable* question is a faithfulness judgement made by the real LLM via the
FINAL_ANSWER_PROMPT. The stub is verified here only to stay retrieval-grounded.

Usage (from project root, venv active):
    python scripts/test_pipeline_phase4to8.py

Requires the scheme index:  python scripts/build_scheme_index.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.agents.state import AgentState
from app.agents.intent import extract_intent
from app.agents.orchestrator import get_orchestrator
from app.models.llm import get_llm

# Each case: the English query + which tools SHOULD run and expected extractions.
TEST_CASES = [
    {
        "label": "Weather only — must NOT call crop or scheme (spec §22)",
        "query": "What is today's weather in Nashik?",
        "expect": {"crop": False, "weather": True, "scheme": False},
        "expect_location": "Nashik",
    },
    {
        "label": "Scheme only — must NOT call crop or weather (spec §22)",
        "query": "What documents are needed to apply for PM-KISAN?",
        "expect": {"crop": False, "weather": False, "scheme": True},
    },
    {
        "label": "Crop advice only — must NOT call weather or scheme",
        "query": "My onion crop is 45 days old. What care should I take now?",
        "expect": {"crop": True, "weather": False, "scheme": False},
        "expect_crop": "onion",
        "expect_stage": 45,
    },
    {
        "label": "Multi-tool — crop + weather + scheme (spec §21)",
        "query": ("My wheat crop is 40 days old and heavy rain is expected in Pune. "
                  "What should I do and is there any scheme for irrigation?"),
        "expect": {"crop": True, "weather": True, "scheme": True},
        "expect_crop": "wheat",
        "expect_stage": 40,
        "expect_location": "Pune",
    },
    {
        "label": "Unanswerable-but-topical scheme — must stay grounded (spec §12/§33)",
        "query": "What new government scheme will be launched next month for my village?",
        "expect": {"crop": False, "weather": False, "scheme": True},
        "grounded_only": True,
    },
]


def _tool_ran(state):
    return {
        "crop": state.crop_data is not None,
        "weather": state.weather_data is not None,
        "scheme": bool(state.scheme_docs),
    }


def run():
    llm = get_llm(use_stub=True)
    orchestrator = get_orchestrator(llm)
    all_ok = True

    for tc in TEST_CASES:
        print(f"\n{'-'*64}")
        print(f"Test  : {tc['label']}")
        print(f"Query : {tc['query']}")

        state = AgentState(source_language="en", english_text=tc["query"])
        state = extract_intent(state, llm)
        print(f"Intent: {state.intent} | crop={state.crop} stage={state.crop_stage_days} "
              f"loc={state.location} | weather={state.needs_weather} "
              f"scheme={state.needs_scheme} crop_info={state.needs_crop_info}")

        state = orchestrator.run(state)
        ran = _tool_ran(state)

        checks = []

        # 1. Correct tool selection (the core Phase 8 contract)
        for tool, want in tc["expect"].items():
            checks.append((f"{tool} tool {'ran' if want else 'skipped'}", ran[tool] == want))

        # 2. Extraction assertions (location / crop / stage) where specified
        if "expect_location" in tc:
            checks.append((f"location={tc['expect_location']}", state.location == tc["expect_location"]))
        if "expect_crop" in tc:
            checks.append((f"crop={tc['expect_crop']}", state.crop == tc["expect_crop"]))
        if "expect_stage" in tc:
            checks.append((f"stage={tc['expect_stage']}", state.crop_stage_days == tc["expect_stage"]))

        # 3. Answer is non-empty
        checks.append(("answer non-empty", bool(state.english_answer and len(state.english_answer) > 20)))

        # 4. Groundedness: any scheme text must come from retrieval, never fabricated
        if ran["scheme"]:
            ctx = state.scheme_docs[0].get("context", "")
            grounded = ("(relevance:" in ctx) or ("do not contain sufficient" in ctx)
            checks.append(("scheme answer is retrieval-grounded", grounded))

        ok = all(v for _, v in checks)
        all_ok = all_ok and ok

        print(f"\nAnswer preview: {state.english_answer[:220]}"
              f"{'...' if len(state.english_answer) > 220 else ''}")
        print(f"\nTool trace:")
        for t in state.trace:
            print(f"  {t}")
        print("\n[" + ("PASS" if ok else "FAIL") + "]  "
              + " | ".join(f"{k}: {'ok' if v else 'FAIL'}" for k, v in checks))

    print(f"\n{'='*64}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    run()
