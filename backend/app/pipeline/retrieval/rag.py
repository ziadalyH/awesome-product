"""RAG retriever: OpenAI embeddings + cosine similarity."""
import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from app.models import DocSection
from app.pipeline.retrieval.base import BaseRetriever


EMBEDDINGS_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "embeddings_cache.json"
)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Return the cosine similarity between two embedding vectors.

    Args:
        a: First embedding vector.
        b: Second embedding vector.

    Returns:
        Similarity score in ``[0.0, 1.0]``; 0.0 if either vector is zero.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RagRetriever(BaseRetriever):
    """Retrieves relevant doc sections using OpenAI embeddings and cosine similarity.

    Call ``build()`` once to embed all sections (results are cached to disk).
    Then use ``retrieve()`` or ``retrieve_scored()`` for each query.
    """

    def __init__(self, embedding_model: str = "text-embedding-3-small", top_k: int = 10):
        """
        Args:
            embedding_model: OpenAI embedding model name.
            top_k: Default number of top sections to return.
        """
        self.embedding_model = embedding_model
        self.top_k = top_k
        self._client: Optional[AsyncOpenAI] = None
        self.logger = logging.getLogger(__name__)
        self._embeddings: Dict[str, List[float]] = {}
        self._ready = False

    @property
    def client(self) -> AsyncOpenAI:
        """Lazily-initialised ``AsyncOpenAI`` client."""
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    async def build(self, docs: Dict[str, List[DocSection]]) -> None:
        """Embed all doc sections and cache results to disk.

        Loads from ``embeddings_cache.json`` if it exists and is up-to-date;
        otherwise calls the OpenAI embeddings API in batches of 100.

        Args:
            docs: Full documentation keyed by page ID.
        """
        cache_path = os.path.abspath(EMBEDDINGS_CACHE_PATH)
        all_sections: Dict[str, str] = {
            section.id: f"{section.section_title}\n\n{section.content}"
            for page_sections in docs.values()
            for section in page_sections
        }

        if os.path.exists(cache_path):
            with open(cache_path) as f:
                cached = json.load(f)
            cached_ids = set(cached.get("ids", []))
            if cached_ids == set(all_sections.keys()):
                self.logger.info(f"Loading embeddings from cache ({len(cached_ids)} sections)")
                self._embeddings = cached["embeddings"]
                self._ready = True
                return
            added = len(set(all_sections.keys()) - cached_ids)
            removed = len(cached_ids - set(all_sections.keys()))
            self.logger.info(f"Embeddings cache stale (added={added}, removed={removed}), re-embedding...")

        self.logger.info(f"Computing embeddings for {len(all_sections)} sections...")
        ids = list(all_sections.keys())
        texts = [all_sections[i] for i in ids]
        embeddings: Dict[str, List[float]] = {}

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            response = await self.client.embeddings.create(model=self.embedding_model, input=batch_texts)
            for j, emb_obj in enumerate(response.data):
                embeddings[batch_ids[j]] = emb_obj.embedding
            self.logger.info(f"Embedded {min(i + batch_size, len(ids))}/{len(ids)} sections")

        self._embeddings = embeddings
        self._ready = True

        with open(cache_path, "w") as f:
            json.dump({"ids": ids, "embeddings": embeddings}, f)
        self.logger.info(f"Embeddings saved to: {cache_path}")

    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        results = await self.retrieve_scored(query)
        return [sid for sid, _ in results]

    async def retrieve_scored(self, query: str, top_k: Optional[int] = None) -> List[Tuple[str, float]]:
        """Return ``(section_id, score)`` tuples sorted by descending similarity.

        Args:
            query: Query text to embed.
            top_k: Number of results; defaults to ``self.top_k``.

        Returns:
            List of ``(section_id, cosine_similarity)`` pairs.

        Raises:
            RuntimeError: If ``build()`` has not been called first.
        """
        if not self._ready:
            raise RuntimeError("RagRetriever.build() must be called before retrieve()")
        k = top_k if top_k is not None else self.top_k
        response = await self.client.embeddings.create(model=self.embedding_model, input=[query])
        query_vec = response.data[0].embedding
        scores: List[Tuple[str, float]] = [
            (sid, _cosine_similarity(query_vec, vec))
            for sid, vec in self._embeddings.items()
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:k]

    def invalidate_cache(self) -> None:
        """Delete the on-disk embeddings cache and reset in-memory state."""
        cache_path = os.path.abspath(EMBEDDINGS_CACHE_PATH)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            self.logger.info("Embeddings cache invalidated")
        self._embeddings = {}
        self._ready = False
