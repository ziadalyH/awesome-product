"""Abstract base class for all retrieval strategies."""

from abc import ABC, abstractmethod
from typing import Dict, List
from app.models import DocSection


class BaseRetriever(ABC):
    """Interface that all retrieval strategies must implement."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        """Return a list of section IDs relevant to the query.

        Args:
            query: User's change-request string.
            docs: Full documentation keyed by page ID.
            section_index: Flat list of ``{id, page, section}`` dicts.

        Returns:
            Ordered list of section ID strings to pass to the editor.
        """
        ...
