# Getting started

Use Python 3.12 and install uv. From the repository root, sync the locked environment.
uv downloads Python 3.12 when needed and installs the project in its local environment.

```sh
uv sync --locked
uv run --locked ai-updates --mock --query 'cat:cs.AI' --limit 2
```

Mock mode fetches live arXiv metadata and generates deterministic, visibly marked
placeholder summaries. It makes zero model API calls and requires no API key.
Defaults are `reports/ai-updates-mock/` and `data/ai-updates-mock.sqlite3`.
Live mode defaults to `reports/ai-updates/` and `data/ai-updates.sqlite3`.
A second run skips previously reported unversioned arXiv IDs. Revisions count as
the same paper. History is shared across queries that use the same database.
Pass a separate history path to maintain an independent stream.

For real summaries, set `OPENAI_API_KEY` in your environment and run
`uv run --locked ai-updates --query 'cat:cs.AI' --limit 2`. The default model is
`gpt-4.1-mini`, configurable through `--model` or `OPENAI_MODEL`.
Only titles and abstracts are sent to OpenAI. Check summaries against the
abstract before relying on their claims. The live model incurs API costs.

Use `--lookback-days 7` to set the UTC first-submission window, and
`--report-directory` and `--history-path` to change output locations.
Keep the history file outside the public report directory. Empty runs preserve
existing reports. Errors return a nonzero exit status. HTTP retries are bounded
to three attempts with at most 30 seconds of delay per retry. Overlapping runs
using the same database wait up to five seconds for its write reservation.

View the mock HTML report over local HTTP.

```sh
uv run --locked python -m http.server 8000 --bind 127.0.0.1 --directory reports/ai-updates-mock
```

Open http://127.0.0.1:8000/. The directory also contains `research.md`.

For cron, use absolute paths, a fixed working directory, and the same history
and output paths as manual runs. For example, adapt the paths below to your
installation. Provision credentials in the cron environment for live mode.

```cron
0 9 * * * cd /absolute/path/ai-foundry && /absolute/path/to/uv run --locked ai-updates --mock --query 'cat:cs.AI' --report-directory /absolute/path/ai-foundry/reports/ai-updates-mock --history-path /absolute/path/ai-foundry/data/ai-updates-mock.sqlite3 >> /absolute/path/ai-updates.log 2>&1
```

Run offline verification with `uv run --locked python -m unittest discover -s tests -v`.
