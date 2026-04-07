"""Pipeline configuration dataclass and default singleton."""

from dataclasses import dataclass


@dataclass
class PipelineConfig:
    """Tunable parameters for the documentation-update pipeline.

    Attributes:
        model: Chat model used by validator, pre-check, triage, and filter agents.
        editor_model: Chat model used by the editor agent.
        rag_top_k: Number of top sections returned by RAG retrieval.
        rag_embedding_model: OpenAI embedding model used to build the RAG index.
        hybrid_rag_top_k: Candidate pool size for the hybrid retriever's RAG pass.
        max_sections_in_prompt: Maximum sections shown to the triage agent.
        verbose_logging: Enable extra debug logging when True.
    """

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
