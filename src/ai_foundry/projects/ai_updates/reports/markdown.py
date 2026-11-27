"""Markdown and HTML output for the same research report."""

import html
import os
import re
import tempfile
from pathlib import Path

from ..db.models import PaperSummary


class ReportRenderer:
    """Render and publish browser and Markdown reports."""

    def markdown_text(self, value: str) -> str:
        """Escape untrusted Markdown text.

        Args:
            value: Source or generated text.

        Returns:
            Escaped text.
        """
        # Escape HTML first, then Markdown punctuation.
        escaped: str = html.escape(value, quote=False)
        escaped = re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped)
        return escaped

    def render(self, entries: list[PaperSummary], mock: bool) -> tuple[str, str]:
        """Create both report formats.

        Args:
            entries: Report entries.
            mock: Whether summaries are placeholders.

        Returns:
            Markdown and complete HTML documents.
        """
        # Build both formats from the same immutable entries.
        heading: str = "AI research update" + (" — MOCK MODE" if mock else "")
        markdown_sections: list[str] = [f"# {heading}"]
        cards: list[str] = []
        for entry in entries:
            paper_title: str = self.markdown_text(entry.paper.title)
            summary_text: str = self.markdown_text(entry.summary)
            published: str = entry.paper.published.date().isoformat()
            markdown_sections.append(
                f"## {paper_title}\n\n{published} · [arXiv](<{entry.paper.url}>)\n\n"
                f"Based on the abstract.\n\n{summary_text}"
            )
            cards.append(
                f"<article><h2>{html.escape(entry.paper.title)}</h2>"
                f"<p>{published} · <a href='{html.escape(entry.paper.url, quote=True)}'>arXiv</a></p>"
                f"<p class='label'>Based on the abstract.</p><p>{html.escape(entry.summary)}</p></article>"
            )
        markdown: str = "\n\n".join(markdown_sections) + "\n"
        document: str = (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(heading)}</title><style>"
            "body{font:18px/1.6 system-ui;background:#f3f5f7;color:#172c39;max-width:900px;margin:40px auto;padding:0 24px}"
            "article{background:white;padding:24px;margin:20px 0;border-radius:12px}"
            "h2{line-height:1.3}a{color:#145ca4}.label{color:#526672;font-size:14px}"
            f"</style></head><body><h1>{html.escape(heading)}</h1>{''.join(cards)}</body></html>"
        )
        return markdown, document

    def publish(self, entries: list[PaperSummary], mock: bool, directory: Path) -> None:
        """Stage both reports before replacing their destinations.

        Args:
            entries: Completed summaries.
            mock: Whether the mock client was used.
            directory: Public output directory.

        Raises:
            OSError: If staging or replacement fails.
        """
        # Stage complete files before touching existing reports.
        markdown: str
        document: str
        markdown, document = self.render(entries, mock)
        directory.mkdir(parents=True, exist_ok=True)
        temporary_paths: list[tuple[Path, Path]] = []
        try:
            for name, content in (("research.md", markdown), ("index.html", document)):
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as temporary:
                    temporary_path: Path = Path(temporary.name)
                    temporary_paths.append((temporary_path, directory / name))
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
            # Failed publication leaves history uncommitted for retry.
            for temporary_path, destination in temporary_paths:
                temporary_path.replace(destination)
        finally:
            for temporary_path, destination in temporary_paths:
                temporary_path.unlink(missing_ok=True)
