from abc import ABC, abstractmethod
from typing import Dict, List
from app.models import DocSection


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        docs: Dict[str, List[DocSection]],
        section_index: List[Dict],
    ) -> List[str]:
        """Return a list of section IDs relevant to the query."""
        ...
