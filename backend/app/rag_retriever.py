"""
RAG-based section retriever using OpenAI embeddings + cosine similarity.
Embeddings are computed once on startup and cached to disk.
"""
import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

from openai import AsyncOpenAI
from .models import DocSection

EMBEDDINGS_CACHE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "embeddings_cache.json"
)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RagRetriever:
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.embedding_model = embedding_model
        self._client: Optional[AsyncOpenAI] = None  # initialized lazily on first use
        self.logger = logging.getLogger(__name__)
        self._embeddings: Dict[str, List[float]] = {}
        self._ready = False

    @property
    def client(self) -> AsyncOpenAI:
        """Lazily create the OpenAI client so the API key is available by the time it's needed."""
        if self._client is None:
            self._client = AsyncOpenAI()
        return self._client

    async def build(self, docs: Dict[str, List[DocSection]]) -> None:
        """
        Build the embedding index from docs.
        Loads from disk cache if it covers all current section IDs,
        otherwise re-embeds and saves to disk.
        """
        cache_path = os.path.abspath(EMBEDDINGS_CACHE_PATH)

        # Build section_id -> embed text map
        all_sections: Dict[str, str] = {
            section.id: f"{section.section_title}\n\n{section.content}"
            for page_sections in docs.values()
            for section in page_sections
        }

        # Use disk cache if it matches the current section set exactly
        if os.path.exists(cache_path):
            with open(cache_path) as f:
                cached = json.load(f)
            cached_ids = set(cached.get("ids", []))
            if cached_ids == set(all_sections.keys()):
                self.logger.info(f"Loading embeddings from cache ({len(cached_ids)} sections)")
                self._embeddings = cached["embeddings"]
                self._ready = True
                return
            else:
                added = len(set(all_sections.keys()) - cached_ids)
                removed = len(cached_ids - set(all_sections.keys()))
                self.logger.info(
                    f"Embeddings cache stale (added={added}, removed={removed}), re-embedding..."
                )

        # Embed all sections in batches
        self.logger.info(f"Computing embeddings for {len(all_sections)} sections...")
        ids = list(all_sections.keys())
        texts = [all_sections[i] for i in ids]
        embeddings: Dict[str, List[float]] = {}

        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=batch_texts,
            )
            for j, emb_obj in enumerate(response.data):
                embeddings[batch_ids[j]] = emb_obj.embedding
            self.logger.info(
                f"Embedded {min(i + batch_size, len(ids))}/{len(ids)} sections"
            )

        self._embeddings = embeddings
        self._ready = True

        with open(cache_path, "w") as f:
            json.dump({"ids": ids, "embeddings": embeddings}, f)
        self.logger.info(f"Embeddings saved to: {cache_path}")

    async def retrieve(
        self, query: str, top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Embed the query and return the top_k most similar section IDs.
        Returns list of (section_id, score) sorted by descending score.
        """
        if not self._ready:
            raise RuntimeError("RagRetriever.build() must be called before retrieve()")

        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=[query],
        )
        query_vec = response.data[0].embedding

        scores: List[Tuple[str, float]] = [
            (sid, _cosine_similarity(query_vec, vec))
            for sid, vec in self._embeddings.items()
        ]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def invalidate_cache(self) -> None:
        """
        Delete the on-disk embeddings cache so it is rebuilt on next startup.
        Call this after docs are updated via approved suggestions.
        """
        cache_path = os.path.abspath(EMBEDDINGS_CACHE_PATH)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            self.logger.info("Embeddings cache invalidated")
        self._embeddings = {}
        self._ready = False
