"""
Markdown chunking and tokenization. Pure Python so it can be tested without
the embedding model or vector store installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.config import CHUNK_OVERLAP, CHUNK_SIZE

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?:])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class Chunk:
    content: str
    source: str
    section: str
    chunk_index: int


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, used for keyword (BM25) search."""
    return _TOKEN_RE.findall(text.lower())


def _iter_sections(content: str) -> list[tuple[list[str], list[str]]]:
    """
    Split markdown into (heading_path, paragraphs) sections.
    Headings inside fenced code blocks are ignored, and code blocks are kept
    as single paragraphs even when they contain blank lines.
    """
    sections: list[tuple[list[str], list[str]]] = []
    heading_stack: list[tuple[int, str]] = []
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False

    def flush_paragraph() -> None:
        if current:
            text = "\n".join(current).strip()
            if text:
                paragraphs.append(text)
            current.clear()

    def flush_section() -> None:
        flush_paragraph()
        if paragraphs:
            sections.append(([title for _, title in heading_stack], list(paragraphs)))
            paragraphs.clear()

    for line in content.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            current.append(line)
            continue
        if in_fence:
            current.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_section()
            level, title = len(heading.group(1)), heading.group(2)
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
        elif not line.strip():
            flush_paragraph()
        else:
            current.append(line)

    flush_section()
    return sections


def _split_long(text: str, limit: int) -> list[str]:
    """Split text longer than `limit` on sentence boundaries, falling back to words."""
    pieces: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if len(sentence) <= limit:
            pieces.append(sentence)
            continue
        line = ""
        for word in sentence.split():
            while len(word) > limit:  # pathological unbroken token
                pieces.append(word[:limit])
                word = word[limit:]
            if line and len(line) + 1 + len(word) > limit:
                pieces.append(line)
                line = word
            else:
                line = f"{line} {word}" if line else word
        if line:
            pieces.append(line)

    # Re-pack small pieces so we don't emit one chunk per sentence.
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + 1 + len(piece) <= limit:
            packed[-1] = f"{packed[-1]} {piece}"
        else:
            packed.append(piece)
    return packed


def _tail(text: str, size: int) -> str:
    """Last ~`size` characters of text, starting on a word boundary."""
    if size <= 0:
        return ""
    if len(text) <= size:
        return text
    cut = text[-size:]
    space = cut.find(" ")
    return cut[space + 1:] if space != -1 else cut


def chunk_document(
    content: str,
    source: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[Chunk]:
    """
    Chunk a markdown document section by section.

    Each chunk is prefixed with its heading breadcrumb (e.g. "Messaging Patterns > Outbox Pattern")
    so both the embedding and the LLM know what topic the text belongs to. Paragraphs are packed
    up to `chunk_size`; oversized paragraphs are split on sentence/word boundaries. Consecutive
    chunks within a section share up to `overlap` characters.
    """
    chunks: list[Chunk] = []

    for heading_path, paragraphs in _iter_sections(content):
        section = " > ".join(heading_path) or source
        prefix = f"{section}\n\n"
        budget = max(chunk_size - len(prefix), 100)

        units: list[str] = []
        for para in paragraphs:
            units.extend(_split_long(para, budget) if len(para) > budget else [para])

        body = ""
        for unit in units:
            if not body:
                body = unit
            elif len(body) + 2 + len(unit) <= budget:
                body = f"{body}\n\n{unit}"
            else:
                chunks.append(Chunk(prefix + body, source, section, len(chunks)))
                carry = _tail(body, overlap)
                body = f"{carry}\n\n{unit}" if carry and len(carry) + 2 + len(unit) <= budget else unit
        if body:
            chunks.append(Chunk(prefix + body, source, section, len(chunks)))

    return chunks
