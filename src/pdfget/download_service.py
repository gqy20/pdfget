"""High-level download service functions."""

from __future__ import annotations

from typing import Any, Protocol, cast

from .config import DOWNLOAD_BASE_DELAY
from .download_plan import ready_papers
from .input_planner import build_download_plan_from_unified_input
from .protocols import UnifiedInputContext
from .schemas import DownloadResult


class DownloadManager(Protocol):
    """Batch downloader created by the download service."""

    def download_batch(
        self,
        papers: list[dict[str, Any]],
        timeout: int = 30,
    ) -> list[DownloadResult]: ...


class DownloadManagerFactory(Protocol):
    """Factory for creating a download manager."""

    def __call__(
        self,
        *,
        fetcher: UnifiedInputContext,
        max_workers: int,
        base_delay: float,
    ) -> DownloadManager: ...


def download_from_unified_input(
    fetcher: UnifiedInputContext,
    input_value: str,
    *,
    column: str | None = None,
    limit: int | None = None,
    max_workers: int = 1,
    base_delay: float | None = None,
    download_manager_cls: DownloadManagerFactory | None = None,
) -> list[DownloadResult]:
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

        manager_factory = cast(DownloadManagerFactory, UnifiedDownloadManager)
    else:
        manager_factory = download_manager_cls

    download_manager = manager_factory(
        fetcher=fetcher,
        max_workers=max_workers,
        base_delay=base_delay if base_delay is not None else DOWNLOAD_BASE_DELAY,
    )
    return cast(list[DownloadResult], download_manager.download_batch(papers))
