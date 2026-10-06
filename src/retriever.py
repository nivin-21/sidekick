"""
Retriever: hybrid (vector + BM25 keyword) search over the ChromaDB knowledge base.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.chunking import tokenize
from src.config import CHROMA_PERSIST_PATH, COLLECTION_NAME, EMBEDDING_MODEL, MIN_SIMILARITY, TOP_K

RRF_K = 60  # standard Reciprocal Rank Fusion constant


class IndexNotFoundError(RuntimeError):
    """Raised when the vector store has not been populated by the ingest step."""


@dataclass
class RetrievedChunk:
    content: str
    source: str
    section: str
    score: float  # cosine similarity in [-1, 1]; 0.0 for keyword-only matches


def distance_to_similarity(distance: float) -> float:
    """ChromaDB's cosine distance is `1 - cosine_similarity`."""
    return 1.0 - distance


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    """Fuse several ranked id lists into one ranking (best first)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)


class Retriever:
    """
    Hybrid retriever. Semantic search catches paraphrases; BM25 catches exact
    terms (e.g. "2PC", "PACELC") that small embedding models blur together.
    """

    def __init__(
        self,
        collection=None,
        embed: Callable[[str], list[float]] | None = None,
    ) -> None:
        if collection is None:
            collection = self._open_collection()
        if embed is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(EMBEDDING_MODEL)
            embed = lambda text: model.encode(text).tolist()  # noqa: E731

        self._collection = collection
        self._embed = embed

        data = collection.get(include=["documents", "metadatas"])
        self._ids: list[str] = data["ids"]
        self._docs = dict(zip(data["ids"], data["documents"]))
        self._metas = dict(zip(data["ids"], data["metadatas"]))
        if not self._ids:
            raise IndexNotFoundError("Knowledge base is empty — run: python -m src.ingest")
        self._bm25 = BM25Okapi([tokenize(doc) for doc in data["documents"]])

    @staticmethod
    def _open_collection():
        import chromadb

        client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
        try:
            return client.get_collection(name=COLLECTION_NAME)
        except Exception as e:
            raise IndexNotFoundError(
                f"Collection '{COLLECTION_NAME}' not found at {CHROMA_PERSIST_PATH} — run: python -m src.ingest"
            ) from e

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[RetrievedChunk]:
        """
        Return up to top_k chunks ranked by fused vector + keyword relevance.
        Returns [] when nothing is semantically close enough, so off-topic
        questions are not answered from loosely related context.
        """
        candidates = min(max(top_k * 3, 10), len(self._ids))

        results = self._collection.query(
            query_embeddings=[self._embed(query)],
            n_results=candidates,
            include=["distances"],
        )
        similarities = {
            doc_id: distance_to_similarity(dist)
            for doc_id, dist in zip(results["ids"][0], results["distances"][0])
        }
        if not similarities or max(similarities.values()) < min_similarity:
            return []

        vector_ranking = [doc_id for doc_id, sim in similarities.items() if sim >= min_similarity]

        bm25_scores = self._bm25.get_scores(tokenize(query))
        keyword_ranking = [
            self._ids[i]
            for i in sorted(range(len(self._ids)), key=lambda i: bm25_scores[i], reverse=True)[:candidates]
            if bm25_scores[i] > 0
        ]

        fused = reciprocal_rank_fusion([vector_ranking, keyword_ranking])[:top_k]
        return [
            RetrievedChunk(
                content=self._docs[doc_id],
                source=self._metas[doc_id]["source"],
                section=self._metas[doc_id].get("section", ""),
                score=round(similarities.get(doc_id, 0.0), 4),
            )
            for doc_id in fused
        ]

    async def aretrieve(self, query: str, top_k: int = TOP_K) -> list[RetrievedChunk]:
        """Run retrieval in a worker thread so embedding doesn't block the event loop."""
        return await asyncio.to_thread(self.retrieve, query, top_k)

    def doc_count(self) -> int:
        """Return the total number of chunks in the collection."""
        return len(self._ids)

    def list_sources(self) -> list[str]:
        """Return unique source filenames indexed in the collection."""
        return sorted({m["source"] for m in self._metas.values()})
