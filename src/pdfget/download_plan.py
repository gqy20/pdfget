"""Build a unified plan between paper discovery and downloading."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, TypedDict

from .paper_schema import PaperRecord, normalize_paper_record
from .protocols import IdentifierResolver

DownloadStrategy = Literal["pmc", "arxiv", "direct_pdf"]
PlanStatus = Literal["ready", "skipped"]
SkipReason = Literal[
    "",
    "no_download_route",
    "duplicate",
    "unresolved_identifier",
    "missing_identifier",
]


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
    resolved_by: str
    resolved_from: str
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


def _resolve_download_record(
    paper: PaperRecord,
    *,
    pmid_to_pmcid: Mapping[str, str],
    doi_to_pmcid: Mapping[str, str],
) -> tuple[PaperRecord, str, str]:
    """Add resolved download identifiers to a paper record when possible."""
    if paper["pmcid"] or paper["arxiv_id"] or paper["pdf_url"]:
        return paper, "", ""

    if paper["pmid"] and paper["pmid"] in pmid_to_pmcid:
        return (
            normalize_paper_record({**paper, "pmcid": pmid_to_pmcid[paper["pmid"]]}),
            "pmid_to_pmcid",
            paper["pmid"],
        )

    if paper["doi"] and paper["doi"] in doi_to_pmcid:
        return (
            normalize_paper_record({**paper, "pmcid": doi_to_pmcid[paper["doi"]]}),
            "doi_to_pmcid",
            paper["doi"],
        )

    return paper, "", ""


def build_download_plan(
    papers: list[dict],
    *,
    source: str = "unknown",
    resolver: IdentifierResolver | None = None,
) -> DownloadPlan:
    """Build a download plan from normalized or raw paper dictionaries."""
    normalized_papers = [
        normalize_paper_record(paper, str(paper.get("source") or source))
        for paper in papers
    ]
    pmids_to_resolve = [
        paper["pmid"]
        for paper in normalized_papers
        if paper["pmid"] and not choose_download_strategy(paper)
    ]
    dois_to_resolve = [
        paper["doi"]
        for paper in normalized_papers
        if paper["doi"] and not choose_download_strategy(paper)
    ]
    pmid_to_pmcid = resolver.resolve_pmids(pmids_to_resolve) if resolver else {}
    doi_to_pmcid = resolver.resolve_dois(dois_to_resolve) if resolver else {}

    entries: list[DownloadPlanEntry] = []
    seen_ready: dict[str, int] = {}
    for index, normalized_paper in enumerate(normalized_papers):
        normalized, resolved_by, resolved_from = _resolve_download_record(
            normalized_paper,
            pmid_to_pmcid=pmid_to_pmcid,
            doi_to_pmcid=doi_to_pmcid,
        )
        strategy = choose_download_strategy(normalized)
        dedupe_key = build_dedupe_key(normalized)
        duplicate_of = seen_ready.get(dedupe_key) if dedupe_key else None
        status: PlanStatus = "ready" if strategy and duplicate_of is None else "skipped"
        skip_reason: SkipReason = ""
        if not strategy:
            if not dedupe_key:
                skip_reason = "missing_identifier"
            elif normalized["pmid"] or normalized["doi"]:
                skip_reason = "unresolved_identifier"
            else:
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
                "resolved_by": resolved_by,
                "resolved_from": resolved_from,
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


def save_download_plan(output_dir: str, plan: DownloadPlan) -> Path:
    """Save the latest download plan and a timestamped copy."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    latest_path = output_path / "download_plan.json"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archived_path = output_path / f"download_plan_{timestamp}.json"

    for path in (latest_path, archived_path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(plan, file, indent=2, ensure_ascii=False)

    return latest_path
