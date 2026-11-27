"""Offline regression coverage for research updates."""

import contextlib
import io
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request

from ai_foundry.core.llm.client import MockTextClient, OpenAITextClient
from ai_foundry.core.sources.http import HttpClient
from ai_foundry.core.db.sqlite import SQLiteDatabase
from ai_foundry.projects.ai_updates.agents.summarizer import Summarizer
from ai_foundry.projects.ai_updates.config import UpdateConfig
from ai_foundry.projects.ai_updates.db.history import ReportHistoryStore
from ai_foundry.projects.ai_updates.main import main
from ai_foundry.projects.ai_updates.db.models import Paper, PaperSummary
from ai_foundry.projects.ai_updates.reports.markdown import ReportRenderer
from ai_foundry.projects.ai_updates.sources.papers import ArxivSource
from ai_foundry.projects.ai_updates.workflows.generate_update import UpdateWorkflow

FIXTURE: bytes = (Path(__file__).parent / "fixtures/arxiv.xml").read_bytes()


class ResearchTests(unittest.TestCase):
    """Exercise the workflow through its public entry points."""

    def test_pagination_dates_and_revisions(self) -> None:
        """Skip seen IDs and revisions before enforcing the limit."""
        # Return a full page followed by an unseen result.
        transport: Mock = Mock()
        transport.request.side_effect = [FIXTURE, FIXTURE]
        source: ArxivSource = ArxivSource(transport)
        with patch("ai_foundry.projects.ai_updates.sources.papers.PAGE_SIZE", 3), patch(
            "ai_foundry.projects.ai_updates.sources.papers.time.sleep"
        ):
            papers: list[Paper] = source.find(
                "cat:cs.AI", datetime(2026, 11, 24, tzinfo=timezone.utc),
                datetime(2026, 11, 26, tzinfo=timezone.utc), {"2611.12345"}, 1,
            )
        self.assertEqual([paper.identifier for paper in papers], ["2611.12346"])
        # Filter older entries and deduplicate different revisions.
        transport.request.side_effect = None
        transport.request.return_value = FIXTURE
        papers = source.find("cat:cs.AI", datetime(2026, 11, 25, tzinfo=timezone.utc),
                             datetime(2026, 11, 26, tzinfo=timezone.utc), set(), 5)
        self.assertEqual(len(papers), 1)

    def test_pagination_past_seen_page(self) -> None:
        """Fetch another page when every entry was already reported."""
        # Simulate two single-entry pages and verify pagination.
        source: ArxivSource = ArxivSource(Mock())
        parsed: list[Paper] = source.parse(FIXTURE)
        with patch.object(source, "parse", side_effect=[[parsed[0]], [parsed[2]]]), patch(
            "ai_foundry.projects.ai_updates.sources.papers.PAGE_SIZE", 1
        ), patch("ai_foundry.projects.ai_updates.sources.papers.time.sleep"):
            papers: list[Paper] = source.find(
                "cat:cs.AI", datetime(2026, 11, 20, tzinfo=timezone.utc),
                datetime(2026, 11, 26, tzinfo=timezone.utc), {"2611.12345"}, 1,
            )
        self.assertEqual(papers[0].identifier, "2611.12346")
        self.assertIn("start=1", source.transport.request.call_args.args[0].full_url)

    def test_history_persistence_rollback_and_overlap(self) -> None:
        """Persist completed IDs and roll back unsuccessful transactions."""
        # Initialize a fresh DAL and stage a record.
        with tempfile.TemporaryDirectory() as temporary:
            database_path: Path = Path(temporary) / "history.sqlite3"
            database: SQLiteDatabase = SQLiteDatabase(database_path)
            history: ReportHistoryStore = ReportHistoryStore(database)
            paper: Paper = ArxivSource(Mock()).parse(FIXTURE)[0]
            entry: PaperSummary = PaperSummary(paper, "Summary")
            database.begin()
            history.record([entry])
            database.rollback()
            self.assertEqual(history.reported_ids(), set())
            database.begin()
            history.record([entry, entry])
            database.commit()
            database.close()
            # Reopen and confirm persistence and lock exclusion.
            database = SQLiteDatabase(database_path)
            history = ReportHistoryStore(database)
            self.assertEqual(history.reported_ids(), {paper.identifier})
            other: SQLiteDatabase = SQLiteDatabase(database_path)
            other.connection.execute("PRAGMA busy_timeout = 0")
            database.begin()
            with self.assertRaises(sqlite3.OperationalError):
                other.begin()
            other.close()
            database.close()

    def test_workflow_retries_failed_publication_and_skips_completed(self) -> None:
        """A failed report leaves papers eligible for the next run."""
        # Use fixture papers and the zero-network model implementation.
        with tempfile.TemporaryDirectory() as temporary:
            root: Path = Path(temporary)
            config: UpdateConfig = UpdateConfig(mock=True, report_directory=root / "reports",
                                                 history_path=root / "history.sqlite3")
            source: Mock = Mock()
            paper: Paper = ArxivSource(Mock()).parse(FIXTURE)[0]
            source.find.side_effect = lambda query, cutoff, now, seen, limit: (
                [] if paper.identifier in seen else [paper]
            )
            renderer: ReportRenderer = ReportRenderer()
            workflow: UpdateWorkflow = UpdateWorkflow(source, Summarizer(MockTextClient()), renderer)
            with patch.object(renderer, "publish", side_effect=OSError("Disk full")):
                with self.assertRaises(OSError):
                    workflow.run(config)
            with patch("ai_foundry.core.sources.http.urlopen", side_effect=AssertionError("Model network call")):
                self.assertEqual(workflow.run(config), 1)
                original: str = (config.report_directory / "index.html").read_text()
                self.assertEqual(workflow.run(config), 0)
            self.assertEqual((config.report_directory / "index.html").read_text(), original)
            self.assertIn("MOCK MODE", original)

    def test_html_escaping_and_deterministic_mock(self) -> None:
        """Untrusted source and model text stay inert in HTML."""
        # Render hostile text through the production renderer.
        paper: Paper = Paper("2611.12345", "<script>alert(1)</script>", "abstract",
                             datetime.now(timezone.utc), "https://arxiv.org/abs/2611.12345")
        client: MockTextClient = MockTextClient()
        self.assertEqual(client.generate("", "source"), client.generate("", "source"))
        markdown: str
        document: str
        markdown, document = ReportRenderer().render([PaperSummary(paper, "<img src=x>")], True)
        self.assertNotIn("<script>", document)
        self.assertNotIn("<img src=x>", document)
        self.assertIn("&lt;script&gt;", document)
        self.assertIn("Based on the abstract", markdown)

    def test_retry_after_budget_and_model_response(self) -> None:
        """Retry transient HTTP failures and validate provider responses."""
        # Retry a rate limit once and honor its delay.
        response: Mock = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b"ok"
        error: HTTPError = HTTPError("https://example.com", 429, "limit", {"Retry-After": "1"}, None)
        with patch("ai_foundry.core.sources.http.urlopen", side_effect=[error, response]), patch(
            "ai_foundry.core.sources.http.time.sleep"
        ) as sleeper:
            self.assertEqual(HttpClient().request(Request("https://example.com")), b"ok")
            sleeper.assert_called_once_with(1)
        error = HTTPError("https://example.com", 429, "limit", {"Retry-After": "99"}, None)
        with patch("ai_foundry.core.sources.http.urlopen", side_effect=error):
            with self.assertRaises(OSError):
                HttpClient().request(Request("https://example.com"))
        transport: Mock = Mock()
        transport.request.return_value = b'{"choices":[{"message":{"content":"Summary"}}]}'
        self.assertEqual(OpenAITextClient("key", "model", transport).generate("instructions", "source"), "Summary")
        transport.request.return_value = b"{}"
        with self.assertRaises(ValueError):
            OpenAITextClient("key", "model", transport).generate("instructions", "source")

    def test_cli_mock_without_credentials(self) -> None:
        """Run the CLI with a minimal cron-like environment and no key."""
        # Supply a timeless fixture through the API boundary.
        with tempfile.TemporaryDirectory() as temporary:
            output: Path = Path(temporary) / "reports"
            history: Path = Path(temporary) / "history.sqlite3"
            terminal: io.StringIO = io.StringIO()
            arguments: list[str] = [
                "ai-updates", "--mock", "--lookback-days", "36500",
                "--report-directory", str(output), "--history-path", str(history),
            ]
            with patch.dict(os.environ, {}, clear=True), patch("sys.argv", arguments), patch(
                "ai_foundry.core.sources.http.HttpClient.request", return_value=FIXTURE
            ), patch("ai_foundry.projects.ai_updates.main.OpenAITextClient", side_effect=AssertionError("Live client")), contextlib.redirect_stdout(terminal):
                main()
                main()
            self.assertIn("MOCK MODE", terminal.getvalue())
            self.assertIn("0 new papers", terminal.getvalue())
            self.assertTrue((output / "index.html").exists())

    def test_invalid_feed_and_settings(self) -> None:
        """Reject malformed metadata and unsafe output layouts."""
        # Keep invalid data out of reports and history.
        with self.assertRaises(ValueError):
            ArxivSource(Mock()).parse(b"invalid XML")
        self.assertEqual(ArxivSource(Mock()).parse(b'<feed xmlns="http://www.w3.org/2005/Atom"/>'), [])
        with self.assertRaises(ValueError):
            UpdateConfig(report_directory=Path("public"), history_path=Path("public/history.db")).validate()


if __name__ == "__main__":
    unittest.main()
