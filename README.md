# Sidekick — Backend Systems Design Advisor

A fully local RAG (Retrieval-Augmented Generation) system that answers backend engineering and system design questions. No cloud APIs, no cost — runs entirely on your machine.

Ask questions like:
- *"When should I use Kafka over RabbitMQ?"* → then follow up with *"what about ordering guarantees?"*
- *"How do I handle distributed transactions across microservices?"*
- *"Which database should I pick for a high-write time-series workload?"*

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  User Question (+ chat history)             │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Streamlit UI   │  demo/app.py
                    │ (chat interface)│
                    └────────┬────────┘
                             │ HTTP POST /ask  →  NDJSON event stream
                    ┌────────▼────────┐
                    │   FastAPI API   │  src/api.py
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │    Sidekick (RAG chain)     │  src/sidekick.py
              │                             │
              │  1. hybrid retrieve (k=5)   │
              │  2. no context? → refuse    │
              │  3. chat(system, history,   │
              │          context+question)  │
              └──────┬──────────────┬───────┘
                     │              │
          ┌──────────▼────────┐ ┌───▼─────────────┐
          │    Retriever      │ │  Ollama Server  │
          │ src/retriever.py  │ │  llama3.2:3b    │
          │ vector + BM25,    │ │  /api/chat      │
          │ fused with RRF    │ │  localhost:11434│
          └──────────┬────────┘ └─────────────────┘
                     │
     ┌───────────────▼──────────┐
     │        ChromaDB          │
     │  (persistent vector DB)  │
     │  all-MiniLM-L6-v2        │
     └───────────┬──────────────┘
                 │ built by src/ingest.py + src/chunking.py
     ┌───────────▼──────────────┐
     │      Knowledge Base      │
     │  knowledge_base/*.md     │
     └──────────────────────────┘
```

## Knowledge Base Topics

| File | Topic |
|------|-------|
| `cap_theorem.md` | CAP theorem, PACELC, consistency tradeoffs |
| `caching_strategies.md` | Cache-aside, write-through, write-behind, Redis |
| `database_selection.md` | SQL vs NoSQL decision matrix |
| `messaging_patterns.md` | Kafka, RabbitMQ, SQS, Saga, Outbox pattern |
| `api_design.md` | REST vs GraphQL vs gRPC, versioning, rate limiting |
| `scalability_patterns.md` | Sharding, load balancing, connection pooling |
| `consistency_models.md` | Strong/eventual consistency, 2PC, Saga |
| `microservices_patterns.md` | Circuit breaker, bulkhead, service mesh, API gateway |

## Prerequisites

- **Python 3.11 or 3.12.** Newer versions (3.13+) are not supported yet because `numpy<2` (required by the pinned ChromaDB/sentence-transformers stack) has no wheels for them.
- [Ollama](https://ollama.com)

**Windows (PowerShell)**

```powershell
winget install Ollama.Ollama
ollama pull llama3.2:3b   # ~2GB; Ollama runs as a background service after install
```

**macOS**

```bash
brew install ollama
ollama pull llama3.2:3b
ollama serve
```

## Setup

**Windows (PowerShell)**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m src.ingest                         # build the index (re-run after editing knowledge_base/)
uvicorn src.api:app --reload --port 8000     # terminal 1
streamlit run demo/app.py                    # terminal 2 (activate the venv first)
```

**macOS / Linux**

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python -m src.ingest
uvicorn src.api:app --reload --port 8000     # terminal 1
streamlit run demo/app.py                    # terminal 2
```

Open [http://localhost:8501](http://localhost:8501) to use the chat interface.

> **Upgrading from "BE Guru"?** The vector collection was renamed from `be_guru` to `sidekick`. Re-run `python -m src.ingest` once.

## How RAG Works Here

1. **Ingest** (`src/ingest.py`, `src/chunking.py`): Markdown docs are split per heading section, then packed into chunks of ≤800 chars on paragraph/sentence/word boundaries with a small overlap. Each chunk is prefixed with its heading breadcrumb (e.g. `Messaging Patterns > Outbox Pattern`) so it keeps its topic. Chunks are embedded with `all-MiniLM-L6-v2` and stored in ChromaDB. The collection is rebuilt on every run, so edited or deleted docs never leave stale chunks.

2. **Retrieve** (`src/retriever.py`): The question (plus the previous question, for follow-ups) is searched two ways — semantic vector search and BM25 keyword search (which catches exact terms like `2PC` or `PACELC`). Rankings are merged with Reciprocal Rank Fusion. If no chunk reaches the cosine-similarity threshold (`MIN_SIMILARITY`), nothing is returned. Retrieval runs in a worker thread so it doesn't block the server.

3. **Generate** (`src/sidekick.py`): With no relevant context, Sidekick says so without calling the LLM. Otherwise it calls Ollama's `/api/chat` with a system prompt, the recent chat history, and the retrieved context + question, at low temperature.

4. **Serve** (`src/api.py`): FastAPI streams typed NDJSON events to the client. The Streamlit UI renders tokens live and shows the sources used, with section and similarity.

### Why this architecture?

- **No LangChain**: The RAG pipeline is plain Python — every step is visible and understandable.
- **Local-first**: Zero cloud cost, works offline, no data leaves your machine.
- **Persistent ChromaDB**: Restarting the API doesn't re-embed — the vector store survives restarts.
- **Extendable**: Add `.md` files to `knowledge_base/`, re-run `python -m src.ingest`, and restart the API.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Ask a question; streams NDJSON events |
| `/health` | GET | Checks the index is loaded and Ollama has the model (503 with a hint otherwise) |
| `/sources` | GET | List indexed knowledge base files |

**Request**

```json
{
  "question": "what about ordering guarantees?",
  "history": [
    {"role": "user", "content": "When should I use Kafka over RabbitMQ?"},
    {"role": "assistant", "content": "Use Kafka when..."}
  ],
  "top_k": 5
}
```

`question` is 1–2000 chars; `history` and `top_k` (1–10) are optional.

**Response** — `application/x-ndjson`, one JSON object per line:

```
{"type": "sources", "sources": [{"source": "messaging_patterns.md", "section": "Messaging Patterns > Kafka", "score": 0.71}]}
{"type": "token", "text": "Kafka "}
{"type": "token", "text": "guarantees ordering per partition..."}
{"type": "done"}
```

If Ollama fails, an `{"type": "error", "message": "..."}` event is sent before `done`.

```bash
curl -N -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Explain the outbox pattern"}'
```

## Configuration

Settings come from environment variables or a `.env` file in the project root — copy `.env.example` to `.env` to start. Common ones:

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_MODEL` | `llama3.2:3b` | Any model you've pulled with `ollama pull` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server |
| `OLLAMA_TEMPERATURE` | `0.2` | Lower = more grounded answers |
| `TOP_K` | `5` | Chunks sent to the LLM |
| `MIN_SIMILARITY` | `0.3` | Cosine similarity below which a question is treated as off-topic |
| `MAX_HISTORY_TURNS` | `6` | Previous messages sent for follow-ups |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `800` / `100` | Chunking (re-ingest after changing) |
| `CHROMA_PERSIST_PATH` | `chroma_db` | Relative to the project root, not the current directory |
| `CORS_ORIGINS` | `http://localhost:8501,...` | Browser origins allowed to call the API |
| `SIDEKICK_API` | `http://localhost:8000` | API URL used by the Streamlit UI |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use an in-memory fake vector store, a fake embedder, and a mocked Ollama, so they run in about a second without models or servers.

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | Llama 3.2 3B via Ollama |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Retrieval | ChromaDB (vector) + rank-bm25 (keyword), Reciprocal Rank Fusion |
| API | FastAPI + uvicorn |
| Demo UI | Streamlit |
