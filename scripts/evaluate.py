"""Phase 12 — Evaluation framework.

A small, reproducible eval harness over the dev pipeline (spec §39). It reports
quantitative metrics rather than pass/fail assertions:

  1. Intent classification accuracy      (label matches expectation)
  2. Agent tool-selection accuracy       (right tools, no unnecessary calls)
  3. RAG retrieval quality               (top-1 source correctness + mean score)
  4. RAG safety                          (off-topic queries correctly refused)
  5. Answer quality                      (grounded / actionable / cited)

Exits non-zero only if a headline metric falls below a sane floor, so it can
double as a CI gate.

Usage (from project root, venv active):
    python scripts/evaluate.py

Uses the FAISS scheme index (build it first). Network-free: the labelled set
uses only intent extraction + crop/scheme paths (no live weather calls).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

import logging
logging.disable(logging.WARNING)  # keep the report clean

from app.agents.state import AgentState
from app.agents.intent import extract_intent
from app.agents.orchestrator import get_orchestrator
from app.models.llm import get_llm
from app.tools.scheme_tool import get_scheme_context
from app.rag.scheme_rag import SchemeRAG

# ── Labelled data ─────────────────────────────────────────────────────────────
# (query, expected_intent, {weather, scheme, crop})
INTENT_SET = [
    ("My wheat crop is 40 days old, what should I do now?", "crop_advice",
     {"weather": False, "scheme": False, "crop": True}),
    ("What fertilizer should I apply to my wheat at 40 days?", "fertilizer",
     {"weather": False, "scheme": False, "crop": True}),
    ("How should I schedule irrigation for my onion at 45 days?", "irrigation",
     {"weather": False, "scheme": False, "crop": True}),
    ("My tomato leaves have yellow spots and insects, what to do?", "pest_or_disease",
     {"weather": False, "scheme": False, "crop": True}),
    ("What is the weather in Nashik today?", "weather",
     {"weather": True, "scheme": False, "crop": False}),
    ("Will it rain in Pune tomorrow?", "weather",
     {"weather": True, "scheme": False, "crop": False}),
    ("How do I apply for PM-KISAN?", "government_scheme",
     {"weather": False, "scheme": True, "crop": False}),
    ("What is the premium for crop insurance under PMFBY?", "government_scheme",
     {"weather": False, "scheme": True, "crop": False}),
    ("My wheat is 40 days old, will it rain in Pune, any irrigation scheme?", "multiple",
     {"weather": True, "scheme": True, "crop": True}),
    ("How do I begin organic farming as a beginner?", "general_farming",
     {"weather": False, "scheme": False, "crop": False}),
]

# (query, expected_scheme_source_stem)
RAG_SET = [
    ("PM-KISAN eligibility and how to apply", "pm_kisan"),
    ("crop insurance premium rate and claim process", "pm_fasal_bima_yojana"),
    ("Kisan Credit Card interest rate and loan limit", "kisan_credit_card"),
    ("soil health card nutrient testing parameters", "soil_health_card"),
]

OFF_TOPIC = [
    "how to repair a diesel tractor gearbox",
    "best smartphone under 20000 rupees",
]

# (query, needs_scheme) — answer-quality subset (crop + scheme only, no network)
ANSWER_SET = [
    ("My wheat crop is 40 days old, what fertilizer should I apply?", False),
    ("My onion crop is 45 days old, what care should I take?", False),
    ("How do I apply for PM-KISAN and what documents are needed?", True),
    ("What is the premium under PMFBY crop insurance?", True),
]


def _pct(n, d):
    return 100.0 * n / d if d else 0.0


def _tools_ran(state):
    return {
        "crop": state.crop_data is not None,
        "weather": state.weather_data is not None,
        "scheme": bool(state.scheme_docs),
    }


def main():
    llm = get_llm(use_stub=True)
    orch = get_orchestrator(llm)
    rag = SchemeRAG(); rag.load()

    print("=" * 64)
    print("EVALUATION REPORT — Farmer Advisory Voice Agent (dev/stub)")
    print("=" * 64)

    # ── 1 & 2: intent + tool selection ────────────────────────────────────────
    intent_hits = 0
    routing_hits = 0
    unnecessary = 0
    for query, exp_intent, exp_flags in INTENT_SET:
        s = extract_intent(AgentState(source_language="en", english_text=query), llm)
        got_flags = {"weather": s.needs_weather, "scheme": s.needs_scheme,
                     "crop": s.needs_crop_info or s.crop is not None}
        if s.intent == exp_intent:
            intent_hits += 1
        if got_flags == exp_flags:
            routing_hits += 1
        # count tools requested that were not expected
        unnecessary += sum(1 for k in exp_flags if got_flags[k] and not exp_flags[k])

    n = len(INTENT_SET)
    intent_acc = _pct(intent_hits, n)
    routing_acc = _pct(routing_hits, n)
    print(f"\n1. Intent classification accuracy : {intent_acc:5.1f}%  ({intent_hits}/{n})")
    print(f"2. Tool-selection accuracy        : {routing_acc:5.1f}%  ({routing_hits}/{n})")
    print(f"   Unnecessary tool requests      : {unnecessary}")

    # ── 3 & 4: RAG retrieval + safety ─────────────────────────────────────────
    rag_hits = 0
    scores = []
    for query, exp_src in RAG_SET:
        res = rag.query(query, top_k=1)
        top = res[0] if res else None
        if top:
            scores.append(top["score"])
            if top["source"] == exp_src:
                rag_hits += 1
    rag_acc = _pct(rag_hits, len(RAG_SET))
    mean_score = sum(scores) / len(scores) if scores else 0.0
    print(f"\n3. RAG top-1 source accuracy      : {rag_acc:5.1f}%  ({rag_hits}/{len(RAG_SET)})")
    print(f"   Mean top-1 relevance           : {mean_score:.3f}")

    refused = sum(1 for q in OFF_TOPIC if "do not contain sufficient" in get_scheme_context(q))
    refuse_acc = _pct(refused, len(OFF_TOPIC))
    print(f"4. RAG off-topic refusal          : {refuse_acc:5.1f}%  ({refused}/{len(OFF_TOPIC)})")

    # ── 5: answer quality ─────────────────────────────────────────────────────
    grounded = actionable = cited = 0
    n_scheme = 0
    for query, needs_scheme in ANSWER_SET:
        s = AgentState(source_language="en", english_text=query)
        s = orch.run(extract_intent(s, llm))
        ans = s.english_answer or ""
        if len(ans) > 20:
            grounded += 1
        if "What you should do" in ans:
            actionable += 1
        if needs_scheme:
            n_scheme += 1
            if "Source:" in ans:
                cited += 1
    na = len(ANSWER_SET)
    print(f"\n5. Answer quality")
    print(f"   Non-empty / grounded           : {_pct(grounded, na):5.1f}%  ({grounded}/{na})")
    print(f"   Actionable (has step list)     : {_pct(actionable, na):5.1f}%  ({actionable}/{na})")
    print(f"   Scheme answers cite a source   : {_pct(cited, n_scheme):5.1f}%  ({cited}/{n_scheme})")

    # ── Verdict (soft CI gate) ────────────────────────────────────────────────
    print("\n" + "=" * 64)
    floors = {
        "intent accuracy ≥ 80%": intent_acc >= 80,
        "tool selection ≥ 90%": routing_acc >= 90,
        "no unnecessary tools": unnecessary == 0,
        "RAG top-1 ≥ 75%": rag_acc >= 75,
        "off-topic refusal = 100%": refuse_acc >= 100,
        "answers actionable ≥ 75%": _pct(actionable, na) >= 75,
    }
    for name, ok in floors.items():
        print(f"  [{'OK' if ok else 'LOW'}] {name}")
    passed = all(floors.values())
    print(f"\nOverall: {'HEALTHY ✅' if passed else 'NEEDS ATTENTION ⚠️'}")
    print("=" * 64)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
