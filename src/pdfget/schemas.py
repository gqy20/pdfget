"""Typed schemas for structured payloads."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from .paper_schema import PaperRecord


class SearchPayload(TypedDict):
    """Schema-first search output payload."""

    schema: Literal["paper_record.v1"]
    query: str
    timestamp: float
    total: int
    results: list[dict[str, Any]]


class DownloadResult(TypedDict, total=False):
    """Single download result produced by PDF downloaders."""

    doi: str
    pmcid: str
    arxiv_id: str
    pdf_url: str
    source_url: str
    title: str
    source: str
    success: bool
    path: str
    full_text_url: str
    error: str
    stage: str


class DownloadPayload(TypedDict):
    """Schema-first download result payload."""

    schema: Literal["download_result.v1"]
    timestamp: float
    source: str
    total: int
    success: int
    results: list[DownloadResult]
    input_value: NotRequired[str]


class RunSummaryEntry(TypedDict):
    """One retryable run summary entry."""

    index: int
    status: Literal["success", "failed"]
    stage: str
    identifier: str
    identifier_type: str
    paper: dict[str, Any] | PaperRecord
    result: DownloadResult
    path: str
    error: str


class RunSummary(TypedDict):
    """Retryable download run summary payload."""

    schema: Literal["run_summary.v1"]
    timestamp: float
    source: str
    output_dir: str
    total: int
    success: int
    failed: int
    results: list[RunSummaryEntry]
    input_value: NotRequired[str]
    previous_report: NotRequired[str]
    download_plan_path: NotRequired[str]


class PmcidStats(TypedDict):
    """PMCID counting statistics payload."""

    query: str
    total: int
    checked: int
    with_pmcid: int
    without_pmcid: int
    rate: float
    elapsed_seconds: float
    estimated_size_mb: float
    processing_speed: NotRequired[float]
    from_cache: NotRequired[bool]
