"""Build a unified plan between paper discovery and downloading."""

from __future__ import annotations

from typing import Literal, TypedDict

from .paper_schema import PaperRecord, normalize_paper_record

DownloadStrategy = Literal["pmc", "arxiv", "direct_pdf"]
PlanStatus = Literal["ready", "skipped"]
SkipReason = Literal["", "no_download_route", "duplicate"]


class DownloadPlanEntry(TypedDict):
    """One planned download entry."""

    index: int
    status: PlanStatus
    strategy: str
    identifier: str
    identifier_type: str
    download_url: str
    skip_reason: SkipReason
    duplicate_of: int | None
    dedupe_key: str
    merged_sources: list[str]
    source: str
    paper: PaperRecord


class DownloadPlan(TypedDict):
    """A normalized download plan produced from any supported input."""

    schema: str
    source: str
    total: int
    ready: int
    skipped: int
    entries: list[DownloadPlanEntry]


def choose_download_strategy(paper: PaperRecord) -> DownloadStrategy | None:
    """Return the preferred download strategy for a normalized paper record."""
    if paper["pmcid"]:
        return "pmc"
    if paper["arxiv_id"]:
        return "arxiv"
    if paper["pdf_url"]:
        return "direct_pdf"
    return None


def build_dedupe_key(paper: PaperRecord) -> str:
    """Return a stable key for duplicate detection."""
    if paper["pmcid"]:
        return f"pmcid:{paper['pmcid'].lower()}"
    if paper["doi"]:
        return f"doi:{paper['doi'].lower()}"
    if paper["arxiv_id"]:
        return f"arxiv:{paper['arxiv_id'].lower()}"
    if paper["pmid"]:
        return f"pmid:{paper['pmid'].lower()}"
    title = " ".join(paper["title"].lower().split())
    return f"title:{title}" if title else ""


def _source_label(paper: PaperRecord, fallback: str) -> str:
    return paper["source"] or paper["raw_source"] or fallback


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def build_download_plan(
    papers: list[dict], *, source: str = "unknown"
) -> DownloadPlan:
    """Build a download plan from normalized or raw paper dictionaries."""
    entries: list[DownloadPlanEntry] = []
    seen_ready: dict[str, int] = {}
    for index, paper in enumerate(papers):
        normalized = normalize_paper_record(paper, str(paper.get("source") or source))
        strategy = choose_download_strategy(normalized)
        dedupe_key = build_dedupe_key(normalized)
        duplicate_of = seen_ready.get(dedupe_key) if dedupe_key else None
        status: PlanStatus = "ready" if strategy and duplicate_of is None else "skipped"
        skip_reason: SkipReason = ""
        if not strategy:
            skip_reason = "no_download_route"
        elif duplicate_of is not None:
            skip_reason = "duplicate"

        merged_sources = [_source_label(normalized, source)] if status == "ready" else []
        entries.append(
            {
                "index": index,
                "status": status,
                "strategy": strategy or "",
                "identifier": normalized["identifier"],
                "identifier_type": normalized["identifier_type"],
                "download_url": normalized["download_url"],
                "skip_reason": skip_reason,
                "duplicate_of": duplicate_of,
                "dedupe_key": dedupe_key,
                "merged_sources": merged_sources,
                "source": source,
                "paper": normalized,
            }
        )

        if status == "ready" and dedupe_key:
            seen_ready[dedupe_key] = index
        elif duplicate_of is not None:
            _append_unique(
                entries[duplicate_of]["merged_sources"],
                _source_label(normalized, source),
            )

    ready_count = sum(1 for entry in entries if entry["status"] == "ready")
    return {
        "schema": "download_plan.v1",
        "source": source,
        "total": len(entries),
        "ready": ready_count,
        "skipped": len(entries) - ready_count,
        "entries": entries,
    }


def ready_papers(plan: DownloadPlan) -> list[PaperRecord]:
    """Return papers that should be passed to the download manager."""
    return [
        entry["paper"]
        for entry in plan["entries"]
        if entry["status"] == "ready"
    ]
