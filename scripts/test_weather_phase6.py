"""Phase 6 smoke-test: Weather tool via Open-Meteo.

Usage (from project root, venv active):
    python scripts/test_weather_phase6.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

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

    all_ok &= run_fallbacks()

    print(f"\n{'='*60}")
    print(f"Result: {'ALL PASSED' if all_ok else 'SOME TESTS FAILED'}")
    sys.exit(0 if all_ok else 1)


def run_fallbacks() -> bool:
    """Open-Meteo refusing (it rate-limits shared host IPs), both providers
    down, and the place lookup unreachable."""
    from app.tools import weather_tool as w

    print(f"\n{'-'*60}\nFallbacks")
    results = []

    def check(label, ok):
        print(f"[{PASS if ok else FAIL}] {label}")
        results.append(ok)

    real_om, real_met, real_search = w._fetch_forecast, w._fetch_met_norway, w._search_place
    try:
        w._forecasts.clear()
        w._fetch_forecast = lambda lat, lon: None
        raw, summary = get_weather_context("Nashik")
        check("Open-Meteo refused → MET Norway forecast, 3 days",
              raw is not None and raw["source"] == "MET Norway"
              and "Forecast source: MET Norway" in summary and summary.count("°C, Rain:") == 3)
        check("no rain probability from MET → none invented", "% chance" not in summary)

        w._forecasts.clear()
        w._fetch_met_norway = lambda lat, lon: None
        raw, summary = get_weather_context("Pune")
        check("both providers down → 'temporarily unavailable'",
              raw is None and "temporarily unavailable" in summary)

        def unreachable(name):
            raise ConnectionError("network down")
        w._search_place = unreachable
        raw, summary = get_weather_context("Satara")
        check("place lookup unreachable → service down, not 'place not found'",
              raw is None and "temporarily unavailable" in summary and "Satara" not in w._places)
    finally:
        w._fetch_forecast, w._fetch_met_norway, w._search_place = real_om, real_met, real_search
        w._forecasts.clear()
    return all(results)


if __name__ == "__main__":
    run()
