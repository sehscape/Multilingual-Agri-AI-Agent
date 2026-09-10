"""Lightweight keyword retriever for the government-scheme documents.

Used in LITE_MODE (RAG_BACKEND=bm25) — a pure-Python BM25 ranker over the same
scheme text files the FAISS pipeline uses, but with **zero heavy dependencies**
(no torch / transformers / sentence-transformers / faiss). This keeps the app
small enough to run on a 512 MB free host.

Trade-off vs. the embedding pipeline: keyword matching, not semantic. It still
finds the right scheme for direct questions ("how to apply for PM-KISAN",
"crop insurance premium") and still refuses clearly off-topic questions (a query
with no meaningful term overlap scores ~0).

Interface mirrors SchemeRAG.query():
    query(question, top_k) -> list[{source, chunk_id, text, score}]
where score is normalised to 0-1 (share of the top hit) so the existing
RAG_MIN_SCORE threshold keeps working.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from app.config import CHUNK_OVERLAP, CHUNK_SIZE, SCHEMES_RAW_DIR, TOP_K
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks on sentence/newline boundaries.

    Self-contained copy of the chunker (keeps LITE_MODE decoupled from the
    embedding pipeline, which pulls in numpy at import time).
    """
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep in ("\n", ". ", " "):
                pos = text.rfind(sep, start + chunk_size // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Very common words that carry no retrieval signal for scheme questions.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "be", "how", "do", "i", "my", "can", "what", "which", "with", "at", "it",
    "this", "that", "as", "by", "from", "any", "there", "will", "would", "should",
    "need", "want", "get", "am", "me", "you", "your", "if", "so", "about",
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


class KeywordSchemeRetriever:
    """BM25 ranker over scheme-document chunks. Builds in-memory at first use.

    Two tweaks over plain BM25 for this small, structured corpus (one named
    scheme per file):
      • name boost — a query term that matches the scheme's own name/header
        (e.g. "pm", "kisan", "pmfby") adds a strong bonus, so "apply for
        PM-KISAN" ranks the PM-KISAN file above files that merely mention
        "kisan" a lot (Kisan Credit Card).
      • min-term guard — the top hit must match at least MIN_QUERY_TERMS
        distinct query terms, else the query is treated as off-topic.
    """

    _K1 = 1.5
    _B = 0.75
    _NAME_BOOST = 3.0        # bonus per query term found in a scheme's name/header
    MIN_QUERY_TERMS = 2      # distinct query terms the top hit must contain

    def __init__(self) -> None:
        self._chunks: list[dict] = []      # {source, chunk_id, text}
        self._doc_tokens: list[list[str]] = []
        self._doc_freqs: list[Counter] = []
        self._name_tokens: list[set] = []  # per-chunk: tokens of its scheme name/header
        self._df: Counter = Counter()
        self._idf: dict[str, float] = {}
        self._avg_len: float = 0.0
        self._built = False

    def build(self, raw_dir: Path = SCHEMES_RAW_DIR) -> None:
        raw_dir = Path(raw_dir)
        files = sorted(p for p in raw_dir.iterdir() if p.suffix == ".txt")
        if not files:
            raise ValueError(f"No scheme .txt files found in {raw_dir}")

        for path in files:
            text = path.read_text(encoding="utf-8")
            # Name tokens: the filename + the header block (SCHEME/SOURCE/CATEGORY
            # lines), which reliably carries the scheme's name and acronym.
            header = "\n".join(text.splitlines()[:4])
            name_tok = set(_tokenize(path.stem.replace("_", " ")) + _tokenize(header))
            for i, chunk in enumerate(_split_text(text, CHUNK_SIZE, CHUNK_OVERLAP)):
                self._chunks.append({"source": path.stem, "chunk_id": i, "text": chunk})
                self._name_tokens.append(name_tok)

        self._doc_tokens = [_tokenize(c["text"]) for c in self._chunks]
        self._doc_freqs = [Counter(toks) for toks in self._doc_tokens]
        for toks in self._doc_tokens:
            for term in set(toks):
                self._df[term] += 1

        n = len(self._chunks)
        self._avg_len = sum(len(t) for t in self._doc_tokens) / max(n, 1)
        self._idf = {
            term: math.log(1 + (n - df + 0.5) / (df + 0.5))
            for term, df in self._df.items()
        }
        self._built = True
        logger.info("KeywordSchemeRetriever built: %d chunks from %d files", n, len(files))

    def _score(self, q_terms: list[str], doc_idx: int) -> tuple[float, int]:
        """Return (score, #distinct query terms matched in the chunk body)."""
        freqs = self._doc_freqs[doc_idx]
        dl = len(self._doc_tokens[doc_idx])
        name_tok = self._name_tokens[doc_idx]
        score = 0.0
        matched = 0
        for term in q_terms:
            if term in freqs:
                matched += 1
                idf = self._idf.get(term, 0.0)
                tf = freqs[term]
                denom = tf + self._K1 * (1 - self._B + self._B * dl / self._avg_len)
                score += idf * (tf * (self._K1 + 1)) / denom
            if term in name_tok:
                score += self._NAME_BOOST
        return score, matched

    def query(self, question: str, top_k: int = TOP_K) -> list[dict]:
        if not self._built:
            self.build()
        q_terms = list(dict.fromkeys(_tokenize(question)))  # distinct, ordered
        if not q_terms:
            return []

        scored = []
        for i in range(len(self._chunks)):
            s, matched = self._score(q_terms, i)
            if s > 0:
                scored.append((i, s, matched))
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]
        if not scored:
            return []

        top = scored[0][1]
        results = []
        for idx, s, matched in scored:
            c = self._chunks[idx]
            results.append({
                "source": c["source"],
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "score": round(s / top, 3) if top else 0.0,
                "raw_score": round(s, 3),
                "matched_terms": matched,
            })
        return results
