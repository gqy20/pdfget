# PDFGet Test Suite

This directory contains the regression tests for PDFGet's search, identifier
planning, download, reporting, logging, and CLI workflows.

## Test Layout

- `test_main_arxiv.py`: CLI workflow behavior, JSON output, dry-run, resume, and arXiv paths
- `test_download_plan.py`: normalized download plan generation, deduplication, and identifier resolution
- `test_csv_and_identifiers.py`: CSV parsing, mixed identifier input, and unified input downloads
- `test_doi_integration.py`: DOI to PMCID conversion and download-service integration
- `test_manager.py`: concurrent download manager ordering, worker reuse, and error handling
- `test_downloader.py`: single-paper PDF download behavior
- `test_searcher.py`: PubMed, Europe PMC, arXiv, and combined search behavior
- `test_counter.py`: PMCID statistics and credential propagation
- `test_config_paths.py`: cache/export behavior and public API migration boundaries

## Run Tests

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src/pdfget
```

The suite uses mocks for network-sensitive paths and should not require live
external API calls.
