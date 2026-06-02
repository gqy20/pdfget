#!/usr/bin/env python3
"""Unified concurrent download manager."""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .config import DOWNLOAD_BASE_DELAY, DOWNLOAD_RANDOM_DELAY
from .downloader import PDFDownloader
from .logger import get_logger
from .protocols import DownloadContext


class UnifiedDownloadManager:
    """Manage concurrent downloads across supported paper identifiers."""

    def __init__(
        self,
        fetcher: DownloadContext,
        max_workers: int = 1,
        base_delay: float = DOWNLOAD_BASE_DELAY,
        random_delay_range: float = DOWNLOAD_RANDOM_DELAY,
        source_priority: list[str] | None = None,
    ):
        self.logger = get_logger(__name__)
        self.fetcher = fetcher
        self.max_workers = max_workers
        self.base_delay = base_delay
        self.random_delay_range = random_delay_range
        self.source_priority = source_priority

        self._lock = threading.Lock()
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0
        self._total = 0
        self._thread_local = threading.local()

    def _paper_identity(self, paper: dict[str, Any]) -> str:
        """Return the best identifier for mapping results back to inputs."""
        return paper.get("doi") or paper.get("pmcid") or paper.get("arxiv_id") or ""

    def _get_delay(self) -> float:
        """Add small jitter so concurrent requests do not synchronize."""
        if self.random_delay_range > 0:
            return self.base_delay + random.uniform(0, self.random_delay_range)
        return self.base_delay

    def _update_progress(
        self, success: bool = False, pdf_downloaded: bool = False
    ) -> None:
        """Update thread-safe progress counters."""
        with self._lock:
            self._completed += 1
            if success:
                self._successful += 1
                if pdf_downloaded:
                    self._pdf_count += 1
            else:
                self._failed += 1

            progress = (self._completed / self._total) * 100
            self.logger.info(
                f"  进度: {self._completed}/{self._total} ({progress:.1f}%) "
                f"成功: {self._successful} PDF: {self._pdf_count} 失败: {self._failed}"
            )

    def _create_thread_downloader(self) -> PDFDownloader:
        """Create an isolated downloader instance for each worker thread."""
        return PDFDownloader(
            str(self.fetcher.output_dir),
            self.fetcher.session,
            source_priority=self.source_priority,
        )

    def _get_thread_downloader(self) -> PDFDownloader:
        """Return a downloader instance reused within the current worker thread."""
        downloader = getattr(self._thread_local, "downloader", None)
        if downloader is None:
            downloader = self._create_thread_downloader()
            self._thread_local.downloader = downloader
        return downloader

    def _download_single_task(
        self, paper: dict[str, Any], timeout: int = 30
    ) -> dict[str, Any]:
        """Download a single paper inside a worker thread."""
        try:
            time.sleep(self._get_delay())
            downloader = self._get_thread_downloader()
            result = downloader.download_paper(paper)
            result["doi"] = paper.get("doi", "")
            result["pmcid"] = paper.get("pmcid", "") or ""
            result["arxiv_id"] = paper.get("arxiv_id", "") or ""

            success = result.get("success", False)
            pdf_downloaded = bool(result.get("path"))
            self._update_progress(success, pdf_downloaded)
            return result
        except Exception as exc:
            identifier = self._paper_identity(paper) or "unknown"
            self.logger.debug(f"下载失败 ({identifier}): {exc}")
            self._update_progress(False)
            return {
                "doi": paper.get("doi", ""),
                "pmcid": paper.get("pmcid", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "success": False,
                "error": str(exc),
                "stage": "worker_error",
                "source": "worker",
                "attempts": [
                    {
                        "source": "worker",
                        "success": False,
                        "stage": "worker_error",
                        "error": str(exc),
                    }
                ],
            }

    def _download_concurrent(self, papers: list[dict], timeout: int = 30) -> list[dict]:
        """Download papers concurrently and preserve input ordering."""
        self._total = len(papers)
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

        ordered_results: list[dict[str, Any] | None] = [None] * len(papers)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index: dict[Any, int] = {}
            for index, paper in enumerate(papers):
                future = executor.submit(self._download_single_task, paper, timeout)
                future_to_index[future] = index

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                paper = papers[index]
                try:
                    ordered_results[index] = future.result()
                except Exception as exc:
                    ordered_results[index] = (
                        {
                            "doi": paper.get("doi", ""),
                            "pmcid": paper.get("pmcid", ""),
                            "arxiv_id": paper.get("arxiv_id", ""),
                            "success": False,
                            "error": str(exc),
                            "stage": "worker_error",
                            "source": "worker",
                            "attempts": [
                                {
                                    "source": "worker",
                                    "success": False,
                                    "stage": "worker_error",
                                    "error": str(exc),
                                }
                            ],
                        }
                    )

        return [
            result
            if result is not None
            else {
                "doi": paper.get("doi", ""),
                "pmcid": paper.get("pmcid", ""),
                "arxiv_id": paper.get("arxiv_id", ""),
                "success": False,
                "error": "Not found",
                "stage": "worker_error",
                "source": "worker",
                "attempts": [
                    {
                        "source": "worker",
                        "success": False,
                        "stage": "worker_error",
                        "error": "Not found",
                    }
                ],
            }
            for paper, result in zip(papers, ordered_results, strict=True)
        ]

    def download_batch(
        self,
        papers: list[dict[str, Any]],
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Download a batch of papers."""
        if not papers:
            return []

        doi_count = sum(1 for paper in papers if paper.get("doi"))
        pmcid_count = sum(1 for paper in papers if paper.get("pmcid"))
        arxiv_count = sum(
            1 for paper in papers if paper.get("arxiv_id") or paper.get("pdf_url")
        )

        if not doi_count and not pmcid_count and not arxiv_count:
            self.logger.warning("没有有效的 DOI、PMCID 或 arXiv 标识符可以下载")
            return []

        return self._download_concurrent(papers, timeout)
