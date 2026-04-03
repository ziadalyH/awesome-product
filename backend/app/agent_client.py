import httpx
import os
from typing import List
from .models import EditSuggestion, SuggestionStatus


AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8001")


async def get_suggestions(query: str) -> List[EditSuggestion]:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{AGENT_BASE_URL}/api/agent/suggest",
            json={"query": query},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            EditSuggestion(
                id=s["id"],
                file=s["file"],
                section_title=s["section_title"],
                current_content=s["current_content"],
                suggested_content=s["suggested_content"],
                reason=s["reason"],
                status=SuggestionStatus(s["status"]),
            )
            for s in data["suggestions"]
        ]
