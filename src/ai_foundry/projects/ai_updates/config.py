"""Configuration for one research update."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UpdateConfig:
    """Settings shared by source, model, history, and report stages."""

    query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL"
    lookback_days: int = 7
    limit: int = 5
    model: str = "gpt-4.1-mini"
    mock: bool = False
    report_directory: Path = Path("reports/ai-updates")
    history_path: Path = Path("data/ai-updates.sqlite3")

    def validate(self) -> None:
        """Validate input and keep database files outside public output.

        Raises:
            ValueError: If input settings or paths are unsafe.
        """
        # Validate bounds before contacting external services.
        if not self.query.strip() or self.lookback_days < 1 or self.limit < 1:
            raise ValueError("Query must be nonempty and lookback days and limit must be positive")
        if self.history_path.resolve().is_relative_to(self.report_directory.resolve()):
            raise ValueError("History must be outside the served report directory")
