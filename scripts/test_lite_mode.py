"""Verify LITE_MODE runs the app without any heavy ML dependency.

LITE_MODE is what the free Render deploy uses (512 MB RAM). This checks:
  1. torch / transformers / faiss / sentence-transformers are never imported.
  2. The keyword scheme retriever picks the right scheme and refuses off-topic.
  3. The full typed pipeline (intent -> crop + weather + scheme -> answer -> TTS)
     runs end to end.

Run it with LITE_MODE forced on:
    LITE_MODE=true python scripts/test_lite_mode.py        (bash)
    $env:LITE_MODE="true"; python scripts/test_lite_mode.py  (PowerShell)
"""
import os
import sys
from pathlib import Path

os.environ["LITE_MODE"] = "true"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.logging import enable_utf8_console
enable_utf8_console()

import logging
logging.disable(logging.WARNING)

_fail = 0


def check(label, ok):
    global _fail
    if not ok:
        _fail += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")


def run():
    from app.config import LITE_MODE, RAG_BACKEND, USE_STUB_LLM, USE_STUB_TRANSLATION
    check("LITE_MODE on", LITE_MODE)
    check("RAG_BACKEND forced to bm25", RAG_BACKEND == "bm25")
    check("stub LLM + stub translation forced", USE_STUB_LLM and USE_STUB_TRANSLATION)

    # ── Scheme retrieval quality ─────────────────────────────────────────────
    from app.tools.scheme_tool import get_scheme_context
    cases = [
        ("How do I apply for PM-KISAN?", "Pm Kisan"),
        ("crop insurance premium under PMFBY", "Pm Fasal Bima Yojana"),
        ("Kisan Credit Card loan interest rate", "Kisan Credit Card"),
        ("soil health card testing", "Soil Health Card"),
    ]
    for q, want in cases:
        out = get_scheme_context(q)
        check(f"scheme: {q[:38]!r} -> {want}", want in out)

    for q in ("how to fix a tractor engine", "cheap laptop deals", "history of the roman empire"):
        out = get_scheme_context(q)
        check(f"off-topic refused: {q[:34]!r}", "do not contain sufficient" in out)

    # ── Full typed pipeline ─────────────────────────────────────────────────
    from app.ui.gradio_app import build_ui, _run_pipeline
    build_ui()
    out = _run_pipeline(
        None,
        "My wheat is 40 days old, will it rain in Pune, and any scheme for irrigation?",
        "Pune",
    )
    _, _, _, answer, audio, intent_box, _, _ = out
    check("all 3 tools routed (crop+weather+scheme)",
          all(t in intent_box for t in ("crop", "weather", "scheme")))
    check("answer generated", bool(answer) and len(answer) > 40)
    check("voice audio produced", bool(audio))

    # ── No heavy libs imported ──────────────────────────────────────────────
    heavy = [m for m in ("torch", "transformers", "sentence_transformers",
                         "faiss", "whisper", "langchain") if m in sys.modules]
    check(f"no heavy ML libs imported (found: {heavy or 'none'})", not heavy)

    print("\n" + "=" * 56)
    print("Result:", "ALL PASSED" if _fail == 0 else f"{_fail} FAILED")
    sys.exit(0 if _fail == 0 else 1)


if __name__ == "__main__":
    run()
