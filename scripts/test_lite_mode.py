"""Verify LITE_MODE runs the app without any heavy ML dependency.

LITE_MODE is what the free Render deploy uses (512 MB RAM). The heavy ML
libraries are BLOCKED for this whole test — exactly as they are absent on
Render — and then:
  1. The keyword scheme retriever picks the right scheme and refuses off-topic.
  2. The Lite screen: microphone hidden, typed-only note shown, language picker.
  3. The full typed pipeline (intent → LangChain agent → crop + weather + scheme
     → answer → TTS) runs end to end.

(LangChain itself is part of the Lite build — it is pure Python. Its optional
`transformers` import is simply skipped when transformers is unavailable.)

Run it (LITE_MODE is forced on by the script):
    python scripts/test_lite_mode.py

Importing this module has no side effects — the Lite host is only simulated
when it is run as a script, so it can't leak into other test runs.
"""
import builtins
import os
import sys
from pathlib import Path

# Packages that are not installed on the Render host.
_BLOCKED = {"torch", "torchaudio", "transformers", "sentence_transformers",
            "faiss", "whisper", "accelerate"}

_fail = 0


def _simulate_lite_host() -> None:
    """Force LITE_MODE and make the heavy ML packages unimportable, as on
    Render. Must run before anything from `app` is imported. No Groq key: this
    is the typed-English Lite build (scripts/test_voice_languages.py covers
    the Lite build with a key)."""
    os.environ["LITE_MODE"] = "true"
    os.environ["GROQ_API_KEY"] = ""
    real_import = builtins.__import__

    def no_heavy_import(name, *args, **kwargs):
        if name.split(".")[0] in _BLOCKED:
            raise ImportError(f"{name} is not installed on the LITE host (blocked by test)")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = no_heavy_import


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

    # ── Lite screen ─────────────────────────────────────────────────────────
    from app.ui.gradio_app import build_ui, _run_pipeline
    cfg = build_ui().get_config_file()
    comps = cfg["components"]
    mic = next(c for c in comps if "ag-mic" in (c.get("props", {}).get("elem_classes") or []))
    check("microphone hidden", mic["props"].get("visible") is False)
    lite_note = next((c for c in comps if c.get("type") == "html"
                      and "lightweight version" in str(c["props"].get("value", ""))), None)
    check("typed-only note shown", lite_note is not None and lite_note["props"].get("visible") is not False)
    check("language picker present",
          any("ag-lang" in (c.get("props", {}).get("elem_classes") or []) for c in comps))

    # ── Full typed pipeline (LangChain agent) ─────────────────────────────────
    out = _run_pipeline(
        None,
        "My wheat is 40 days old, will it rain in Pune, and any scheme for irrigation?",
        "Pune",
    )
    _, _, _, answer, audio, intent_box, _, trace = out
    check("all 3 tools routed (crop+weather+scheme)",
          all(t in intent_box for t in ("crop", "weather", "scheme")))
    check("answered by the LangChain agent", "LangChain ReAct agent" in trace)
    check("answer generated", bool(answer) and len(answer) > 40)
    check("voice audio produced", bool(audio))

    # ── Nothing heavy got in ────────────────────────────────────────────────
    heavy = [m for m in _BLOCKED if m in sys.modules]
    check(f"ran with heavy ML libs unavailable (loaded: {heavy or 'none'})", not heavy)

    print("\n" + "=" * 56)
    print("Result:", "ALL PASSED" if _fail == 0 else f"{_fail} FAILED")
    sys.exit(0 if _fail == 0 else 1)


if __name__ == "__main__":
    _simulate_lite_host()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from app.utils.logging import enable_utf8_console
    enable_utf8_console()

    import logging
    logging.disable(logging.WARNING)

    run()
