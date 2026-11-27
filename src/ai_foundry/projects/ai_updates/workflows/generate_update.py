"""Compose discovery, summaries, reports, and durable history."""

from datetime import datetime, timedelta, timezone

from ..agents.summarizer import Summarizer
from ..config import UpdateConfig
from ..db.dal import UpdateDataAccess
from ..db.models import Paper, PaperSummary
from ..reports.markdown import ReportRenderer
from ..sources.papers import ArxivSource


class UpdateWorkflow:
    """Generate one serialized research report."""

    def __init__(self, source: ArxivSource, summarizer: Summarizer, renderer: ReportRenderer) -> None:
        """Compose workflow dependencies.

        Args:
            source: arXiv paper source.
            summarizer: Abstract summarization agent.
            renderer: Report publisher.
        """
        # Keep orchestration independent of concrete model selection.
        self.source: ArxivSource = source
        self.summarizer: Summarizer = summarizer
        self.renderer: ReportRenderer = renderer

    def run(self, config: UpdateConfig) -> int:
        """Generate a report and record its paper IDs.

        Args:
            config: Validated run settings.

        Returns:
            Number of newly reported papers.

        Raises:
            OSError: If retrieval or publication fails.
            ValueError: If configuration or metadata is invalid.
            sqlite3.Error: If history access fails.
        """
        # Reserve the history before selecting unseen papers.
        config.validate()
        data_access: UpdateDataAccess = UpdateDataAccess(config.history_path)
        with data_access:
            now: datetime = datetime.now(timezone.utc)
            cutoff: datetime = now - timedelta(days=config.lookback_days)
            reported_ids: set[str] = data_access.history.reported_ids()
            papers: list[Paper] = self.source.find(config.query, cutoff, now, reported_ids, config.limit)
            if not papers:
                count: int = 0
                return count
            # Publish both outputs before committing reported IDs.
            summaries: list[PaperSummary] = [self.summarizer.summarize(paper) for paper in papers]
            self.renderer.publish(summaries, config.mock, config.report_directory)
            data_access.history.record(summaries)
            count = len(summaries)
            return count
