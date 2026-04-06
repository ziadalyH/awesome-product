from dataclasses import dataclass


@dataclass
class PipelineConfig:
    # Used by validator, precheck, triage, signal extractor, hybrid filters
    model: str = "gpt-4o-mini"
    editor_model: str = "gpt-4o-mini"

    # RAG settings
    rag_top_k: int = 10
    rag_embedding_model: str = "text-embedding-3-small"

    # Hybrid settings
    hybrid_rag_top_k: int = 20

    # Triage settings
    max_sections_in_prompt: int = 328

    verbose_logging: bool = False


DEFAULT_CONFIG = PipelineConfig()
