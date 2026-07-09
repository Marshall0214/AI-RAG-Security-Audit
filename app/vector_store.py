import hashlib
import math
import os

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
import chromadb.telemetry.product.posthog as chroma_posthog
from chromadb.api.types import Documents, EmbeddingFunction
from chromadb.config import Settings

from app.models import Document, DocumentChunk, Role, User
from app.rag import tokenize

chroma_posthog.Posthog._direct_capture = lambda self, event: None

MIN_RELEVANCE_SCORE = 350


class LocalHashEmbeddingFunction(EmbeddingFunction):
    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def __call__(self, input: Documents) -> list[list[float]]:
        return [self._embed(document) for document in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class ChromaRagStore:
    def __init__(self) -> None:
        self.client = chromadb.EphemeralClient(
            Settings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name="rag_document_chunks",
            embedding_function=LocalHashEmbeddingFunction(),
            metadata={
                "description": (
                    "RAG chunks with owner_id and tenant_id metadata for "
                    "authorization filtering."
                )
            },
        )

    def add_chunk(self, chunk: DocumentChunk, document: Document) -> None:
        self.collection.add(
            ids=[self._chunk_vector_id(chunk.id)],
            documents=[f"{document.title}\n{chunk.text}"],
            metadatas=[
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "owner_id": chunk.owner_id,
                    "tenant_id": chunk.tenant_id,
                    "document_title": document.title,
                }
            ],
        )

    def search_for_user(
        self,
        query: str,
        user: User,
        max_results: int,
    ) -> list[tuple[int, int]]:
        where = None
        if user.role != Role.ADMIN:
            where = {
                "$and": [
                    {"owner_id": {"$eq": user.id}},
                    {"tenant_id": {"$eq": user.tenant_id}},
                ]
            }

        return self._query(query=query, max_results=max_results, where=where)

    def search_all(self, query: str, max_results: int) -> list[tuple[int, int]]:
        return self._query(query=query, max_results=max_results, where=None)

    def _query(
        self,
        query: str,
        max_results: int,
        where: dict[str, object] | None,
    ) -> list[tuple[int, int]]:
        if self.collection.count() == 0:
            return []

        n_results = min(max_results, self.collection.count())
        result = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["metadatas", "distances"],
        )

        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        matches: list[tuple[int, int]] = []
        for metadata, distance in zip(metadatas[0], distances[0]):
            chunk_id = int(metadata["chunk_id"])
            score = max(1, int(round((1 / (1 + float(distance))) * 1000)))
            if score >= MIN_RELEVANCE_SCORE:
                matches.append((chunk_id, score))

        return matches

    def _chunk_vector_id(self, chunk_id: int) -> str:
        return f"chunk-{chunk_id}"
