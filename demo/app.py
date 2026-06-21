"""
Streamlit demo UI for BE Guru.
Run with: streamlit run demo/app.py
"""

import re

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="BE Guru",
    page_icon="🏛",
    layout="wide",
)

st.title("BE Guru")
st.caption("A RAG-powered backend systems design advisor — asks your architecture questions")

# --- Sidebar ---
with st.sidebar:
    st.header("Knowledge Base")
    st.markdown("Topics covered:")

    try:
        resp = requests.get(f"{API_BASE}/sources", timeout=5)
        if resp.ok:
            for src in resp.json().get("sources", []):
                label = src.replace(".md", "").replace("_", " ").title()
                st.markdown(f"- {label}")
        else:
            st.warning("Could not fetch sources.")
    except requests.exceptions.ConnectionError:
        st.error("API not running.\nStart with:\n```\nuvicorn src.api:app --reload --port 8000\n```")

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
    st.markdown("**How RAG works here:**")
    st.markdown(
        "1. Your question is embedded into a vector\n"
        "2. ChromaDB finds the most similar knowledge base chunks\n"
        "3. Chunks are injected into the LLM prompt as context\n"
        "4. Llama 3.2 generates an answer grounded in that context"
    )

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            with st.expander("Sources used"):
                for src in msg["sources"]:
                    st.markdown(f"- `{src}`")

# --- Input ---
prefill = st.session_state.pop("prefill", "")
question = st.chat_input("Ask a backend system design question...") or prefill

if question:
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_text = ""
        display_text = ""
        sources: list[str] = []

        try:
            with requests.post(
                f"{API_BASE}/ask",
                json={"question": question},
                stream=True,
                timeout=120,
            ) as response:
                if response.status_code != 200:
                    st.error(f"API error: {response.status_code} — {response.text}")
                else:
                    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                        if chunk:
                            full_text += chunk
                            # Strip trailing sources footer for display, show it separately
                            display_text = re.sub(r"\n\n---\n\*\*Sources:\*\*.*$", "", full_text, flags=re.DOTALL)
                            placeholder.markdown(display_text + "▌")

            # Extract sources from footer
            source_match = re.search(r"\*\*Sources:\*\* (.+)$", full_text)
            if source_match:
                raw = source_match.group(1)
                sources = re.findall(r"`([^`]+)`", raw)

            display_text = re.sub(r"\n\n---\n\*\*Sources:\*\*.*$", "", full_text, flags=re.DOTALL)
            placeholder.markdown(display_text)

            if sources:
                with st.expander("Sources used"):
                    for src in sources:
                        st.markdown(f"- `{src}`")

        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
            if full_text:
                # Partial response received before disconnect — show what we got
                display_text = re.sub(r"\n\n---\n\*\*Sources:\*\*.*$", "", full_text, flags=re.DOTALL)
                placeholder.markdown(display_text + "\n\n*[Connection closed early — partial response above]*")
            else:
                st.error(
                    "Cannot connect to the API. Make sure it's running:\n"
                    "```\nuvicorn src.api:app --reload --port 8000\n```"
                )

    st.session_state["messages"].append({
        "role": "assistant",
        "content": display_text if question else "",
        "sources": sources,
    })
