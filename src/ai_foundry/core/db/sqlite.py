"""SQLite data access and transaction lifecycle."""

import sqlite3
from pathlib import Path


class SQLiteDatabase:
    """Own one SQLite connection and its transaction lifecycle."""

    def __init__(self, path: Path) -> None:
        """Open a database, creating its parent directory.

        Args:
            path: Local database file.

        Raises:
            OSError: If directory creation fails.
            sqlite3.Error: If opening the database fails.
        """
        # Create the database outside the public report directory.
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: sqlite3.Connection = sqlite3.connect(path, timeout=5)

    def begin(self) -> None:
        """Acquire a write reservation to serialize runs.

        Raises:
            sqlite3.Error: If another run holds the database past the timeout.
        """
        # Hold the reservation across selection and report publication.
        self.connection.execute("BEGIN IMMEDIATE")

    def commit(self) -> None:
        """Persist the active transaction."""
        # Commit history only after report publication.
        self.connection.commit()

    def rollback(self) -> None:
        """Discard the active transaction."""
        # Leave papers eligible for a later retry.
        self.connection.rollback()

    def close(self) -> None:
        """Release the connection and its locks."""
        # SQLite rolls back any outstanding transaction.
        self.connection.close()
