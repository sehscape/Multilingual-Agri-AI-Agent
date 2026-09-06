"""Multilingual embedding model abstraction (Phase 7 – RAG).

The embedding model converts text chunks and queries into dense vectors.
BGE-M3 is preferred because it handles Hindi, Marathi, Punjabi, and English.
Documents may be in any supported language; queries arrive in English after IndicTrans2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.config import EMBEDDING_MODEL_ID
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseEmbeddings(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Return a list of embedding vectors for a list of documents."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Return the embedding vector for a single query string."""


class SentenceTransformerEmbeddings(BaseEmbeddings):
    """sentence-transformers wrapper – works for both bge-m3 and MiniLM."""

    def __init__(self, model_id: str = EMBEDDING_MODEL_ID) -> None:
        self.model_id = model_id
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        logger.info("Loading embedding model: %s", self.model_id)
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self.model_id)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._load()
        return self._model.encode(texts, show_progress_bar=False).tolist()

    def embed_query(self, text: str) -> List[float]:
        self._load()
        return self._model.encode([text], show_progress_bar=False)[0].tolist()


def get_embeddings(model_id: str = EMBEDDING_MODEL_ID) -> BaseEmbeddings:
    return SentenceTransformerEmbeddings(model_id=model_id)
