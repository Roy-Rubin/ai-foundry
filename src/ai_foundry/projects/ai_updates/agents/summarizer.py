"""Abstract-only summarization."""

from pathlib import Path

from ai_foundry.core.llm.client import TextClient
from ..models import Paper, PaperSummary


class Summarizer:
    """Apply a fixed prompt to titles and abstracts."""

    def __init__(self, client: TextClient) -> None:
        """Load the prompt.

        Args:
            client: Live or mock generation client.
        """
        # Load the same prompt for both client implementations.
        self.client: TextClient = client
        self.instructions: str = (
            Path(__file__).parents[1] / "prompts" / "summary.txt"
        ).read_text(encoding="utf-8")

    def summarize(self, paper: Paper) -> PaperSummary:
        """Summarize one abstract.

        Args:
            paper: Source paper.

        Returns:
            Summary paired with original bibliographic metadata.
        """
        # Restrict source material to the title and abstract.
        source: str = f"Title: {paper.title}\nAbstract: {paper.abstract}"
        summary: str = self.client.generate(self.instructions, source)
        result: PaperSummary = PaperSummary(paper, summary)
        return result
