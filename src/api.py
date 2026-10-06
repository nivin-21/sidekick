"""
FastAPI server for Sidekick.
Run with: uvicorn src.api:app --reload --port 8000
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.config import CORS_ORIGINS, OLLAMA_BASE_URL, OLLAMA_MODEL, TOP_K
from src.retriever import IndexNotFoundError
from src.sidekick import Sidekick

INGEST_HINT = "Knowledge base is not indexed. Run: python -m src.ingest — then restart the API."


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eagerly initialize Sidekick at startup to avoid cold-start on first request."""
    app.state.sidekick = None
    app.state.startup_error = None
    try:
        app.state.sidekick = Sidekick()
    except IndexNotFoundError as e:
        # Keep serving so /health can explain what's wrong instead of crashing on boot.
        app.state.startup_error = str(e)
    yield
    if app.state.sidekick is not None:
        await app.state.sidekick.aclose()


app = FastAPI(
    title="Sidekick",
    description="A RAG-powered backend systems design advisor",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def get_sidekick(request: Request) -> Sidekick:
    sidekick = getattr(request.app.state, "sidekick", None)
    if sidekick is None:
        raise HTTPException(status_code=503, detail=INGEST_HINT)
    return sidekick


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20_000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=50)
    top_k: int = Field(default=TOP_K, ge=1, le=10)


async def _ndjson_events(sidekick: Sidekick, body: AskRequest) -> AsyncGenerator[str, None]:
    """Serialize Sidekick events as newline-delimited JSON."""
    history = [turn.model_dump() for turn in body.history]
    try:
        async for event in sidekick.ask(body.question.strip(), history=history, top_k=body.top_k):
            yield json.dumps(event) + "\n"
    except Exception as e:
        # Surface failures as an event so the stream closes cleanly instead of abruptly
        yield json.dumps({"type": "error", "message": f"{type(e).__name__}: {e}"}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"


@app.post("/ask")
async def ask(body: AskRequest, sidekick: Sidekick = Depends(get_sidekick)) -> StreamingResponse:
    """
    Ask Sidekick a system design question.
    Streams NDJSON events: `sources`, then `token` (repeated), optional `error`, then `done`.
    """
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="Question cannot be blank.")

    return StreamingResponse(_ndjson_events(sidekick, body), media_type="application/x-ndjson")


@app.get("/health")
async def health(request: Request) -> dict:
    """Health check — verifies the index is loaded and Ollama has the model."""
    sidekick: Sidekick | None = getattr(request.app.state, "sidekick", None)
    if sidekick is None:
        raise HTTPException(
            status_code=503,
            detail={"index": "missing", "error": request.app.state.startup_error or INGEST_HINT},
        )

    try:
        model_ok = await sidekick.model_available()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not reachable at {OLLAMA_BASE_URL}. Start it with: ollama serve",
        )
    if not model_ok:
        raise HTTPException(
            status_code=503,
            detail=f"Model '{OLLAMA_MODEL}' is not pulled. Run: ollama pull {OLLAMA_MODEL}",
        )

    return {
        "status": "ok",
        "model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "index": "loaded",
        "chunks_loaded": sidekick.doc_count(),
    }


@app.get("/sources")
async def sources(sidekick: Sidekick = Depends(get_sidekick)) -> dict:
    """List all knowledge base files indexed in the vector store."""
    return {"sources": sidekick.list_sources()}
