import re

from app.models import DocumentChunk

WORD_PATTERN = re.compile(r"[A-Za-z0-9_\-\u4e00-\u9fff]+")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(end - overlap, start + 1)

    return chunks


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in WORD_PATTERN.findall(text)]


def score_chunk(query: str, chunk: DocumentChunk, document_title: str) -> int:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0

    searchable = f"{document_title} {chunk.text}".lower()
    score = 0
    for token in query_tokens:
        if token in searchable:
            score += searchable.count(token)

    return score
