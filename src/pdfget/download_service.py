"""High-level download service.

The function ``download_from_unified_input`` is the single public façade for
external callers; it composes ``build_download_plan_from_unified_input`` (in
:mod:`input_planner`) with ``execute_download_plan`` (defined here).

CLI workflows import :func:`execute_download_plan` directly so they do not
have to re-build the plan to drive the manager.
"""

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
        source_priority: list[str] | None = None,
    ) -> DownloadManager: ...


def execute_download_plan(
    plan: dict[str, Any],
    *,
    fetcher: UnifiedInputContext,
    max_workers: int = 1,
    base_delay: float | None = None,
    source_priority: list[str] | None = None,
    download_manager_cls: DownloadManagerFactory | None = None,
) -> list[DownloadResult]:
    """Drive ``UnifiedDownloadManager`` against an already-built plan.

    Pure orchestration: pull ready papers from ``plan``, instantiate the
    configured manager, and return its results. Does not write files or
    emit reports — those concerns belong to the CLI layer.
    """
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
        source_priority=source_priority,
    )
    return cast(
        list[DownloadResult],
        download_manager.download_batch(papers),
    )


def download_from_unified_input(
    fetcher: UnifiedInputContext,
    input_value: str,
    *,
    column: str | None = None,
    limit: int | None = None,
    max_workers: int = 1,
    base_delay: float | None = None,
    source_priority: list[str] | None = None,
    download_manager_cls: DownloadManagerFactory | None = None,
) -> list[DownloadResult]:
    """Build a plan from unified input and execute it.

    Convenience façade for external callers who do not need to inspect the
    intermediate :class:`DownloadPlan`; see :func:`build_download_plan_from_unified_input`
    and :func:`execute_download_plan` for finer-grained control.
    """
    plan = build_download_plan_from_unified_input(
        input_value,
        column=column,
        limit=limit,
        resolver=fetcher,
        logger=fetcher.logger,
    )
    return execute_download_plan(
        plan,
        fetcher=fetcher,
        max_workers=max_workers,
        base_delay=base_delay,
        source_priority=source_priority,
        download_manager_cls=download_manager_cls,
    )
