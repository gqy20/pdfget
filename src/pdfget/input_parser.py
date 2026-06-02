"""Parse CLI and CSV inputs into normalized paper records."""

from __future__ import annotations

import csv
import os

from .paper_schema import normalize_paper_record
from .utils.identifier_utils import IdentifierUtils


def detect_input_type(input_str: str) -> str:
    """Detect whether input is a CSV path, single identifier, or list."""
    if not input_str or not input_str.strip():
        return "invalid"

    input_str = input_str.strip()
    if os.path.exists(input_str):
        return "csv_file"
    if "," in input_str:
        return "multiple"
    return "single"


def auto_detect_column(csv_path: str) -> str | None:
    """Pick the best identifier column from a CSV header."""
    priority_columns = ["ID", "PMCID", "doi", "pmid"]

    with open(csv_path, encoding="utf-8") as f:
        csv_reader = csv.reader(f)
        header = next(csv_reader, None)

        if header is None or not header:
            return None

        header_map = {col.upper(): col for col in header}
        for priority_col in priority_columns:
            if priority_col.upper() in header_map:
                return header_map[priority_col.upper()]

        return header[0] if header else None


def parse_identifier_string(id_str: str) -> list[str]:
    """Parse a single identifier or comma-separated identifier list."""
    if not id_str or not id_str.strip():
        return []
    return [identifier.strip() for identifier in id_str.split(",") if identifier.strip()]


def read_identifier_values_from_csv(csv_path: str, id_column: str = "ID") -> list[str]:
    """Read raw identifier values from a CSV column while preserving row order."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

    values: list[str] = []
    with open(csv_path, encoding="utf-8") as f:
        csv_reader = csv.reader(f)
        header = next(csv_reader, None)
        if header is None:
            return values

        id_col_index = 0
        for i, col in enumerate(header):
            if col.strip().lower() == id_column.lower():
                id_col_index = i
                break

        for row in csv_reader:
            if not row or id_col_index >= len(row):
                continue
            identifier = row[id_col_index].strip()
            if identifier:
                values.append(identifier)

    return values


def classify_identifiers(identifiers: list[str]) -> dict[str, list[str]]:
    """Classify raw identifiers by supported identifier type."""
    classified: dict[str, list[str]] = {
        "pmcids": [],
        "pmids": [],
        "dois": [],
        "arxiv_ids": [],
    }

    for identifier in identifiers:
        id_type = IdentifierUtils.detect_identifier_type(identifier)
        if id_type == "pmcid":
            normalized_pmcid = IdentifierUtils.format_pmcid(identifier)
            if normalized_pmcid:
                classified["pmcids"].append(normalized_pmcid)
        elif id_type == "pmid":
            classified["pmids"].append(identifier)
        elif id_type == "doi":
            classified["dois"].append(identifier)
        elif id_type == "arxiv":
            normalized_arxiv_id = IdentifierUtils.normalize_arxiv_id(identifier)
            if normalized_arxiv_id:
                classified["arxiv_ids"].append(normalized_arxiv_id)

    return classified


def build_papers_from_identifiers(identifiers: list[str]) -> list[dict]:
    """Build paper records in the same order as user input."""
    papers: list[dict] = []
    for identifier in identifiers:
        id_type = IdentifierUtils.detect_identifier_type(identifier)
        if id_type == "pmcid":
            normalized_pmcid = IdentifierUtils.format_pmcid(identifier)
            if normalized_pmcid:
                papers.append(
                    normalize_paper_record(
                        {
                            "pmcid": normalized_pmcid,
                            "title": f"PMCID: {normalized_pmcid}",
                            "source": "direct_pmcid",
                        },
                        "direct_pmcid",
                        matched_by="pmcid",
                    )
                )
        elif id_type == "pmid":
            papers.append(
                normalize_paper_record(
                    {
                        "pmid": identifier,
                        "title": f"PMID: {identifier}",
                        "source": "mixed_identifiers",
                    },
                    "mixed_identifiers",
                    matched_by="pmid",
                )
            )
        elif id_type == "doi":
            papers.append(
                normalize_paper_record(
                    {
                        "doi": identifier,
                        "title": f"DOI: {identifier}",
                        "source": "mixed_identifiers",
                    },
                    "mixed_identifiers",
                    matched_by="doi",
                )
            )
        elif id_type == "arxiv":
            normalized_arxiv_id = IdentifierUtils.normalize_arxiv_id(identifier)
            if normalized_arxiv_id:
                papers.append(
                    normalize_paper_record(
                        {
                            "arxiv_id": normalized_arxiv_id,
                            "title": f"arXiv: {normalized_arxiv_id}",
                            "source": "direct_arxiv",
                        },
                        "direct_arxiv",
                        matched_by="arxiv_id",
                    )
                )

    return papers
