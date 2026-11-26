# AI research update plan

Build one command that finds recent papers online, writes short summaries, and produces a Markdown report with source links. Start with arXiv and summarize from abstracts. Make the command usable both on demand and from cron.

## Shared core

- `core/sources/http.py` handles HTTP requests with a timeout and bounded retries for transient failures. Respect `Retry-After` when present and within the retry budget. Surface an actionable error if a source remains unavailable.
- `core/llm/` defines a small text-generation interface and one provider adapter. Use a fake client for offline verification. Keep model selection and credentials in configuration and read secrets from the environment.
- Add shared agent or storage abstractions when a use case requires them. The first workflow can call its source, summarizer, and renderer directly.

## AI updates project

1. Define paper and summary records in `models.py` and configure the arXiv query, result limit, and output path in `config.py`.
2. Implement `sources/papers.py` to query arXiv for recent matches, parse the Atom feed, and extract titles, publication dates, abstracts, and canonical links. Deduplicate by arXiv ID.
3. Implement `agents/summarizer.py` and `prompts/summary.txt` to produce two or three sentences per paper. Ask the model to explain the contribution and any findings stated in the abstract. Label each summary as abstract-based and keep bibliographic details from the source record.
4. Wire retrieval, summarization, and Markdown rendering together in `workflows/generate_update.py`. Each entry should show the title, publication date, source link, and summary. A successful search with zero matches should say so explicitly.
5. Expose the workflow through `main.py` with query, result limit, and output path options. Default to standard output and support writing to a file. Return a nonzero exit status when retrieval or summarization fails. When writing a file, replace it only after the report is complete.
6. Document a one-off run and a cron example that invokes the same command. The cron example should specify the Python executable, working directory, environment, output path, and log destination. Choose the query and schedule before installing a recurring job.

## Acceptance checks

- Run the whole workflow with a saved Atom response and fake LLM, then check the report links and summaries. Exercise duplicate entries, an empty feed, a rate-limit response, and an LLM failure.
- Run once with a narrow arXiv query and the configured LLM. Check that the report opens as Markdown and that each summary is supported by its linked abstract.
- Run the documented command in a cron-like environment and verify that it writes the expected report and returns the correct exit status.
