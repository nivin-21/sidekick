"""
Ingestion pipeline: loads knowledge base markdown files, chunks them,
embeds with sentence-transformers, and stores in ChromaDB.
Run with: python -m src.ingest
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"
CHROMA_PERSIST_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME = "be_guru"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def load_documents() -> list[dict]:
    """Load all markdown files from the knowledge base directory."""
    docs = []
    for md_file in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        docs.append({"source": md_file.name, "content": content})
        print(f"  Loaded: {md_file.name} ({len(content)} chars)")
    return docs


def chunk_document(content: str, source: str) -> list[dict]:
    """
    Chunk a document preserving paragraph boundaries.
    Splits on double newlines first, then merges small paragraphs
    and splits large ones to stay near CHUNK_SIZE.
    """
    paragraphs = re.split(r"\n\n+", content.strip())
    chunks = []
    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= CHUNK_SIZE:
            current_chunk = (current_chunk + "\n\n" + para).strip()
        else:
            if current_chunk:
                chunks.append({
                    "content": current_chunk,
                    "source": source,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1
                overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else current_chunk
                candidate = (overlap_text + "\n\n" + para).strip()
                # If overlap + para still exceeds limit, split it by character
                if len(candidate) > CHUNK_SIZE:
                    for i in range(0, len(candidate), CHUNK_SIZE - CHUNK_OVERLAP):
                        sub = candidate[i:i + CHUNK_SIZE]
                        chunks.append({
                            "content": sub,
                            "source": source,
                            "chunk_index": chunk_index,
                        })
                        chunk_index += 1
                    current_chunk = ""
                else:
                    current_chunk = candidate
            else:
                # Paragraph itself is larger than CHUNK_SIZE — split by chars
                for i in range(0, len(para), CHUNK_SIZE - CHUNK_OVERLAP):
                    sub = para[i:i + CHUNK_SIZE]
                    chunks.append({
                        "content": sub,
                        "source": source,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1
                current_chunk = ""

    if current_chunk:
        chunks.append({
            "content": current_chunk,
            "source": source,
            "chunk_index": chunk_index,
        })

    return chunks


def embed_and_store(chunks: list[dict], model: SentenceTransformer, collection: chromadb.Collection) -> None:
    """Embed chunks and upsert into ChromaDB."""
    texts = [c["content"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    ids = [f"{c['source']}__chunk_{c['chunk_index']}" for c in chunks]
    metadatas = [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in chunks]

    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def main() -> None:
    print("=== BE Guru — Ingestion Pipeline ===\n")

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"\nConnecting to ChromaDB at: {CHROMA_PERSIST_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print("\nLoading knowledge base documents:")
    docs = load_documents()
    if not docs:
        print("ERROR: No markdown files found in knowledge_base/")
        return

    total_chunks = 0
    for doc in docs:
        chunks = chunk_document(doc["content"], doc["source"])
        embed_and_store(chunks, model, collection)
        total_chunks += len(chunks)
        print(f"  Indexed: {doc['source']} → {len(chunks)} chunks")

    print(f"\nDone. Total chunks stored: {total_chunks}")
    print(f"Collection '{COLLECTION_NAME}' has {collection.count()} documents.")


if __name__ == "__main__":
    main()
