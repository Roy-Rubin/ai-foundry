"""Recent paper discovery through the arXiv Atom API."""

import re
import time
from datetime import datetime, timezone
from urllib.parse import SplitResult, urlencode, urlsplit
from urllib.request import Request
from xml.etree import ElementTree

from ai_foundry.core.sources.http import HttpClient
from ..db.models import Paper

ATOM: dict[str, str] = {"atom": "http://www.w3.org/2005/Atom"}
PAGE_SIZE: int = 100


class ArxivSource:
    """Retrieve and paginate recent papers without downloading PDFs."""

    def __init__(self, transport: HttpClient) -> None:
        """Configure the source.

        Args:
            transport: HTTP transport with bounded retries.
        """
        # Reuse the core transport.
        self.transport: HttpClient = transport

    def find(self, query: str, cutoff: datetime, now: datetime, seen: set[str], limit: int) -> list[Paper]:
        """Find unseen submissions within a UTC time window.

        Args:
            query: arXiv query expression.
            cutoff: Inclusive earliest first submission.
            now: Inclusive latest submission.
            seen: Already reported IDs.
            limit: Maximum unseen papers.

        Returns:
            New papers in source order.

        Raises:
            ValueError: If arXiv returns invalid metadata or an API error.
            OSError: If retrieval fails.
        """
        # Apply the date filter remotely and verify precise timestamps locally.
        search: str = (
            f"({query}) AND submittedDate:[{cutoff:%Y%m%d%H%M} TO {now:%Y%m%d%H%M}]"
        )
        selected: list[Paper] = []
        encountered: set[str] = set(seen)
        start: int = 0
        while len(selected) < limit:
            parameters: str = urlencode({
                "search_query": search, "start": start, "max_results": PAGE_SIZE,
                "sortBy": "submittedDate", "sortOrder": "descending",
            })
            request: Request = Request(
                f"https://export.arxiv.org/api/query?{parameters}",
                headers={"User-Agent": "ai-foundry-research/0.1"},
            )
            payload: bytes = self.transport.request(request)
            papers: list[Paper] = self.parse(payload)
            for paper in papers:
                if cutoff <= paper.published <= now and paper.identifier not in encountered:
                    selected.append(paper)
                    encountered.add(paper.identifier)
                    if len(selected) == limit:
                        break
            if len(papers) < PAGE_SIZE:
                break
            start += PAGE_SIZE
            # Respect arXiv's recommended spacing for paginated requests.
            time.sleep(3)
        return selected

    def parse(self, payload: bytes) -> list[Paper]:
        """Parse an Atom response into validated paper metadata.

        Args:
            payload: XML response bytes.

        Returns:
            Parsed papers.

        Raises:
            ValueError: If the feed or entries are invalid.
        """
        # Validate XML structure before extracting entries.
        try:
            root: ElementTree.Element = ElementTree.fromstring(payload)
        except ElementTree.ParseError as error:
            raise ValueError("Invalid arXiv XML response") from error
        if root.tag != f"{{{ATOM['atom']}}}feed":
            raise ValueError("Expected an arXiv Atom feed")
        papers: list[Paper] = []
        for entry in root.findall("atom:entry", ATOM):
            identifier_url: str = entry.findtext("atom:id", default="", namespaces=ATOM).strip()
            parsed_url: SplitResult = urlsplit(identifier_url)
            if parsed_url.path.startswith("/api/errors"):
                raise ValueError(entry.findtext("atom:summary", default="arXiv API error", namespaces=ATOM))
            if parsed_url.hostname not in {"arxiv.org", "www.arxiv.org"} or not parsed_url.path.startswith("/abs/"):
                raise ValueError("Invalid arXiv paper ID")
            identifier: str = re.sub(r"v\d+$", "", parsed_url.path.removeprefix("/abs/"))
            if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z.-]+/\d{7})", identifier):
                raise ValueError("Invalid arXiv ID format")
            title: str = " ".join(entry.findtext("atom:title", default="", namespaces=ATOM).split())
            abstract: str = " ".join(entry.findtext("atom:summary", default="", namespaces=ATOM).split())
            published_text: str = entry.findtext("atom:published", default="", namespaces=ATOM)
            published: datetime = datetime.fromisoformat(published_text.replace("Z", "+00:00"))
            if not title or not abstract or published.tzinfo is None:
                raise ValueError("Incomplete arXiv paper metadata")
            papers.append(Paper(identifier, title, abstract, published.astimezone(timezone.utc),
                                f"https://arxiv.org/abs/{identifier}"))
        return papers
