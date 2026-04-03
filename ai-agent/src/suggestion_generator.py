import json
import logging
import uuid
from typing import Dict, List
from openai import AsyncOpenAI
from .models import DocSection, EditSuggestion, SuggestionStatus


class SuggestionGenerator:
    def __init__(self, openai_api_key: str, logger: logging.Logger):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.logger = logger
        self.model = "gpt-4o"

    async def generate(
        self, query: str, docs: Dict[str, List[DocSection]]
    ) -> List[EditSuggestion]:
        all_sections: List[DocSection] = []
        for sections in docs.values():
            all_sections.extend(sections)

        relevant = await self._find_relevant_sections(query, all_sections)
        if not relevant:
            self.logger.info("No relevant sections identified for query")
            return []

        return await self._generate_suggestions(query, relevant)

    async def _find_relevant_sections(
        self, query: str, sections: List[DocSection]
    ) -> List[DocSection]:
        index = [
            {"index": i, "file": s.file, "section": s.section_title, "preview": s.content[:300]}
            for i, s in enumerate(sections)
        ]

        prompt = f"""You are a documentation expert. A user wants to update the OpenAI Agents SDK documentation with this change:

"{query}"

Below is an index of all documentation sections. Identify which sections need to be updated based on the change request.

Section index:
{json.dumps(index, indent=2)}

Return JSON: {{"relevant_indices": [list of integer indices]}}
Only include sections that directly need modification. Return an empty list if none apply."""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a documentation expert. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            result = json.loads(resp.choices[0].message.content)
            indices = result.get("relevant_indices", [])
            self.logger.info(f"Identified {len(indices)} relevant sections: {indices}")
            return [sections[i] for i in indices if 0 <= i < len(sections)]
        except Exception as e:
            self.logger.error(f"Error finding relevant sections: {e}")
            return []

    async def _generate_suggestions(
        self, query: str, sections: List[DocSection]
    ) -> List[EditSuggestion]:
        sections_text = ""
        for i, s in enumerate(sections):
            sections_text += f"\n=== [{i}] File: {s.file} | Section: {s.section_title} ===\n{s.content}\n"

        prompt = f"""You are a technical documentation editor. Apply this change request to the documentation sections below and return edit suggestions.

Change request: "{query}"

Documentation sections to update:
{sections_text}

For each section that needs updating, produce a precise suggestion. Keep unchanged sections out.

Return JSON:
{{
  "suggestions": [
    {{
      "file": "path/to/file.md",
      "section_title": "Section title",
      "current_content": "The full current text of the section (verbatim)",
      "suggested_content": "The full updated text with your changes applied",
      "reason": "Brief explanation of why this change is needed"
    }}
  ]
}}"""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation editor. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=4096,
            )
            result = json.loads(resp.choices[0].message.content)
            raw = result.get("suggestions", [])
            suggestions = []
            for s in raw:
                suggestions.append(
                    EditSuggestion(
                        id=str(uuid.uuid4()),
                        file=s.get("file", ""),
                        section_title=s.get("section_title", ""),
                        current_content=s.get("current_content", ""),
                        suggested_content=s.get("suggested_content", ""),
                        reason=s.get("reason", ""),
                        status=SuggestionStatus.PENDING,
                    )
                )
            self.logger.info(f"Generated {len(suggestions)} suggestions")
            return suggestions
        except Exception as e:
            self.logger.error(f"Error generating suggestions: {e}")
            return []
