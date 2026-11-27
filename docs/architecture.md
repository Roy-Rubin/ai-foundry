# Architecture

The research update workflow composes paper discovery, summarization, report
publication, and history tracking.

Database code lives in dedicated `db` packages:

- `core/db/sqlite.py`: shared `SQLiteDatabase` connection and transaction
  primitives.
- `projects/ai_updates/db/models.py`: the `Paper` and `PaperSummary`
  records shared by sources, agents, reports, and history storage.
- `projects/ai_updates/db/history.py`: `ReportHistoryStore`, which owns
  the reported-paper schema and SQL queries.
- `projects/ai_updates/db/dal.py`: `UpdateDataAccess`, which composes the
  connection and history store and manages each run's transaction and cleanup.

The workflow opens `UpdateDataAccess` as a context manager before selecting
unseen papers. It publishes reports before recording their history. Successful
runs commit; failures roll back and leave papers eligible for retry. A write
reservation serializes concurrent runs. Existing SQLite history files remain
compatible with this layout; no migration is required.
