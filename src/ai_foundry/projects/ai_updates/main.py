"""One-off and cron-compatible research update command."""

import argparse
import os
import sqlite3
from pathlib import Path

from ai_foundry.core.llm.client import MockTextClient, OpenAITextClient, TextClient
from ai_foundry.core.sources.http import HttpClient
from .agents.summarizer import Summarizer
from .config import UpdateConfig
from .reports.markdown import ReportRenderer
from .sources.papers import ArxivSource
from .workflows.generate_update import UpdateWorkflow


def main() -> None:
    """Parse settings and run a research update.

    Raises:
        SystemExit: For invalid arguments or a failed run.
    """
    # Select paths and the model implementation before any network work.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Summarize recent unseen arXiv abstracts")
    parser.add_argument("--query", default=UpdateConfig.query)
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--mock", action="store_true", help="Zero model calls; live arXiv retrieval still runs")
    parser.add_argument("--report-directory", type=Path)
    parser.add_argument("--history-path", type=Path)
    arguments: argparse.Namespace = parser.parse_args()
    suffix: str = "-mock" if arguments.mock else ""
    config: UpdateConfig = UpdateConfig(
        query=arguments.query, lookback_days=arguments.lookback_days, limit=arguments.limit,
        model=arguments.model, mock=arguments.mock,
        report_directory=arguments.report_directory or Path(f"reports/ai-updates{suffix}"),
        history_path=arguments.history_path or Path(f"data/ai-updates{suffix}.sqlite3"),
    )
    try:
        config.validate()
        transport: HttpClient = HttpClient()
        client: TextClient
        if config.mock:
            client = MockTextClient()
        else:
            api_key: str = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("Set OPENAI_API_KEY or use --mock")
            client = OpenAITextClient(api_key, config.model, transport)
        workflow: UpdateWorkflow = UpdateWorkflow(ArxivSource(transport), Summarizer(client), ReportRenderer())
        count: int = workflow.run(config)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Research update failed: {error}\n")
    # Report the outcome without replacing previous reports on an empty run.
    mode: str = "MOCK MODE — " if config.mock else ""
    print(f"{mode}{count} new papers reported.")
    if count:
        print(f"Markdown: {config.report_directory / 'research.md'}")
        print(f"HTML: {config.report_directory / 'index.html'}")


if __name__ == "__main__":
    main()
