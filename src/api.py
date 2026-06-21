"""
FastAPI server for BE Guru.
Run with: uvicorn src.api:app --reload --port 8000
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.guru import Guru

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

_guru: Guru | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly initialize Guru at startup to avoid cold-start on first request."""
    global _guru
    _guru = Guru()
    yield


app = FastAPI(
    title="BE Guru",
    description="A RAG-powered backend systems design advisor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_guru() -> Guru:
    assert _guru is not None, "Guru not initialized — lifespan handler did not run"
    return _guru


class AskRequest(BaseModel):
    question: str


async def _stream_response(question: str) -> AsyncGenerator[str, None]:
    """Async generator that streams answer tokens from Guru."""
    guru = get_guru()
    try:
        async for token in guru.ask(question):
            yield token
    except Exception as e:
        # Yield errors as text so the connection closes cleanly instead of abruptly
        yield f"\n\n[ERROR] {type(e).__name__}: {e}"


@app.post("/ask")
async def ask(body: AskRequest) -> StreamingResponse:
    """Ask the BE Guru a system design question. Returns a streaming text response."""
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    return StreamingResponse(
        _stream_response(body.question),
        media_type="text/plain",
    )


@app.get("/health")
async def health() -> dict:
    """Health check — verifies Ollama is reachable and ChromaDB is loaded."""
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    if not ollama_ok:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not reachable at {OLLAMA_BASE_URL}. Start it with: ollama serve",
        )

    guru = get_guru()
    return {
        "status": "ok",
        "model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "docs_loaded": guru.doc_count(),
    }


@app.get("/sources")
async def sources() -> dict:
    """List all knowledge base files indexed in the vector store."""
    guru = get_guru()
    return {"sources": guru.list_sources()}
