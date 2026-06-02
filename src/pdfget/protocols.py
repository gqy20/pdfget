"""Shared structural protocols for service boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import requests


class ServiceLogger(Protocol):
    """Minimal logger surface used by orchestration services."""

    def info(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...


class IdentifierResolver(Protocol):
    """Resolve PMID/DOI values to PMCID values for download planning."""

    def resolve_pmids(self, pmids: list[str]) -> Mapping[str, str]: ...

    def resolve_dois(self, dois: list[str]) -> Mapping[str, str]: ...


class SearchProvider(IdentifierResolver, Protocol):
    """Search and resolve papers for CLI workflows."""

    email: str
    api_key: str
    logger: ServiceLogger

    def search_papers(
        self,
        query: str,
        limit: int = 50,
        source: str | None = None,
        use_cache: bool = True,
        fetch_pmcid: bool = False,
    ) -> list[dict[Any, Any]]: ...


class DownloadContext(Protocol):
    """Configuration needed to create per-worker PDF downloaders."""

    output_dir: str | Path
    session: requests.Session


class UnifiedInputContext(SearchProvider, DownloadContext, Protocol):
    """Capabilities needed by unified input planning and downloading."""

