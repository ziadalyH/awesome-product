"""Documentation fetcher: scrapes and caches OpenAI Agents SDK docs as structured sections."""

import asyncio
import httpx
import json
import logging
import os
import re
from typing import Dict, List
from bs4 import BeautifulSoup, Tag
from .models import DocSection

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs_cache.json")


def _make_id(page_id: str, section_title: str) -> str:
    """Return a stable section ID from a page ID and section heading.

    Args:
        page_id: The doc page slug (e.g. ``"tools"``).
        section_title: The raw heading text.

    Returns:
        A string in the form ``"<page_id>#<slugified-title>"``.
    """
    slug = re.sub(r"[^\w\s-]", "", section_title.lower())
    slug = re.sub(r"[\s]+", "-", slug).strip("-")
    return f"{page_id}#{slug}"

BASE_URL = "https://openai.github.io/openai-agents-python"

DOC_PAGES = [
    "",
    "quickstart",
    "agents",
    "running_agents",
    "results",
    "streaming",
    "tools",
    "handoffs",
    "context",
    "guardrails",
    "multi_agent",
    "human_in_the_loop",
    "mcp",
    "models",
    "config",
    "tracing",
    "usage",
    "repl",
    "visualization",
    "sessions",
    "sessions/advanced_sqlite_session",
    "sessions/encrypted_session",
    "sessions/sqlalchemy_session",
    "realtime/guide",
    "realtime/quickstart",
    "realtime/transport",
    "voice/quickstart",
    "voice/pipeline",
    "voice/tracing",
    "release",
    "examples",
]


class DocFetcher:
    """Fetches and caches OpenAI Agents SDK documentation as ``DocSection`` objects.

    On first run the pages listed in ``DOC_PAGES`` are scraped and saved to
    ``docs_cache.json``.  Subsequent runs load directly from the cache.
    """

    def __init__(self):
        self.docs: Dict[str, List[DocSection]] = {}
        self.logger = logging.getLogger(__name__)

    async def fetch_docs(self):
        """Load docs from cache if available, otherwise scrape and save cache."""
        cache = os.path.abspath(CACHE_PATH)
        if os.path.exists(cache):
            self.logger.info(f"Loading docs from cache: {cache}")
            with open(cache) as f:
                data = json.load(f)
            for page_id, sections in data.items():
                self.docs[page_id] = [DocSection(**s) for s in sections]
            self.logger.info(f"Loaded {len(self.docs)} pages from cache ({sum(len(v) for v in self.docs.values())} sections)")
            return

        self.logger.info("No cache found — scraping docs (this only happens once)...")
        await self._scrape_docs()

        with open(cache, "w") as f:
            json.dump(
                {pid: [s.model_dump() for s in secs] for pid, secs in self.docs.items()},
                f,
            )
        self.logger.info(f"Docs cached to: {cache}")

    async def _scrape_docs(self):
        """Scrape all pages in ``DOC_PAGES`` concurrently and populate ``self.docs``."""
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for page in DOC_PAGES:
                url = f"{BASE_URL}/{page}/" if page else f"{BASE_URL}/"
                content = await self._fetch_page(client, url)
                if content:
                    page_id = page if page else "index"
                    sections = self._parse_html(content, page_id)
                    if sections:
                        self.docs[page_id] = sections
                        self.logger.info(f"Scraped {len(sections)} sections from '{page_id}'")
                await asyncio.sleep(0.1)

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> str:
        """Fetch raw HTML for a URL; returns empty string on non-200 or error."""
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            self.logger.warning(f"Got {resp.status_code} for {url}")
            return ""
        except Exception as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return ""

    def _parse_html(self, html: str, page_id: str) -> List[DocSection]:
        """Parse an HTML page and split it into ``DocSection`` objects by heading.

        Args:
            html: Raw HTML string for the page.
            page_id: Slug identifier for the page (used in section IDs).

        Returns:
            Ordered list of ``DocSection`` objects extracted from the article element.
        """
        soup = BeautifulSoup(html, "html.parser")
        article = soup.find("article") or soup.find("main")
        if not article or not isinstance(article, Tag):
            return []

        sections: List[DocSection] = []
        current_title = page_id.split("/")[-1].replace("-", " ").title()
        current_chunks: List[str] = []
        line_counter = 0
        current_start = 0

        for element in article.children:
            if not isinstance(element, Tag):
                continue
            tag = element.name
            if tag in ("h1", "h2", "h3"):
                if current_chunks:
                    body = "\n\n".join(current_chunks).strip()
                    if body:
                        sections.append(DocSection(
                            id=_make_id(page_id, current_title),
                            file=page_id,
                            section_title=current_title,
                            content=body,
                            line_start=current_start,
                            line_end=line_counter,
                        ))
                current_title = element.get_text(strip=True)
                current_chunks = []
                current_start = line_counter
                line_counter += 1
            elif tag == "div" and "highlight" in element.get("class", []):
                code = element.find("code")
                if code:
                    current_chunks.append(f"```\n{code.get_text()}\n```")
                line_counter += 1
            elif tag in ("p", "ul", "ol", "table", "blockquote"):
                text = element.get_text(separator=" ", strip=True)
                if text:
                    current_chunks.append(text)
                line_counter += 1

        if current_chunks:
            body = "\n\n".join(current_chunks).strip()
            if body:
                sections.append(DocSection(
                    id=_make_id(page_id, current_title),
                    file=page_id,
                    section_title=current_title,
                    content=body,
                    line_start=current_start,
                    line_end=line_counter,
                ))

        return sections
