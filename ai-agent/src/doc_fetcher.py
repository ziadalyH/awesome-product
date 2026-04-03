import httpx
import base64
import re
import logging
from typing import Dict, List
from .models import DocSection


class DocFetcher:
    GITHUB_API = "https://api.github.com"
    REPO = "openai/openai-agents-python"
    DOCS_PATH = "docs"

    def __init__(self):
        self.docs: Dict[str, List[DocSection]] = {}
        self.logger = logging.getLogger(__name__)

    async def fetch_docs(self):
        """Fetch all markdown docs from GitHub and parse into sections."""
        async with httpx.AsyncClient(timeout=30) as client:
            files = await self._get_doc_files(client)
            for file_path in files:
                content = await self._fetch_file(client, file_path)
                if content:
                    sections = self._parse_sections(content, file_path)
                    if sections:
                        self.docs[file_path] = sections
                        self.logger.info(f"Loaded {len(sections)} sections from {file_path}")

    async def _get_doc_files(self, client: httpx.AsyncClient) -> List[str]:
        files = []
        await self._scan_directory(client, self.DOCS_PATH, files)
        return files

    async def _scan_directory(self, client: httpx.AsyncClient, path: str, files: List[str]):
        url = f"{self.GITHUB_API}/repos/{self.REPO}/contents/{path}"
        try:
            resp = await client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code != 200:
                self.logger.warning(f"GitHub API returned {resp.status_code} for {path}")
                return
            for item in resp.json():
                if item["type"] == "file" and item["name"].endswith(".md"):
                    files.append(item["path"])
                elif item["type"] == "dir":
                    await self._scan_directory(client, item["path"], files)
        except Exception as e:
            self.logger.error(f"Error scanning {path}: {e}")

    async def _fetch_file(self, client: httpx.AsyncClient, path: str) -> str:
        url = f"{self.GITHUB_API}/repos/{self.REPO}/contents/{path}"
        try:
            resp = await client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code != 200:
                return ""
            data = resp.json()
            return base64.b64decode(data["content"]).decode("utf-8")
        except Exception as e:
            self.logger.error(f"Error fetching {path}: {e}")
            return ""

    def _parse_sections(self, content: str, file_path: str) -> List[DocSection]:
        """Parse markdown into sections split by headings (h1-h3)."""
        sections = []
        lines = content.split("\n")
        current_title = file_path.split("/")[-1].replace(".md", "").replace("-", " ").title()
        current_lines: List[str] = []
        current_start = 0

        for i, line in enumerate(lines):
            if re.match(r"^#{1,3} ", line):
                if current_lines:
                    body = "\n".join(current_lines).strip()
                    if body:
                        sections.append(DocSection(
                            file=file_path,
                            section_title=current_title,
                            content=body,
                            line_start=current_start,
                            line_end=i - 1,
                        ))
                current_title = re.sub(r"^#{1,3} ", "", line).strip()
                current_lines = [line]
                current_start = i
            else:
                current_lines.append(line)

        if current_lines:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append(DocSection(
                    file=file_path,
                    section_title=current_title,
                    content=body,
                    line_start=current_start,
                    line_end=len(lines) - 1,
                ))
        return sections
