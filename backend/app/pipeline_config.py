from dataclasses import dataclass
from typing import Literal


@dataclass
class PipelineConfig:
    triage_model: str = "gpt-4o-mini"
    editor_model: str = "gpt-4o-mini"
    max_sections_in_prompt: int = 328
    verbose_logging: bool = False

    # --- RAG settings ---
    # "triage" uses the LLM triage agent (original behaviour)
    # "rag"    uses OpenAI embeddings + cosine similarity
    retrieval_mode: Literal["triage", "rag", "hybrid", "auto"] = "triage"
    rag_top_k: int = 10           # top-K for pure RAG mode
    hybrid_rag_top_k: int = 20    # top-K for hybrid RAG stage
    rag_embedding_model: str = "text-embedding-3-small"


DEFAULT_CONFIG = PipelineConfig()
