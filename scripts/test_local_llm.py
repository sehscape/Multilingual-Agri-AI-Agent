"""Verify the REAL open-source LLM runs locally on CPU (no GPU).

This is the "real brain" check: it uses the fast rule-based router for intent,
runs the crop tool, then generates the final answer with HuggingFaceLocalLLM
(a small open-source model, e.g. Qwen2.5-0.5B-Instruct) on the CPU.

First run downloads the model (~1 GB, one-time). Generation on CPU takes roughly
a minute — that is expected without a GPU.

Usage (from project root, venv active):
    python scripts/test_local_llm.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.config import LOCAL_LLM_MODEL_ID
from app.agents.state import AgentState
from app.agents.intent import extract_intent
from app.agents.orchestrator import get_orchestrator
from app.models.llm import StubLLM, HuggingFaceLocalLLM

QUERIES = [
    "My wheat crop is 40 days old, what fertilizer should I apply?",
    "How can I apply for PM-KISAN and what documents are needed?",
]


def run():
    print(f"Local LLM model: {LOCAL_LLM_MODEL_ID}")
    print("Loading model (first run downloads it ~1 GB)…\n")

    router = StubLLM()                        # fast, reliable intent routing
    answer_llm = HuggingFaceLocalLLM(device="cpu")   # real open-source brain
    orch = get_orchestrator(answer_llm)

    ok = True
    for q in QUERIES:
        print("-" * 60)
        print("Q:", q)
        s = extract_intent(AgentState(source_language="en", english_text=q), router)
        print(f"Routed intent: {s.intent} | crop={s.crop} stage={s.crop_stage_days}")
        t0 = time.time()
        s = orch.run(s)
        dt = time.time() - t0
        answer = s.english_answer or ""
        print(f"\nAnswer (generated on CPU in {dt:.1f}s):\n{answer}\n")
        # A real generation should be non-trivial and not the error fallback.
        if len(answer) < 40 or "do not have sufficient" in answer:
            print("[FAIL] answer looks empty or fell back to the error message.")
            ok = False
        else:
            print("[PASS] real LLM produced a substantive answer.")

    print("=" * 60)
    print("Result:", "ALL PASSED — real LLM works on CPU" if ok else "SOME CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    run()
