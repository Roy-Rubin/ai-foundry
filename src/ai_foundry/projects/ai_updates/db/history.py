"""SQL access to successfully reported papers."""

from datetime import datetime, timezone

from ai_foundry.core.db.sqlite import SQLiteDatabase
from .models import PaperSummary


class ReportHistoryStore:
    """Recall reported IDs and record completed reports."""

    def __init__(self, database: SQLiteDatabase) -> None:
        """Initialize history schema.

        Args:
            database: Connection owner.

        Raises:
            sqlite3.Error: If schema initialization fails.
        """
        # Initialize schema before reserving the run transaction.
        self.database: SQLiteDatabase = database
        self.database.connection.execute(
            "CREATE TABLE IF NOT EXISTS reported_papers ("
            "arxiv_id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, "
            "reported_at TEXT NOT NULL)"
        )
        self.database.connection.commit()

    def reported_ids(self) -> set[str]:
        """Recall all successfully reported paper IDs.

        Returns:
            Previously reported unversioned IDs.

        Raises:
            sqlite3.Error: If reading history fails.
        """
        # Convert storage rows to the domain representation.
        identifiers: set[str] = {
            row[0] for row in self.database.connection.execute("SELECT arxiv_id FROM reported_papers")
        }
        return identifiers

    def record(self, summaries: list[PaperSummary]) -> None:
        """Stage completed summaries in the current transaction.

        Args:
            summaries: Successfully published report entries.

        Raises:
            sqlite3.Error: If writing history fails.
        """
        # Use parameterized SQL and tolerate duplicate IDs.
        reported_at: str = datetime.now(timezone.utc).isoformat()
        self.database.connection.executemany(
            "INSERT OR IGNORE INTO reported_papers (arxiv_id, title, summary, reported_at) "
            "VALUES (?, ?, ?, ?)",
            [(entry.paper.identifier, entry.paper.title, entry.summary, reported_at) for entry in summaries],
        )
