"""Utilities for normalizing paper records across data sources."""

from __future__ import annotations

import re
from typing import Any, TypedDict


class PaperRecord(TypedDict):
    """Normalized paper record shape used across the project."""

    source: str
    raw_source: str
    raw_id: str
    title: str
    authors: list[str]
    year: str
    published_at: str
    abstract: str
    journal: str
    repository: str
    pmid: str
    pmcid: str
    doi: str
    arxiv_id: str
    pdf_url: str
    download_url: str
    download_type: str
    identifier: str
    identifier_type: str
    is_downloadable: bool
    matched_by: str
    inPMC: str


def _normalize_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(author).strip() for author in value if str(author).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_year(value: Any) -> str:
    if value is None:
        return ""
    match = re.search(r"\d{4}", str(value))
    return match.group() if match else ""


def build_identifier(record: dict[str, Any]) -> tuple[str, str]:
    """Return the preferred identifier and its type."""
    if record.get("pmcid"):
        return str(record["pmcid"]), "pmcid"
    if record.get("doi"):
        return str(record["doi"]), "doi"
    if record.get("arxiv_id"):
        return str(record["arxiv_id"]), "arxiv"
    if record.get("pmid"):
        return str(record["pmid"]), "pmid"
    return "", ""


def compute_download_fields(record: dict[str, Any]) -> tuple[bool, str]:
    """Return whether the record is downloadable and the preferred URL."""
    if record.get("pdf_url"):
        return True, str(record["pdf_url"])
    if record.get("pmcid"):
        return True, ""
    if record.get("arxiv_id"):
        return True, f"https://arxiv.org/pdf/{record['arxiv_id']}.pdf"
    return False, ""


def normalize_paper_record(
    paper: dict[str, Any],
    source: str = "",
    *,
    matched_by: str = "",
) -> PaperRecord:
    """Normalize a raw paper dictionary into a stable schema."""
    normalized_source = str(paper.get("source") or source or "")
    year = _normalize_year(paper.get("year", ""))
    published_at = str(paper.get("published_at") or year or "")

    base: dict[str, Any] = {
        "source": normalized_source,
        "raw_source": str(paper.get("raw_source") or normalized_source or ""),
        "raw_id": str(
            paper.get("raw_id")
            or paper.get("pmid")
            or paper.get("pmcid")
            or paper.get("arxiv_id")
            or ""
        ),
        "title": str(paper.get("title") or ""),
        "authors": _normalize_authors(paper.get("authors", [])),
        "year": year,
        "published_at": published_at,
        "abstract": str(paper.get("abstract") or ""),
        "journal": str(paper.get("journal") or ""),
        "repository": str(
            paper.get("repository") or ("arXiv" if normalized_source == "arxiv" else "")
        ),
        "pmid": str(paper.get("pmid") or ""),
        "pmcid": str(paper.get("pmcid") or ""),
        "doi": str(paper.get("doi") or ""),
        "arxiv_id": str(paper.get("arxiv_id") or ""),
        "pdf_url": str(paper.get("pdf_url") or ""),
        "download_type": str(paper.get("download_type") or ""),
        "matched_by": str(paper.get("matched_by") or matched_by or ""),
        "inPMC": str(paper.get("inPMC") or ""),
    }

    identifier, identifier_type = build_identifier(base)
    is_downloadable, download_url = compute_download_fields(base)

    if not base["download_type"]:
        if base["pmcid"]:
            base["download_type"] = "pmc"
        elif base["arxiv_id"]:
            base["download_type"] = "arxiv"
        elif base["pdf_url"]:
            base["download_type"] = "pdf"

    base["identifier"] = identifier
    base["identifier_type"] = identifier_type
    base["is_downloadable"] = is_downloadable
    base["download_url"] = download_url

    return base  # type: ignore[return-value]
