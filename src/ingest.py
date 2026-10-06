"""
Ingestion pipeline: loads knowledge base markdown files, chunks them,
embeds with sentence-transformers, and stores in ChromaDB.
Run with: python -m src.ingest

The collection is rebuilt from scratch on every run, so edited or deleted
documents never leave stale chunks behind.
"""

from __future__ import annotations

import chromadb
from sentence_transformers import SentenceTransformer

from src.chunking import Chunk, chunk_document
from src.config import CHROMA_PERSIST_PATH, COLLECTION_NAME, EMBEDDING_MODEL, KNOWLEDGE_BASE_DIR


def load_documents() -> list[dict]:
    """Load all markdown files from the knowledge base directory."""
    docs = []
    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        docs.append({"source": md_file.name, "content": content})
        print(f"  Loaded: {md_file.name} ({len(content)} chars)")
    return docs


def embed_and_store(chunks: list[Chunk], model: SentenceTransformer, collection: chromadb.Collection) -> None:
    """Embed all chunks in one batch and add them to ChromaDB."""
    texts = [c.content for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=64).tolist()

    collection.add(
        ids=[f"{c.source}__chunk_{c.chunk_index}" for c in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[
            {"source": c.source, "section": c.section, "chunk_index": c.chunk_index}
            for c in chunks
        ],
    )


def main() -> None:
    print("=== Sidekick — Ingestion Pipeline ===\n")

    print("Loading knowledge base documents:")
    docs = load_documents()
    if not docs:
        print(f"ERROR: No markdown files found in {KNOWLEDGE_BASE_DIR}")
        return

    chunks: list[Chunk] = []
    for doc in docs:
        doc_chunks = chunk_document(doc["content"], doc["source"])
        chunks.extend(doc_chunks)
        print(f"  Chunked: {doc['source']} → {len(doc_chunks)} chunks")

    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"\nRebuilding collection '{COLLECTION_NAME}' at: {CHROMA_PERSIST_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass  # collection did not exist yet
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    embed_and_store(chunks, model, collection)
    print(f"\nDone. Collection '{COLLECTION_NAME}' has {collection.count()} chunks from {len(docs)} documents.")


if __name__ == "__main__":
    main()
