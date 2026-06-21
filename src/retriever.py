"""
Retriever: semantic search over the ChromaDB knowledge base.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PERSIST_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME = "be_guru"


@dataclass
class RetrievedChunk:
    content: str
    source: str
    score: float


class Retriever:
    """Semantic retriever backed by ChromaDB and sentence-transformers."""

    def __init__(self) -> None:
        self._model = SentenceTransformer(EMBEDDING_MODEL)
        self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
        self._collection = self._client.get_collection(name=COLLECTION_NAME)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.4,
    ) -> list[RetrievedChunk]:
        """
        Embed the query and return the top_k most similar chunks above min_score.
        Returns list of RetrievedChunk sorted by relevance (highest first).
        """
        query_embedding = self._model.encode(query).tolist()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (dist / 2)
            score = round(1.0 - dist / 2.0, 4)
            if score >= min_score:
                chunks.append(RetrievedChunk(
                    content=doc,
                    source=meta["source"],
                    score=score,
                ))

        return chunks

    def doc_count(self) -> int:
        """Return the total number of chunks in the collection."""
        return self._collection.count()

    def list_sources(self) -> list[str]:
        """Return unique source filenames indexed in the collection."""
        results = self._collection.get(include=["metadatas"])
        sources = sorted({m["source"] for m in results["metadatas"]})
        return sources
