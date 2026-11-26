# AI research update plan

Build one command that finds recent arXiv papers, summarizes their abstracts, and saves a Markdown report and a browser-friendly HTML view. Use the same command and history for manual runs and cron.

## Shared core

- `core/sources/http.py` handles HTTP requests with a timeout and bounded retries for transient failures. Respect `Retry-After` within the retry budget and surface an actionable error if the source remains unavailable.
- `core/llm/` defines a small text-generation interface and an OpenAI API adapter. Default to `gpt-4.1-mini`, make the model ID configurable, and read `OPENAI_API_KEY` from the environment. Use a fake client for offline verification.

## AI updates project

1. Define paper and summary records in `models.py`. In `config.py`, set a seven-day default lookback and configure the arXiv query, result limit, report directory, and SQLite history path.
2. In `sources/papers.py`, query the arXiv API for papers first submitted within the lookback window, using a UTC cutoff and newest submissions first. Parse the Atom feed for titles, abstracts, first submission dates, canonical links, and IDs. Page through matches as needed to fill the report limit with unseen papers. Treat revisions as the same paper by using the unversioned arXiv ID.
3. Keep a local SQLite history shared by manual and scheduled runs. Skip duplicate and previously reported IDs before applying the report limit. Serialize runs that share a history to prevent duplicate reports from overlapping runs. Record IDs only after both reports are saved successfully, so a failed run can retry those papers.
4. In `agents/summarizer.py` and `prompts/summary.txt`, send only each paper's title and abstract as source material. Get both from the Atom feed and skip PDF retrieval. Ask for two or three sentences on the contribution and any findings stated in the abstract. Label each summary as abstract-based.
5. Wire retrieval, history, summarization, and report generation together in `workflows/generate_update.py`. Render Markdown and a static `index.html` from the same results. The HTML view shows one card per paper with its title, date, summary, and arXiv link. Keep it to one renderer and inline CSS, with no JavaScript or web framework. Escape paper and model text before rendering HTML.
6. Expose the workflow in `main.py` with query, `--lookback-days`, limit, report directory, and history path options. Print the number of new papers and the report paths. If there are no unseen matches, print that outcome and preserve any existing reports. Return a nonzero exit status for retrieval, summarization, or write failures. Write each report to a temporary file before replacing its destination.
7. Document a one-off command and a cron example using the same executable, report directory, and history path. For the browser view, serve only the report directory using `python -m http.server 8000 --bind 127.0.0.1 --directory <report-directory>` and open `http://127.0.0.1:8000/`. Keep the history database outside the served directory.

## Acceptance checks

- Use a saved Atom response and fake LLM to verify the UTC cutoff, duplicate and revision handling, pagination past seen papers, empty results, rate limiting, and retry after a failed report. Run twice with the same history and check that the second run skips the first run's papers.
- Query the live arXiv API with a narrow query and a limit of two. Confirm that at least one result has a title, abstract, date, and working arXiv link. If rate-limited, retry within the configured budget.
- Summarize one retrieved paper with the configured model. Check that Markdown and the HTML page served over local HTTP show the same paper and that the summary is supported by its abstract.
- Verify that the documented command works in a cron-like environment after the one-off run passes.
