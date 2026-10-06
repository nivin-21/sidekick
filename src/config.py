"""
Central configuration. Every setting can be overridden via environment variables
or a `.env` file in the project root.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is optional
    load_dotenv = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str) -> str:
    """Resolve relative paths against the project root, not the current working directory."""
    path = Path(value)
    return str(path if path.is_absolute() else PROJECT_ROOT / path)


KNOWLEDGE_BASE_DIR = Path(_resolve_path(os.getenv("KNOWLEDGE_BASE_DIR", "knowledge_base")))
CHROMA_PERSIST_PATH = _resolve_path(os.getenv("CHROMA_PERSIST_PATH", "chroma_db"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "sidekick")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

TOP_K = int(os.getenv("TOP_K", "5"))
# Cosine similarity in [-1, 1]. Chunks below this are treated as irrelevant.
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.3"))
# How many previous chat turns are sent to the LLM for follow-up questions.
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "6"))

NO_CONTEXT_ANSWER = (
    "I don't have specific information on that in my knowledge base. "
    "Consider checking the official documentation or relevant engineering blogs."
)

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:8501,http://127.0.0.1:8501").split(",")
    if o.strip()
]
