"""Government scheme tool — Phase 7.

Lazy-loads the SchemeRAG instance on first call.
If the index hasn't been built yet, returns a clear message
so the agent can tell the farmer gracefully.
"""
from __future__ import annotations

from typing import Optional

from app.config import USE_STUB_RAG, RAG_MIN_SCORE, RAG_BACKEND, BM25_MIN_SCORE
from app.utils.logging import get_logger

logger = get_logger(__name__)

_rag = None  # lazy singleton

# Returned when retrieval finds no chunk above RAG_MIN_SCORE — the tool must not
# fabricate scheme details (spec §12 / §33 TEST 5).
_INSUFFICIENT_INFO = (
    "The available government scheme documents do not contain sufficient "
    "information to answer this question reliably. Please check the official "
    "scheme portal or your local agricultural office."
)


def _get_rag():
    global _rag
    if _rag is not None:
        return _rag

    if USE_STUB_RAG:
        logger.info("USE_STUB_RAG=true — skipping scheme index")
        return None

    try:
        if RAG_BACKEND == "bm25":
            # Lightweight keyword retriever — no torch / embeddings / faiss.
            from app.rag.keyword_retriever import KeywordSchemeRetriever
            rag = KeywordSchemeRetriever()
            rag.build()
            _rag = rag
            return _rag

        from app.rag.scheme_rag import SchemeRAG
        rag = SchemeRAG()
        if SchemeRAG.is_built():
            rag.load()
        else:
            # No prebuilt index (e.g. a fresh host, where the index is
            # git-ignored). Build it once from the committed scheme text files.
            logger.info("Scheme index not found — building it now (one-time first run)…")
            rag.build()
            rag.save()
        _rag = rag
        return _rag
    except Exception as exc:
        logger.error("Scheme index unavailable: %s", exc)
        return None


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
        if not results:
            return _INSUFFICIENT_INFO

        # Off-topic guard. faiss: cosine >= RAG_MIN_SCORE. bm25: the top hit must
        # match >= 2 distinct query terms (a single incidental rare-word match is
        # not "this scheme answers the question").
        if RAG_BACKEND == "bm25":
            top = results[0]
            if top.get("matched_terms", 0) < 2 or top.get("raw_score", 0.0) < BM25_MIN_SCORE:
                logger.info("Scheme (bm25): top matched=%s raw=%.2f — insufficient info.",
                            top.get("matched_terms"), top.get("raw_score", 0.0))
                return _INSUFFICIENT_INFO
            strong = [r for r in results if r["score"] >= RAG_MIN_SCORE]
        else:
            strong = [r for r in results if r["score"] >= RAG_MIN_SCORE]
            if not strong:
                top = max((r["score"] for r in results), default=0.0)
                logger.info("Scheme RAG: no chunk >= %.2f (best=%.2f) — insufficient info.",
                            RAG_MIN_SCORE, top)
                return _INSUFFICIENT_INFO

        return format_scheme_results(strong or results[:1])
    except Exception as exc:
        logger.error("Scheme RAG query failed: %s", exc)
        return "Could not retrieve scheme information at this time. Please try again."
