"""Government scheme RAG pipeline — Phase 7.

Pipeline:
  Raw files (.txt / .pdf) in data/schemes/raw/
    → load text
    → split into overlapping chunks
    → embed with SentenceTransformer
    → build FAISS index
    → save index + metadata to data/vectorstore/

Query path:
  English question → embed → FAISS similarity search → top-K chunks with source info
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np

from app.config import CHUNK_OVERLAP, CHUNK_SIZE, SCHEMES_RAW_DIR, TOP_K, VECTORSTORE_PATH
from app.models.embeddings import BaseEmbeddings, get_embeddings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_INDEX_FILE = Path(VECTORSTORE_PATH) / "schemes.faiss"
_META_FILE = Path(VECTORSTORE_PATH) / "schemes_meta.json"


def _load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_pdf(path: Path) -> str:
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception as exc:
        logger.warning("Could not read PDF %s: %s", path.name, exc)
        return ""


def _load_raw_files(raw_dir: Path) -> list[dict]:
    """Return list of {source, text} dicts for all .txt and .pdf files."""
    docs = []
    for path in sorted(raw_dir.iterdir()):
        if path.suffix == ".txt":
            text = _load_txt(path)
        elif path.suffix == ".pdf":
            text = _load_pdf(path)
        else:
            continue
        if text.strip():
            docs.append({"source": path.stem, "text": text})
            logger.info("Loaded %s (%d chars)", path.name, len(text))
    return docs


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks on sentence/newline boundaries where possible."""
    # Normalise whitespace
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at a newline or period near the end
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


class SchemeRAG:
    def __init__(self, embeddings: Optional[BaseEmbeddings] = None) -> None:
        self._embeddings = embeddings or get_embeddings()
        self._index = None          # faiss.Index
        self._chunks: list[dict] = []  # [{source, text, chunk_id}]

    # ── Build ──────────────────────────────────────────────────────────────────

    def build(self, raw_dir: Path = SCHEMES_RAW_DIR) -> None:
        """Load raw files, chunk, embed, and build a FAISS index in memory."""
        import faiss

        docs = _load_raw_files(raw_dir)
        if not docs:
            raise ValueError(f"No .txt or .pdf files found in {raw_dir}")

        self._chunks = []
        for doc in docs:
            for i, chunk_text in enumerate(
                _split_text(doc["text"], CHUNK_SIZE, CHUNK_OVERLAP)
            ):
                self._chunks.append(
                    {"source": doc["source"], "chunk_id": i, "text": chunk_text}
                )

        logger.info("Total chunks: %d", len(self._chunks))

        texts = [c["text"] for c in self._chunks]
        vectors = np.array(self._embeddings.embed_documents(texts), dtype="float32")
        faiss.normalize_L2(vectors)

        dim = vectors.shape[1]
        self._index = faiss.IndexFlatIP(dim)  # Inner Product = cosine after normalisation
        self._index.add(vectors)
        logger.info("FAISS index built with %d vectors (dim=%d)", len(texts), dim)

    # ── Persist ────────────────────────────────────────────────────────────────

    def save(self, index_file: Path = _INDEX_FILE, meta_file: Path = _META_FILE) -> None:
        import faiss
        index_file.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(index_file))
        meta_file.write_text(json.dumps(self._chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved index → %s | metadata → %s", index_file, meta_file)

    def load(self, index_file: Path = _INDEX_FILE, meta_file: Path = _META_FILE) -> None:
        import faiss
        if not index_file.exists() or not meta_file.exists():
            raise FileNotFoundError(
                f"Index files not found. Run scripts/build_scheme_index.py first.\n"
                f"  Expected: {index_file}\n           {meta_file}"
            )
        self._index = faiss.read_index(str(index_file))
        self._chunks = json.loads(meta_file.read_text(encoding="utf-8"))
        logger.info("Loaded FAISS index (%d vectors) from %s", self._index.ntotal, index_file)

    @staticmethod
    def is_built(index_file: Path = _INDEX_FILE, meta_file: Path = _META_FILE) -> bool:
        return index_file.exists() and meta_file.exists()

    # ── Query ──────────────────────────────────────────────────────────────────

    def query(self, question: str, top_k: int = TOP_K) -> list[dict]:
        """Return top-K relevant chunks for an English question."""
        import faiss
        vec = np.array([self._embeddings.embed_query(question)], dtype="float32")
        faiss.normalize_L2(vec)
        scores, indices = self._index.search(vec, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self._chunks[idx]
            results.append({
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "text": chunk["text"],
                "score": float(score),
            })
        return results


def format_scheme_results(results: list[dict]) -> str:
    """Format RAG results into a context string for the LLM."""
    if not results:
        return "No relevant government scheme information found."
    lines = ["Relevant government scheme information:"]
    for i, r in enumerate(results, 1):
        lines += [
            f"",
            f"[{i}] Source: {r['source'].replace('_', ' ').title()} (relevance: {r['score']:.2f})",
            r["text"],
        ]
    return "\n".join(lines)
