"""Regression coverage for transactional history ownership."""

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from ai_foundry.projects.ai_updates.db.dal import UpdateDataAccess
from ai_foundry.projects.ai_updates.db.models import Paper, PaperSummary


class DataAccessTests(unittest.TestCase):
    """Verify persistence and cleanup at the data-access boundary."""

    def test_context_commits_and_rolls_back_history(self) -> None:
        """Retain successful entries and discard entries from failed runs."""
        # Prepare two records for successful and unsuccessful runs.
        with tempfile.TemporaryDirectory() as temporary:
            database_path: Path = Path(temporary) / "history.sqlite3"
            paper: Paper = Paper(
                "2611.12345", "Paper", "Abstract", datetime.now(timezone.utc),
                "https://arxiv.org/abs/2611.12345",
            )
            other_paper: Paper = Paper(
                "2611.12346", "Other paper", "Abstract", paper.published,
                "https://arxiv.org/abs/2611.12346",
            )
            data_access: UpdateDataAccess = UpdateDataAccess(database_path)
            with data_access:
                data_access.history.record([PaperSummary(paper, "Summary")])

            # A later failure must preserve prior commits and discard new writes.
            data_access = UpdateDataAccess(database_path)
            with self.assertRaisesRegex(ValueError, "Run failed"):
                with data_access:
                    data_access.history.record([PaperSummary(other_paper, "Summary")])
                    raise ValueError("Run failed")
            data_access = UpdateDataAccess(database_path)
            with data_access:
                self.assertEqual(data_access.history.reported_ids(), {paper.identifier})
            with self.assertRaises(sqlite3.ProgrammingError):
                data_access.history.reported_ids()

    def test_commit_failure_rolls_back_and_closes(self) -> None:
        """Closing after a failed commit leaves staged papers eligible."""
        # Stage a real write but fail the final commit.
        with tempfile.TemporaryDirectory() as temporary:
            database_path: Path = Path(temporary) / "history.sqlite3"
            data_access: UpdateDataAccess = UpdateDataAccess(database_path)
            paper: Paper = Paper(
                "2611.12345", "Paper", "Abstract", datetime.now(timezone.utc),
                "https://arxiv.org/abs/2611.12345",
            )
            with patch.object(data_access.database, "commit", side_effect=sqlite3.OperationalError("Commit failed")):
                with self.assertRaisesRegex(sqlite3.OperationalError, "Commit failed"):
                    with data_access:
                        data_access.history.record([PaperSummary(paper, "Summary")])

            # Reopening verifies both rollback and release of the write reservation.
            data_access = UpdateDataAccess(database_path)
            with data_access:
                self.assertEqual(data_access.history.reported_ids(), set())

    def test_initialization_failure_closes_connection(self) -> None:
        """Release the connection when schema initialization fails."""
        # Fail before context entry, where __exit__ cannot clean up.
        database: Mock = Mock()
        with patch(
            "ai_foundry.projects.ai_updates.db.dal.SQLiteDatabase", return_value=database
        ), patch(
            "ai_foundry.projects.ai_updates.db.dal.ReportHistoryStore",
            side_effect=sqlite3.OperationalError("Schema failed"),
        ):
            with self.assertRaisesRegex(sqlite3.OperationalError, "Schema failed"):
                UpdateDataAccess(Path("unused.sqlite3"))
        database.close.assert_called_once_with()

    def test_reservation_failure_closes_connection(self) -> None:
        """Release the connection when another run prevents context entry."""
        # Simulate a timeout while acquiring the run's write reservation.
        database: Mock = Mock()
        database.begin.side_effect = sqlite3.OperationalError("Database locked")
        with patch(
            "ai_foundry.projects.ai_updates.db.dal.SQLiteDatabase", return_value=database
        ):
            data_access: UpdateDataAccess = UpdateDataAccess(Path("unused.sqlite3"))
            with self.assertRaisesRegex(sqlite3.OperationalError, "Database locked"):
                with data_access:
                    self.fail("A failed reservation must prevent workflow execution")
        database.close.assert_called_once_with()
