"""Download run summary helpers."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from .paper_schema import PaperRecord, build_identifier, normalize_paper_record
from .schemas import DownloadResult, RunSummary, RunSummaryEntry

RUN_SUMMARY_SCHEMA: Literal["run_summary.v2"] = "run_summary.v2"
RETRYABLE_STAGES = {"download_pdf", "save_file", "worker_error"}
NON_RETRYABLE_STAGES = {"resolve_identifier", "validate_response", "cache_hit"}


def _result_paper(result: DownloadResult) -> PaperRecord:
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
    papers: list[dict[str, Any]] | None, result: DownloadResult, index: int
) -> dict[str, Any] | PaperRecord:
    if papers is not None and index < len(papers):
        return papers[index]
    return _result_paper(result)


def _build_download_entry(
    *,
    index: int,
    paper: dict[str, Any] | PaperRecord,
    result: DownloadResult,
) -> RunSummaryEntry:
    identifier, identifier_type = build_identifier({**paper, **result})
    success = bool(result.get("success"))
    retryable, retry_reason = classify_retryability(result, paper)
    return {
        "index": index,
        "status": "success" if success else "failed",
        "stage": result.get("stage") or "",
        "identifier": identifier,
        "identifier_type": identifier_type,
        "paper": paper,
        "result": result,
        "path": result.get("path") or "",
        "error": result.get("error") or "",
        "retryable": retryable,
        "retry_reason": retry_reason,
    }


def _build_skipped_entry(plan_entry: Mapping[str, Any]) -> RunSummaryEntry:
    paper = plan_entry.get("paper") or {}
    skip_reason = str(plan_entry.get("skip_reason") or "skipped")
    identifier = str(plan_entry.get("identifier") or "")
    identifier_type = str(plan_entry.get("identifier_type") or "")
    if not identifier:
        identifier, identifier_type = build_identifier(paper)

    result: DownloadResult = {
        "success": False,
        "stage": "plan_skip",
        "source": "download_plan",
        "error": skip_reason,
        "attempts": [
            {
                "source": "download_plan",
                "success": False,
                "stage": "plan_skip",
                "error": skip_reason,
            }
        ],
    }
    return {
        "index": int(plan_entry.get("index") or 0),
        "status": "skipped",
        "stage": "plan_skip",
        "identifier": identifier,
        "identifier_type": identifier_type,
        "paper": paper,
        "result": result,
        "path": "",
        "error": skip_reason,
        "retryable": False,
        "retry_reason": skip_reason,
    }


def _missing_download_result(plan_entry: Mapping[str, Any]) -> DownloadResult:
    paper = plan_entry.get("paper") or {}
    paper_mapping = paper if isinstance(paper, Mapping) else {}
    return {
        "success": False,
        "stage": "missing_download_result",
        "source": "run_summary",
        "error": "Missing download result for ready plan entry",
        "pmcid": str(paper_mapping.get("pmcid") or ""),
        "doi": str(paper_mapping.get("doi") or ""),
        "arxiv_id": str(paper_mapping.get("arxiv_id") or ""),
        "attempts": [
            {
                "source": "run_summary",
                "success": False,
                "stage": "missing_download_result",
                "error": "Missing download result for ready plan entry",
            }
        ],
    }


def classify_retryability(
    result: DownloadResult,
    paper: dict[str, Any] | PaperRecord,
) -> tuple[bool, str]:
    """Return whether a failed result should be retried by default."""
    if result.get("success"):
        return False, ""

    normalized = normalize_paper_record(paper, str(paper.get("source") or "resume"))
    if not normalized["is_downloadable"]:
        return False, "not_downloadable"

    stage = str(result.get("stage") or "")
    error = str(result.get("error") or "").lower()
    if stage in NON_RETRYABLE_STAGES:
        return False, stage
    if "no downloadable identifier" in error or "no identifier" in error:
        return False, "missing_identifier"
    if "不是 pdf 文件" in error or "not pdf" in error:
        return False, "not_pdf"
    if stage in RETRYABLE_STAGES:
        return True, stage
    if "timeout" in error or "超时" in error:
        return True, "timeout"
    if "failed" in error or "失败" in error:
        return True, "download_failed"
    return False, "unknown_failure"


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


def build_run_stats(entries: list[RunSummaryEntry]) -> dict[str, Any]:
    """Build aggregate statistics for machine-readable run reports."""
    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    by_retry_reason: dict[str, int] = {}
    by_skip_reason: dict[str, int] = {}
    by_source: dict[str, int] = {}
    attempts_by_source: dict[str, dict[str, int]] = {}

    for entry in entries:
        _increment(by_status, entry["status"])
        if entry["stage"]:
            _increment(by_stage, entry["stage"])
        if entry["retry_reason"]:
            _increment(by_retry_reason, entry["retry_reason"])
        if entry["status"] == "skipped" and entry["error"]:
            _increment(by_skip_reason, entry["error"])

        result = entry["result"]
        source = str(result.get("source") or "")
        if source:
            _increment(by_source, source)

        for attempt in result.get("attempts", []):
            attempt_source = str(attempt.get("source") or "unknown")
            bucket = attempts_by_source.setdefault(
                attempt_source, {"total": 0, "success": 0, "failed": 0}
            )
            bucket["total"] += 1
            if attempt.get("success"):
                bucket["success"] += 1
            else:
                bucket["failed"] += 1

    return {
        "by_status": by_status,
        "by_stage": by_stage,
        "by_retry_reason": by_retry_reason,
        "by_skip_reason": by_skip_reason,
        "by_source": by_source,
        "attempts_by_source": attempts_by_source,
    }


def build_run_summary(
    results: list[DownloadResult],
    *,
    papers: list[dict[str, Any]] | None = None,
    plan_entries: Sequence[Mapping[str, Any]] | None = None,
    source: str,
    output_dir: str,
    input_value: str | None = None,
    previous_report: str | None = None,
    download_plan_path: str | None = None,
) -> RunSummary:
    """Build a retryable summary for one download run."""
    entries: list[RunSummaryEntry] = []
    if plan_entries is None:
        for index, result in enumerate(results):
            paper = _entry_paper(papers, result, index)
            entries.append(
                _build_download_entry(index=index, paper=paper, result=result)
            )
    else:
        download_index = 0
        for plan_entry in plan_entries:
            if plan_entry.get("status") == "skipped":
                entries.append(_build_skipped_entry(plan_entry))
                continue

            result_index = download_index
            if result_index >= len(results):
                result = _missing_download_result(plan_entry)
            else:
                result = results[result_index]
                download_index += 1
            paper = plan_entry.get("paper") or _entry_paper(
                papers, result, result_index
            )
            entries.append(
                _build_download_entry(
                    index=int(plan_entry.get("index") or download_index),
                    paper=paper,
                    result=result,
                )
            )

    failed_count = sum(1 for entry in entries if entry["status"] == "failed")
    skipped_count = sum(1 for entry in entries if entry["status"] == "skipped")
    payload: RunSummary = {
        "schema": RUN_SUMMARY_SCHEMA,
        "timestamp": time.time(),
        "source": source,
        "output_dir": output_dir,
        "total": len(entries),
        "success": sum(1 for entry in entries if entry["status"] == "success"),
        "failed": failed_count,
        "skipped": skipped_count,
        "stats": build_run_stats(entries),
        "results": entries,
    }
    if input_value is not None:
        payload["input_value"] = input_value
    if previous_report is not None:
        payload["previous_report"] = previous_report
    if download_plan_path is not None:
        payload["download_plan_path"] = download_plan_path
    return payload


def save_run_summary(output_dir: str, summary: RunSummary) -> Path:
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
        retryable = entry.get("retryable")
        if not retryable:
            continue
        normalized = normalize_paper_record(paper, str(paper.get("source") or "resume"))
        if normalized["is_downloadable"]:
            papers.append(normalized)

    return papers
