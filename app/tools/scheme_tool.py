"""Government scheme tool — Phase 7.

Lazy-loads the SchemeRAG instance on first call.
If the index hasn't been built yet, returns a clear message
so the agent can tell the farmer gracefully.
"""
from __future__ import annotations

from typing import Optional

from app.config import USE_STUB_RAG
from app.utils.logging import get_logger

logger = get_logger(__name__)

_rag = None  # lazy singleton


def _get_rag():
    global _rag
    if _rag is not None:
        return _rag

    if USE_STUB_RAG:
        logger.info("USE_STUB_RAG=true — skipping FAISS load")
        return None

    from app.rag.scheme_rag import SchemeRAG
    if not SchemeRAG.is_built():
        logger.warning("Scheme index not built. Run scripts/build_scheme_index.py.")
        return None

    _rag = SchemeRAG()
    _rag.load()
    return _rag


def get_scheme_context(query: Optional[str]) -> str:
    """
    Main entry point for the scheme tool.

    Takes an English query and returns a formatted string with relevant
    government scheme information, ready to include in the LLM prompt.
    """
    if not query:
        return "No scheme query provided."

    if USE_STUB_RAG:
        return (
            "Government scheme lookup is currently in stub mode. "
            "Build the index by running: python scripts/build_scheme_index.py"
        )

    rag = _get_rag()
    if rag is None:
        return (
            "Government scheme information is not available yet. "
            "The knowledge base index needs to be built first."
        )

    try:
        from app.rag.scheme_rag import format_scheme_results
        results = rag.query(query)
        return format_scheme_results(results)
    except Exception as exc:
        logger.error("Scheme RAG query failed: %s", exc)
        return "Could not retrieve scheme information at this time. Please try again."
