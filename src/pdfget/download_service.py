"""High-level download service functions."""

from __future__ import annotations

from typing import Any, Protocol

from .config import DOWNLOAD_BASE_DELAY
from .download_plan import IdentifierResolver, ready_papers
from .input_planner import build_download_plan_from_unified_input


class DownloadLogger(Protocol):
    """Minimal logger surface used by unified input downloads."""

    def info(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...


class UnifiedInputFetcher(IdentifierResolver, Protocol):
    """Fetcher capabilities needed by unified input download service."""

    logger: DownloadLogger


def download_from_unified_input(
    fetcher: UnifiedInputFetcher,
    input_value: str,
    *,
    column: str | None = None,
    limit: int | None = None,
    max_workers: int = 1,
    base_delay: float | None = None,
    download_manager_cls: Any | None = None,
) -> list[dict[str, Any]]:
    """Build a plan from unified input and execute downloads."""
    plan = build_download_plan_from_unified_input(
        input_value,
        column=column,
        limit=limit,
        resolver=fetcher,
        logger=fetcher.logger,
    )
    papers = ready_papers(plan)
    if not papers:
        fetcher.logger.warning("没有找到可下载的标识符")
        return []

    if download_manager_cls is None:
        from .manager import UnifiedDownloadManager

        download_manager_cls = UnifiedDownloadManager

    download_manager = download_manager_cls(
        fetcher=fetcher,
        max_workers=max_workers,
        base_delay=base_delay if base_delay is not None else DOWNLOAD_BASE_DELAY,
    )
    return download_manager.download_batch(papers)
