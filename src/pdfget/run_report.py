"""Download run summary helpers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .paper_schema import PaperRecord, build_identifier, normalize_paper_record

RUN_SUMMARY_SCHEMA = "run_summary.v1"


def _result_paper(result: dict[str, Any]) -> PaperRecord:
    """Build a retryable paper record from a download result."""
    return normalize_paper_record(
        {
            "pmcid": result.get("pmcid") or "",
            "doi": result.get("doi") or "",
            "arxiv_id": result.get("arxiv_id") or "",
            "pdf_url": result.get("pdf_url") or result.get("source_url") or "",
            "title": result.get("title") or "",
            "source": result.get("source") or "download_result",
        },
        str(result.get("source") or "download_result"),
    )


def _entry_paper(
    papers: list[dict[str, Any]] | None, result: dict[str, Any], index: int
) -> dict[str, Any] | PaperRecord:
    if papers is not None and index < len(papers):
        return papers[index]
    return _result_paper(result)


def build_run_summary(
    results: list[dict[str, Any]],
    *,
    papers: list[dict[str, Any]] | None = None,
    source: str,
    output_dir: str,
    input_value: str | None = None,
    previous_report: str | None = None,
) -> dict[str, Any]:
    """Build a retryable summary for one download run."""
    entries: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        paper = _entry_paper(papers, result, index)
        identifier, identifier_type = build_identifier({**paper, **result})
        success = bool(result.get("success"))
        entries.append(
            {
                "index": index,
                "status": "success" if success else "failed",
                "identifier": identifier,
                "identifier_type": identifier_type,
                "paper": paper,
                "result": result,
                "path": result.get("path") or "",
                "error": result.get("error") or "",
            }
        )

    failed_count = sum(1 for entry in entries if entry["status"] == "failed")
    payload: dict[str, Any] = {
        "schema": RUN_SUMMARY_SCHEMA,
        "timestamp": time.time(),
        "source": source,
        "output_dir": output_dir,
        "total": len(entries),
        "success": len(entries) - failed_count,
        "failed": failed_count,
        "results": entries,
    }
    if input_value is not None:
        payload["input_value"] = input_value
    if previous_report is not None:
        payload["previous_report"] = previous_report
    return payload


def save_run_summary(output_dir: str, summary: dict[str, Any]) -> Path:
    """Save the latest run summary and a timestamped copy."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    latest_path = output_path / "run_summary.json"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archived_path = output_path / f"run_summary_{timestamp}.json"

    for path in (latest_path, archived_path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(summary, file, indent=2, ensure_ascii=False)

    return latest_path


def load_failed_papers(report_path: str | Path) -> list[PaperRecord]:
    """Load retryable paper records from failed report entries."""
    path = Path(report_path)
    with open(path, encoding="utf-8") as file:
        payload = json.load(file)

    if payload.get("schema") != RUN_SUMMARY_SCHEMA:
        raise ValueError(f"不支持的运行报告 schema: {payload.get('schema')}")

    papers: list[PaperRecord] = []
    for entry in payload.get("results", []):
        if entry.get("status") != "failed":
            continue
        paper = entry.get("paper") or _result_paper(entry.get("result") or {})
        normalized = normalize_paper_record(paper, str(paper.get("source") or "resume"))
        if normalized["is_downloadable"]:
            papers.append(normalized)

    return papers
