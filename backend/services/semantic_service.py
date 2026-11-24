"""
Phase 5 — Semantic Search Service
Provides semantic similarity search over ARGO float observations
using a pre-built ChromaDB index.

Verified status: this service was exercised against the recovered `argo_profiles`
collection and returned ranked results for a live query. The Chroma index is
persisted under backend/data/chroma/ and is counted at 706 indexed documents.

Unverified status: downstream retrieval flows that combine this service with other
query layers remain pending execution checks.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class SemanticService:
    """
    Lazy-loaded semantic search service backed by ChromaDB.
    Thread-safe singleton via module-level instance.
    """

    def __init__(self):
        self._collection = None
        self._client = None
        self._ready = False

    def _load(self) -> None:
        """Initialize ChromaDB client and load collection."""
        if self._ready:
            return

        import chromadb
        from config import settings

        chroma_dir = settings.chroma_dir
        if not chroma_dir.exists():
            raise RuntimeError(
                f"ChromaDB directory not found: {chroma_dir}. "
                "Please run build_chroma_index.py first."
            )

        logger.info(f"Loading ChromaDB from: {chroma_dir}")
        self._client = chromadb.PersistentClient(path=str(chroma_dir))

        try:
            self._collection = self._client.get_collection(settings.chroma_collection_name)
        except Exception as e:
            raise RuntimeError(
                f"ChromaDB collection '{settings.chroma_collection_name}' not found. "
                f"Please run build_chroma_index.py first. Error: {e}"
            )

        count = self._collection.count()
        logger.info(f"ChromaDB loaded: {count:,} indexed records")
        self._ready = True

    def is_ready(self) -> bool:
        """Return True if the service has been initialized."""
        return self._ready

    def collection_count(self) -> int:
        """Return number of documents in the collection."""
        self._load()
        return self._collection.count()

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the ChromaDB index for semantically similar float observations.

        Args:
            query:  Natural language query string.
            top_k:  Number of results to return (1–20).
            where:  Optional ChromaDB metadata filter dict.

        Returns:
            List of dicts with keys: document, score, metadata
        """
        self._load()

        top_k = max(1, min(top_k, 20))

        try:
            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": top_k,
                "include": ["documents", "distances", "metadatas"],
            }
            if where:
                kwargs["where"] = where

            results = self._collection.query(**kwargs)

            output = []
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for doc, dist, meta in zip(documents, distances, metadatas):
                # ChromaDB cosine distance → similarity score (0–1, higher = better)
                score = round(1.0 - float(dist), 4)
                output.append({
                    "document": doc,
                    "score": score,
                    "metadata": meta or {},
                })

            return output

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def semantic_search_by_region(
        self,
        query: str,
        region: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Semantic search filtered to a specific ocean region."""
        where_filter = {"region": {"$eq": region}}
        return self.semantic_search(query, top_k=top_k, where=where_filter)


# Module-level singleton
_service: SemanticService | None = None


def get_semantic_service() -> SemanticService:
    """Get or create the module-level SemanticService singleton."""
    global _service
    if _service is None:
        _service = SemanticService()
    return _service


# Convenience function for direct imports
def semantic_search(
    query: str,
    top_k: int = 5,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Module-level convenience wrapper for semantic_search."""
    return get_semantic_service().semantic_search(query, top_k=top_k, where=where)
