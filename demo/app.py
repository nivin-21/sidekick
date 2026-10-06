"""
Streamlit demo UI for Sidekick.
Run with: streamlit run demo/app.py
"""

import json
import os

import requests
import streamlit as st

API_BASE = os.getenv("SIDEKICK_API", "http://localhost:8000")
START_API_HINT = "Start it with:\n```\nuvicorn src.api:app --reload --port 8000\n```"

st.set_page_config(
    page_title="Sidekick",
    page_icon="🏛",
    layout="wide",
)

st.title("Sidekick")
st.caption("A RAG-powered backend systems design advisor — ask your architecture questions")


class SourcesUnavailable(Exception):
    pass


@st.cache_data(ttl=60, show_spinner=False)
def fetch_sources() -> list[str]:
    """Cached so the sidebar doesn't hit the API on every rerun. Errors raise, so they aren't cached."""
    try:
        resp = requests.get(f"{API_BASE}/sources", timeout=5)
    except requests.exceptions.ConnectionError:
        raise SourcesUnavailable(f"API not running at {API_BASE}.\n{START_API_HINT}")
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise SourcesUnavailable(str(detail))
    return resp.json().get("sources", [])


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander("Sources used"):
        for src in sources:
            score = f" · similarity {src['score']:.2f}" if src.get("score") else ""
            st.markdown(f"- `{src['source']}` — {src.get('section', '')}{score}")


# --- Sidebar ---
with st.sidebar:
    st.header("Knowledge Base")
    st.markdown("Topics covered:")

    try:
        for src in fetch_sources():
            st.markdown(f"- {src.replace('.md', '').replace('_', ' ').title()}")
    except SourcesUnavailable as e:
        st.error(str(e))

    st.divider()
    st.markdown("**Example questions:**")
    examples = [
        "When should I use Kafka over RabbitMQ?",
        "How do I handle distributed transactions across microservices?",
        "Which database should I pick for a social feed?",
        "Explain the outbox pattern and when to use it.",
        "How do I scale my API to handle 100k requests/sec?",
        "What consistency model should a payment system use?",
    ]
    for ex in examples:
        if st.button(ex, key=ex, use_container_width=True):
            st.session_state["prefill"] = ex

    st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state["messages"] = []
        st.rerun()

    st.markdown("**How RAG works here:**")
    st.markdown(
        "1. Your question (plus the previous one, for follow-ups) is embedded into a vector\n"
        "2. Hybrid search (semantic + keyword) finds the most relevant knowledge base chunks\n"
        "3. Chunks are injected into the LLM prompt as context, with recent chat history\n"
        "4. Llama 3.2 generates an answer grounded in that context"
    )

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            render_sources(msg.get("sources", []))

# --- Input ---
prefill = st.session_state.pop("prefill", "")
question = st.chat_input("Ask a backend system design question...") or prefill

if question:
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]]

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer = ""
        sources: list[dict] = []
        error = None

        try:
            with requests.post(
                f"{API_BASE}/ask",
                json={"question": question, "history": history},
                stream=True,
                timeout=(5, 120),
            ) as response:
                if response.status_code != 200:
                    error = f"API error {response.status_code}: {response.text}"
                else:
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        event = json.loads(line)
                        if event["type"] == "sources":
                            sources = event["sources"]
                        elif event["type"] == "token":
                            answer += event["text"]
                            placeholder.markdown(answer + "▌")
                        elif event["type"] == "error":
                            error = event["message"]
        except requests.exceptions.ConnectionError:
            error = f"Cannot connect to the API at {API_BASE}. {START_API_HINT}"
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ReadTimeout):
            error = "Connection closed early — partial response above."

        if answer:
            placeholder.markdown(answer)
        else:
            placeholder.empty()
        if error:
            st.error(error)
        render_sources(sources)

    # Only record the exchange if we actually got an answer, so failures don't pollute history.
    if answer:
        st.session_state["messages"].append({"role": "user", "content": question})
        st.session_state["messages"].append({"role": "assistant", "content": answer, "sources": sources})
