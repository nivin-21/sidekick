"""Shared fakes so tests run without ChromaDB, sentence-transformers or Ollama."""

from __future__ import annotations

import math

import pytest

from src.retriever import Retriever

VOCAB = ["kafka", "rabbitmq", "queue", "cache", "redis", "database", "2pc", "saga", "pizza"]


def fake_embed(text: str) -> list[float]:
    """Bag-of-words over a tiny vocabulary; good enough to make similarity meaningful."""
    words = [w.strip(".,?;") for w in text.lower().split()]
    vec = [float(words.count(term)) for term in VOCAB]
    return vec if any(vec) else [0.0] * (len(VOCAB) - 1) + [1e-6]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class FakeCollection:
    """Implements the slice of the ChromaDB Collection API the Retriever uses."""

    def __init__(self, docs: dict[str, tuple[str, str, str]]) -> None:
        # id -> (content, source, section)
        self.docs = docs
        self.embeddings = {doc_id: fake_embed(content) for doc_id, (content, _, _) in docs.items()}

    def get(self, include):
        ids = list(self.docs)
        return {
            "ids": ids,
            "documents": [self.docs[i][0] for i in ids],
            "metadatas": [{"source": self.docs[i][1], "section": self.docs[i][2]} for i in ids],
        }

    def query(self, query_embeddings, n_results, include):
        q = query_embeddings[0]
        ranked = sorted(self.docs, key=lambda i: _cosine(q, self.embeddings[i]), reverse=True)[:n_results]
        return {"ids": [ranked], "distances": [[1.0 - _cosine(q, self.embeddings[i]) for i in ranked]]}


DOCS = {
    "m1": ("Kafka is a log. Use Kafka for replay and high throughput.", "messaging.md", "Messaging > Kafka"),
    "m2": ("RabbitMQ is a queue broker with flexible routing.", "messaging.md", "Messaging > RabbitMQ"),
    "c1": ("Use Redis as a cache with cache-aside.", "caching.md", "Caching > Redis"),
    "t1": ("2PC blocks when the coordinator fails; prefer a saga across services.", "consistency.md", "Consistency > 2PC"),
    "d1": ("Pick a database by access pattern.", "database.md", "Databases"),
}


@pytest.fixture
def retriever() -> Retriever:
    return Retriever(collection=FakeCollection(DOCS), embed=fake_embed)
