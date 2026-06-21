# BE Guru — Backend Systems Design Advisor

A fully local RAG (Retrieval-Augmented Generation) system that answers backend engineering and system design questions. No cloud APIs, no cost — runs entirely on your machine.

Ask questions like:
- *"When should I use Kafka over RabbitMQ?"*
- *"How do I handle distributed transactions across microservices?"*
- *"Which database should I pick for a high-write time-series workload?"*

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Question                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Streamlit UI   │  demo/app.py
                    │  (chat interface)│
                    └────────┬────────┘
                             │ HTTP POST /ask
                    ┌────────▼────────┐
                    │   FastAPI API   │  src/api.py
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │         Guru (RAG Chain)     │  src/guru.py
              │                             │
              │  1. retrieve(question, k=5) │
              │  2. build_prompt(context)   │
              │  3. stream_ollama(prompt)   │
              └──────┬──────────────┬───────┘
                     │              │
          ┌──────────▼───┐    ┌─────▼──────────┐
          │  Retriever   │    │  Ollama Server  │
          │  src/retriever│   │  llama3.2:3b    │
          │              │    │  localhost:11434│
          └──────┬───────┘    └─────────────────┘
                 │
     ┌───────────▼──────────────┐
     │        ChromaDB          │
     │  (persistent vector DB)  │
     │  embedded with           │
     │  all-MiniLM-L6-v2        │
     └───────────┬──────────────┘
                 │ ingested from
     ┌───────────▼──────────────┐
     │      Knowledge Base      │
     │  knowledge_base/*.md     │
     │  8 expert BE topics      │
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

- Python 3.9+
- [Ollama](https://ollama.ai)

```bash
# Install Ollama
brew install ollama

# Pull the model (~2GB)
ollama pull llama3.2:3b

# Start Ollama server
ollama serve
```

## Setup

```bash
# 1. Clone and enter the project
cd sidekick

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Ingest the knowledge base (run once, or after adding new docs)
python -m src.ingest

# 5. Start the API server
uvicorn src.api:app --reload --port 8000

# 6. In a new terminal, start the Streamlit demo
source venv/bin/activate
streamlit run demo/app.py
```

Open [http://localhost:8501](http://localhost:8501) to use the chat interface.

## How RAG Works Here

1. **Ingest** (`src/ingest.py`): Markdown docs are split into ~500-char chunks preserving paragraph boundaries. Each chunk is embedded with `sentence-transformers/all-MiniLM-L6-v2` (a 384-dim model) and stored in ChromaDB with cosine similarity index.

2. **Retrieve** (`src/retriever.py`): Your question is embedded with the same model. ChromaDB returns the 5 most semantically similar chunks via cosine similarity.

3. **Generate** (`src/guru.py`): Retrieved chunks are injected into a prompt alongside a system persona. The prompt is sent to `llama3.2:3b` via Ollama's HTTP API with streaming enabled.

4. **Serve** (`src/api.py`): FastAPI streams the response token-by-token to the client. The Streamlit UI displays it in real-time.

### Why this architecture?

- **No LangChain**: The RAG pipeline is plain Python — every step is visible and understandable.
- **Local-first**: Zero cloud cost, works offline, no data leaves your machine.
- **Persistent ChromaDB**: Re-running the app doesn't re-embed — the vector store survives restarts.
- **Extendable**: Add new `.md` files to `knowledge_base/` and re-run `python -m src.ingest`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Ask a question, returns streaming text |
| `/health` | GET | Check Ollama + ChromaDB status |
| `/sources` | GET | List indexed knowledge base files |

## Stack

| Component | Technology |
|-----------|-----------|
| LLM | Llama 3.2 3B via Ollama |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector DB | ChromaDB (persistent) |
| API | FastAPI + uvicorn |
| Demo UI | Streamlit |
