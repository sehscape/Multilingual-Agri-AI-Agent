"""Phase 9 — End-to-end English pipeline test.

The definitive integration test for the dev/stub pipeline. It drives real
English queries through the full chain:

    english_text → intent extraction → orchestrator (crop / weather / scheme) → answer

and verifies three things the spec (§19-22, §33, §36) requires:

  A. INTENT COVERAGE   — every intent type is produced and routed correctly,
                         and the agent never calls unnecessary tools.
  B. EDGE CASES        — missing location, unrecognised crop, and empty input
                         are handled gracefully and never crash the pipeline.
  C. TOOL SAFETY       — out-of-knowledge-base crops and off-topic scheme
                         queries return honest "no info" messages, never
                         fabricated facts.

Every case is wrapped so a raised exception is recorded as a FAIL (the "never
crashes" guarantee is itself under test) rather than aborting the run.

Usage (from project root, venv active):
    python scripts/test_e2e_phase9.py

Requires the scheme index:  python scripts/build_scheme_index.py
Uses live Open-Meteo for weather cases (needs network).
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.agents.state import AgentState
from app.agents.intent import extract_intent
from app.agents.orchestrator import get_orchestrator
from app.models.llm import get_llm
from app.tools.crop_tool import get_crop_context
from app.tools.scheme_tool import get_scheme_context

# ── Part A: intent coverage — (expected_intent, query, expected_tools) ────────
INTENT_CASES = [
    ("crop_advice",
     "My wheat crop is 40 days old, what should I do now?",
     {"crop": True, "weather": False, "scheme": False}),
    ("weather",
     "What is the weather in Nashik today?",
     {"crop": False, "weather": True, "scheme": False}),
    ("government_scheme",
     "How do I apply for PM-KISAN?",
     {"crop": False, "weather": False, "scheme": True}),
    ("fertilizer",
     "What fertilizer should I apply to my wheat crop at 40 days?",
     {"crop": True, "weather": False, "scheme": False}),
    ("irrigation",
     "How should I schedule irrigation for my onion crop at 45 days?",
     {"crop": True, "weather": False, "scheme": False}),
    ("pest_or_disease",
     "My tomato leaves have yellow spots and insects, what should I do?",
     {"crop": True, "weather": False, "scheme": False}),
    ("multiple",
     "My wheat is 40 days old, will it rain in Pune, and is there any irrigation scheme?",
     {"crop": True, "weather": True, "scheme": True}),
    ("general_farming",
     "How do I begin organic farming as a beginner?",
     {"crop": False, "weather": False, "scheme": False}),
    ("unknown",
     "",
     {"crop": False, "weather": False, "scheme": False}),
]


def _tools_ran(state):
    return {
        "crop": state.crop_data is not None,
        "weather": state.weather_data is not None,
        "scheme": bool(state.scheme_docs),
    }


class Runner:
    def __init__(self):
        self.llm = get_llm(use_stub=True)
        self.orch = get_orchestrator(self.llm)
        self.failures = 0
        self.total = 0

    def _report(self, label, checks):
        self.total += 1
        ok = all(v for _, v in checks)
        if not ok:
            self.failures += 1
        tag = "PASS" if ok else "FAIL"
        print(f"[{tag}] {label}")
        for name, v in checks:
            if not v:
                print(f"        ↳ FAILED CHECK: {name}")

    def _run(self, query):
        state = AgentState(source_language="en", english_text=query)
        state = extract_intent(state, self.llm)
        return self.orch.run(state)

    # ── Part A ────────────────────────────────────────────────────────────────
    def part_a(self):
        print("\n" + "=" * 64 + "\nPART A — Intent coverage & tool routing\n" + "=" * 64)
        for expected_intent, query, expected_tools in INTENT_CASES:
            label = f"intent={expected_intent:17s} q={query[:45]!r}"
            try:
                state = self._run(query)
                ran = _tools_ran(state)
                checks = [(f"intent == {expected_intent}", state.intent == expected_intent)]
                for tool, want in expected_tools.items():
                    checks.append((f"{tool} {'ran' if want else 'skipped'}", ran[tool] == want))
                checks.append(("answer non-empty", len(state.english_answer) > 20))
                if ran["scheme"]:
                    ctx = state.scheme_docs[0].get("context", "")
                    checks.append(("scheme grounded",
                                   "(relevance:" in ctx or "do not contain sufficient" in ctx))
                self._report(label, checks)
            except Exception:
                self.total += 1
                self.failures += 1
                print(f"[FAIL] {label}\n        ↳ EXCEPTION:\n{traceback.format_exc()}")

    # ── Part B ────────────────────────────────────────────────────────────────
    def part_b(self):
        print("\n" + "=" * 64 + "\nPART B — Edge cases (must degrade gracefully, never crash)\n" + "=" * 64)

        # B1: weather requested but no location given
        try:
            state = self._run("Will it rain tomorrow? Should I water the field?")
            ctx = (state.weather_data or {}).get("context", "").lower()
            self._report("B1 missing location → graceful weather skip", [
                ("weather tool ran", state.weather_data is not None),
                ("says 'no location'", "no location" in ctx),
                ("answer non-empty", len(state.english_answer) > 20),
            ])
        except Exception:
            self.total += 1; self.failures += 1
            print(f"[FAIL] B1\n{traceback.format_exc()}")

        # B2: crop mentioned but not in the knowledge base (stub can't resolve it)
        try:
            state = self._run("My banana crop is 30 days old, what fertilizer should I use?")
            self._report("B2 unrecognised crop → no crash, honest answer", [
                ("crop stays None (banana unknown)", state.crop is None),
                ("no exception / answer non-empty", len(state.english_answer) > 20),
            ])
        except Exception:
            self.total += 1; self.failures += 1
            print(f"[FAIL] B2\n{traceback.format_exc()}")

        # B3: empty input
        try:
            state = self._run("")
            self._report("B3 empty query → intent=unknown, graceful answer", [
                ("intent == unknown", state.intent == "unknown"),
                ("no tools called", _tools_ran(state) == {"crop": False, "weather": False, "scheme": False}),
                ("answer non-empty", len(state.english_answer) > 20),
            ])
        except Exception:
            self.total += 1; self.failures += 1
            print(f"[FAIL] B3\n{traceback.format_exc()}")

    # ── Part C ────────────────────────────────────────────────────────────────
    def part_c(self):
        print("\n" + "=" * 64 + "\nPART C — Tool safety (no fabrication)\n" + "=" * 64)

        try:
            out = get_crop_context("banana", 30)
            self._report("C1 out-of-KB crop → 'not in the knowledge base'", [
                ("honest not-found message", "not in the knowledge base" in out),
            ])
        except Exception:
            self.total += 1; self.failures += 1
            print(f"[FAIL] C1\n{traceback.format_exc()}")

        try:
            out = get_scheme_context("instructions to repair a diesel tractor gearbox")
            self._report("C2 off-topic scheme → 'insufficient information' guardrail", [
                ("refuses instead of fabricating", "do not contain sufficient" in out),
            ])
        except Exception:
            self.total += 1; self.failures += 1
            print(f"[FAIL] C2\n{traceback.format_exc()}")

    def run(self):
        self.part_a()
        self.part_b()
        self.part_c()
        print("\n" + "=" * 64)
        passed = self.total - self.failures
        print(f"Result: {passed}/{self.total} checks passed — "
              f"{'ALL PASSED' if self.failures == 0 else f'{self.failures} FAILED'}")
        sys.exit(0 if self.failures == 0 else 1)


if __name__ == "__main__":
    Runner().run()
