from src.chunking import _split_long, _tail, chunk_document, tokenize

DOC = """# Messaging Patterns

Intro paragraph about messaging.

## Kafka

Kafka is a distributed log.

```python
# this is a comment, not a heading

print("hi")
```

## Outbox Pattern

### Relay

The relay polls the outbox table.
"""


def test_chunks_carry_heading_breadcrumbs():
    chunks = chunk_document(DOC, "messaging.md")
    assert [c.section for c in chunks] == [
        "Messaging Patterns",
        "Messaging Patterns > Kafka",
        "Messaging Patterns > Outbox Pattern > Relay",
    ]
    assert chunks[1].content.startswith("Messaging Patterns > Kafka\n\n")
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_code_fence_comments_are_not_headings_and_stay_together():
    kafka = chunk_document(DOC, "m.md")[1]
    assert "# this is a comment, not a heading" in kafka.content
    assert 'print("hi")' in kafka.content


def test_chunks_respect_size_and_word_boundaries():
    words = [f"word{i}" for i in range(400)]
    doc = "# Big\n\n" + " ".join(words)
    chunks = chunk_document(doc, "big.md", chunk_size=300, overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 300
        body = chunk.content.split("\n\n", 1)[1]
        assert all(token in words for token in body.split())  # no word was cut in half


def test_consecutive_chunks_overlap():
    paras = "\n\n".join(f"Paragraph number {i} talks about sharding strategies in depth." for i in range(20))
    chunks = chunk_document("# S\n\n" + paras, "s.md", chunk_size=300, overlap=60)
    assert chunks[0].content[-30:] in chunks[1].content


def test_split_long_prefers_sentences():
    text = "One short sentence. " * 10 + "Two."
    pieces = _split_long(text.strip(), 60)
    assert all(len(p) <= 60 for p in pieces)
    assert all(p.endswith(".") for p in pieces)


def test_tail_starts_on_word_boundary():
    assert _tail("alpha beta gamma delta", 12) == "gamma delta"
    assert _tail("short", 50) == "short"
    assert _tail("anything", 0) == ""


def test_tokenize_keeps_alphanumeric_terms():
    assert tokenize("Use 2PC or a Saga? PACELC!") == ["use", "2pc", "or", "a", "saga", "pacelc"]
