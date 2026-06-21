"""
Guru: RAG chain that retrieves relevant context and streams an answer via Ollama.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator

import httpx

from src.retriever import Retriever, RetrievedChunk

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
TOP_K = 5

SYSTEM_PROMPT = """You are a senior backend systems architect with 15+ years of experience \
designing large-scale distributed systems. You give precise, opinionated answers grounded \
in practical experience. You are not verbose — you get to the point.

Rules:
- Answer ONLY based on the provided context sections.
- If the context does not cover the question, say: "I don't have specific information on that \
in my knowledge base. Consider checking the official documentation or relevant engineering blogs."
- Cite the source files that informed your answer (e.g., "from caching_strategies.md").
- Prefer concrete recommendations over vague "it depends" answers — when trade-offs exist, \
state them clearly and give a default recommendation.
- Use bullet points or short paragraphs. No unnecessary preamble."""


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Build the full prompt with retrieved context injected."""
    context_sections = []
    for i, chunk in enumerate(chunks, 1):
        context_sections.append(
            f"[Source {i}: {chunk.source}]\n{chunk.content}"
        )
    context_block = "\n\n---\n\n".join(context_sections)

    return f"""{SYSTEM_PROMPT}

## Context from Knowledge Base

{context_block}

---

## Question

{question}

## Answer"""


class Guru:
    """RAG-powered backend systems advisor."""

    def __init__(self) -> None:
        self._retriever = Retriever()

    async def ask(self, question: str) -> AsyncGenerator[str, None]:  # type: ignore[override]
        """
        Async generator: retrieve relevant context and stream LLM answer token by token.
        Appends a sources footer as the final yielded value for the API layer to parse.
        """
        chunks = self._retriever.retrieve(question, top_k=TOP_K)
        sources = list({c.source for c in chunks})
        prompt = build_prompt(question, chunks)

        try:
            async for token in self._stream_ollama(prompt):
                yield token
        except httpx.ConnectError:
            yield "\n\n[ERROR] Cannot reach Ollama. Start it with: ollama serve"
            return
        except httpx.TimeoutException:
            yield "\n\n[ERROR] Ollama timed out. The model may be loading — try again."
            return
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                yield f"\n\n[ERROR] Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}"
            else:
                yield f"\n\n[ERROR] Ollama returned {e.response.status_code}: {e.response.text}"
            return
        except Exception as e:
            yield f"\n\n[ERROR] Unexpected error: {type(e).__name__}: {e}"
            return

        # Yield sources as a trailing footer sentinel for the API layer to pick up
        if sources:
            sources_line = "\n\n---\n**Sources:** " + ", ".join(f"`{s}`" for s in sources)
            yield sources_line

    async def _stream_ollama(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama's generate API using async HTTP."""
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break

    def doc_count(self) -> int:
        return self._retriever.doc_count()

    def list_sources(self) -> list[str]:
        return self._retriever.list_sources()
