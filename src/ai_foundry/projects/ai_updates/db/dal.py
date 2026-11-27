"""Transactional data-access boundary for research update runs."""

import sqlite3
from pathlib import Path
from types import TracebackType

from ai_foundry.core.db.sqlite import SQLiteDatabase
from .history import ReportHistoryStore


class UpdateDataAccess:
    """Own report history access and one serialized run transaction.

    Use as a context manager to commit a successful run, roll back a failed
    run, and close the database in either case.
    """

    def __init__(self, path: Path) -> None:
        """Open history storage and initialize its schema.

        Args:
            path: Local SQLite history file.

        Raises:
            OSError: If creating the database directory fails.
            sqlite3.Error: If opening or initializing history fails.
        """
        # Compose database ownership with the project-specific SQL store.
        self.database: SQLiteDatabase = SQLiteDatabase(path)
        try:
            self.history: ReportHistoryStore = ReportHistoryStore(self.database)
        except sqlite3.Error:
            # Release the connection if schema initialization cannot finish.
            self.database.close()
            raise

    def __enter__(self) -> "UpdateDataAccess":
        """Reserve history for paper selection and report publication.

        Returns:
            Data access with an active write transaction.

        Raises:
            sqlite3.Error: If acquiring the write reservation fails.
        """
        # Context entry failures must release resources without __exit__.
        try:
            self.database.begin()
        except sqlite3.Error:
            self.database.close()
            raise
        data_access: UpdateDataAccess = self
        return data_access

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finalize history and release the connection.

        Args:
            exception_type: Failure type, or None for a successful run.
            exception: Failure instance supplied by the context manager.
            traceback: Traceback supplied by the context manager.

        Raises:
            sqlite3.Error: If finalizing or closing the database fails.
        """
        # Persist only runs that completed report publication and history writes.
        try:
            if exception_type is None:
                self.database.commit()
            else:
                self.database.rollback()
        finally:
            # Closing also rolls back if committing failed.
            self.database.close()
