"""Phase 7 smoke-test: Government scheme RAG.

Usage (from project root, venv active):
    python scripts/test_scheme_phase7.py

Requires the index to be built first:
    python scripts/build_scheme_index.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

from app.rag.scheme_rag import SchemeRAG, format_scheme_results

PASS = "PASS"
FAIL = "FAIL"

QUERIES = [
    ("PM-KISAN eligibility", "PM-KISAN eligibility and who can apply"),
    ("crop insurance claim", "How to file a crop insurance claim after flood damage"),
    ("KCC interest rate", "What is the interest rate on Kisan Credit Card loan"),
    ("soil health card", "How to get a soil health card and what nutrients are tested"),
    ("government scheme for wheat farmer", "government scheme benefits for wheat farmers"),
]


def run():
    rag = SchemeRAG()
    if not SchemeRAG.is_built():
        print("ERROR: Index not built. Run: python scripts/build_scheme_index.py")
        sys.exit(1)

    rag.load()
    all_ok = True

    for label, query in QUERIES:
        print(f"\n{'-'*60}")
        print(f"Query: {query}")
        results = rag.query(query, top_k=3)
        formatted = format_scheme_results(results)
        print(formatted[:600], "..." if len(formatted) > 600 else "")
        ok = len(results) > 0 and all(r["score"] > 0 for r in results)
        tag = PASS if ok else FAIL
        print(f"\n[{tag}] {label} — got {len(results)} result(s)")
        if not ok:
            all_ok = False

    print(f"\n{'='*60}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    run()
