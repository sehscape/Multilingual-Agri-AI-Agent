"""Phase 6 smoke-test: Weather tool via Open-Meteo.

Usage (from project root, venv active):
    python scripts/test_weather_phase6.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools.weather_tool import get_weather_context

TEST_LOCATIONS = [
    "Pune",           # known city (Marathi belt)
    "Ludhiana",       # known city (Punjabi belt)
    "Varanasi",       # known city (Hindi belt)
    "xyzabc123",      # unknown — should fail gracefully
    None,             # no location — should fail gracefully
]

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


def run():
    all_ok = True
    for loc in TEST_LOCATIONS:
        print(f"\n{'-'*60}")
        print(f"Location: {loc!r}")
        raw, summary = get_weather_context(loc)
        print(summary)
        if loc in ("xyzabc123", None):
            ok = raw is None and len(summary) > 10
            tag = PASS if ok else FAIL
            print(f"\n[{tag}] graceful failure path")
        else:
            ok = raw is not None and "Weather for" in summary
            tag = PASS if ok else FAIL
            print(f"\n[{tag}] successful fetch")
        if not ok:
            all_ok = False

    print(f"\n{'='*60}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    run()
