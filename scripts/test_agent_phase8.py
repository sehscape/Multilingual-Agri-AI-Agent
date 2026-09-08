"""Phase 8 smoke-test: Agent orchestrator end-to-end.

Sets intent fields directly on AgentState (bypasses StubLLM intent extraction)
to test each tool path independently. Uses StubLLM for answer generation only.

Usage (from project root, venv active):
    python scripts/test_agent_phase8.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.agents.state import AgentState
from app.agents.orchestrator import get_orchestrator
from app.models.llm import get_llm

PASS = "PASS"
FAIL = "FAIL"

TEST_CASES = [
    {
        "label": "Crop advice — wheat at 40 days",
        "english_text": "My wheat crop is 40 days old. What fertilizer should I apply?",
        "state_overrides": {
            "intent": "crop_advice",
            "crop": "wheat",
            "crop_stage_days": 40,
            "needs_crop_info": True,
        },
        "expect_crop_data": True,
        "expect_weather_data": False,
        "expect_scheme_docs": False,
    },
    {
        "label": "Weather query with location",
        "english_text": "Will it rain tomorrow in Pune? Should I irrigate my onion field?",
        "state_overrides": {
            "intent": "weather",
            "crop": "onion",
            "location": "Pune",
            "needs_weather": True,
            "needs_crop_info": True,
        },
        "expect_crop_data": True,
        "expect_weather_data": True,
        "expect_scheme_docs": False,
    },
    {
        "label": "Government scheme query",
        "english_text": "How can I apply for PM-KISAN? What documents do I need?",
        "state_overrides": {
            "intent": "government_scheme",
            "needs_scheme": True,
        },
        "expect_crop_data": False,
        "expect_weather_data": False,
        "expect_scheme_docs": True,
    },
    {
        "label": "Multi-intent — crop + weather + scheme",
        "english_text": "My cotton crop has pests. What is the weather in Nagpur? Are there any schemes to help?",
        "state_overrides": {
            "intent": "multiple",
            "crop": "cotton",
            "crop_stage_days": 40,
            "location": "Nagpur",
            "needs_crop_info": True,
            "needs_weather": True,
            "needs_scheme": True,
        },
        "expect_crop_data": True,
        "expect_weather_data": True,
        "expect_scheme_docs": True,
    },
    {
        "label": "Weather without location — graceful skip",
        "english_text": "Will it rain tomorrow? Should I spray pesticide?",
        "state_overrides": {
            "intent": "weather",
            "needs_weather": True,
            # no location set
        },
        "expect_crop_data": False,
        "expect_weather_data": True,   # still set, but with 'no location' message
        "expect_scheme_docs": False,
    },
]


def run():
    llm = get_llm(use_stub=True)
    orchestrator = get_orchestrator(llm)
    all_ok = True

    for tc in TEST_CASES:
        print(f"\n{'-'*60}")
        print(f"Test  : {tc['label']}")
        print(f"Query : {tc['english_text']}")

        state = AgentState(
            source_language="en",
            english_text=tc["english_text"],
        )
        # Apply overrides directly (simulates intent extraction output)
        for k, v in tc["state_overrides"].items():
            setattr(state, k, v)

        print(f"Intent: {state.intent} | crop={state.crop} | stage={state.crop_stage_days} | "
              f"loc={state.location} | weather={state.needs_weather} "
              f"scheme={state.needs_scheme} crop_info={state.needs_crop_info}")

        # Run orchestrator (tools + LLM answer)
        state = orchestrator.run(state)

        # Assertions
        checks = []
        if tc["expect_crop_data"]:
            ok = bool(state.crop_data and state.crop_data.get("context"))
            checks.append(("crop_data populated", ok))
        if tc["expect_weather_data"]:
            ok = bool(state.weather_data and state.weather_data.get("context"))
            checks.append(("weather_data populated", ok))
        if tc["expect_scheme_docs"]:
            ok = bool(state.scheme_docs and state.scheme_docs[0].get("context"))
            checks.append(("scheme_docs populated", ok))

        answer_ok = bool(state.english_answer and len(state.english_answer) > 20)
        checks.append(("english_answer non-empty", answer_ok))

        all_checks_ok = all(v for _, v in checks)
        tag = PASS if all_checks_ok else FAIL

        print(f"\nAnswer preview: {state.english_answer[:250]}{'...' if len(state.english_answer) > 250 else ''}")
        print(f"\nTool trace:")
        for t in state.trace:
            print(f"  {t}")
        check_str = " | ".join(f"{k}: {'ok' if v else 'FAIL'}" for k, v in checks)
        print(f"\n[{tag}]  {check_str}")

        if not all_checks_ok:
            all_ok = False

    print(f"\n{'='*60}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    run()
