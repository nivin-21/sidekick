import json

import httpx

from src.config import NO_CONTEXT_ANSWER, OLLAMA_MODEL
from src.sidekick import Sidekick, build_messages, retrieval_query


def ollama_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="http://ollama", transport=httpx.MockTransport(handler))


def streaming_ok(captured: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        lines = [
            {"message": {"content": "Use "}, "done": False},
            {"message": {"content": "Kafka."}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]
        return httpx.Response(200, text="\n".join(json.dumps(line) for line in lines))

    return handler


async def collect(gen):
    return [event async for event in gen]


async def test_streams_sources_tokens_done(retriever):
    captured = {}
    sidekick = Sidekick(retriever=retriever, client=ollama_client(streaming_ok(captured)))
    events = await collect(sidekick.ask("kafka for replay?"))

    assert [e["type"] for e in events] == ["sources", "token", "token", "done"]
    assert events[0]["sources"][0]["source"] == "messaging.md"
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Use Kafka."
    assert captured["payload"]["model"] == OLLAMA_MODEL
    assert captured["payload"]["messages"][0]["role"] == "system"


async def test_no_context_skips_llm(retriever):
    def handler(request):
        raise AssertionError("Ollama should not be called")

    sidekick = Sidekick(retriever=retriever, client=ollama_client(handler))
    events = await collect(sidekick.ask("best pizza recipe"))
    assert events == [
        {"type": "sources", "sources": []},
        {"type": "token", "text": NO_CONTEXT_ANSWER},
        {"type": "done"},
    ]


async def test_history_is_sent_to_llm(retriever):
    captured = {}
    sidekick = Sidekick(retriever=retriever, client=ollama_client(streaming_ok(captured)))
    history = [
        {"role": "user", "content": "kafka or rabbitmq?"},
        {"role": "assistant", "content": "Kafka for replay."},
    ]
    await collect(sidekick.ask("what about ordering?", history=history))
    messages = captured["payload"]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert "what about ordering?" in messages[-1]["content"]


async def test_missing_model_yields_error_event(retriever):
    sidekick = Sidekick(
        retriever=retriever,
        client=ollama_client(lambda r: httpx.Response(404, json={"error": "model not found"})),
    )
    events = await collect(sidekick.ask("kafka"))
    error = next(e for e in events if e["type"] == "error")
    assert "ollama pull" in error["message"]
    assert events[-1] == {"type": "done"}


async def test_connection_failure_yields_error_event(retriever):
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    sidekick = Sidekick(retriever=retriever, client=ollama_client(handler))
    events = await collect(sidekick.ask("kafka"))
    assert any(e["type"] == "error" and "Cannot reach Ollama" in e["message"] for e in events)


def test_retrieval_query_includes_previous_question():
    history = [{"role": "user", "content": "kafka or rabbitmq?"}, {"role": "assistant", "content": "..."}]
    assert retrieval_query("what about ordering?", history) == "kafka or rabbitmq?\nwhat about ordering?"
    assert retrieval_query("standalone", []) == "standalone"


def test_build_messages_trims_history(monkeypatch):
    monkeypatch.setattr("src.sidekick.MAX_HISTORY_TURNS", 2)
    history = [{"role": "user", "content": str(i)} for i in range(5)]
    messages = build_messages("q", [], history)
    assert [m["content"] for m in messages[1:-1]] == ["3", "4"]
