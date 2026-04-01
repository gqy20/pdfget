#!/usr/bin/env python3
"""Unified concurrent download manager."""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .config import DOWNLOAD_BASE_DELAY, DOWNLOAD_RANDOM_DELAY
from .fetcher import PaperFetcher
from .logger import get_logger


class UnifiedDownloadManager:
    """Manage concurrent downloads across supported paper identifiers."""

    def __init__(
        self,
        fetcher: PaperFetcher,
        max_workers: int = 1,
        base_delay: float = DOWNLOAD_BASE_DELAY,
        random_delay_range: float = DOWNLOAD_RANDOM_DELAY,
    ):
        self.logger = get_logger(__name__)
        self.fetcher = fetcher
        self.max_workers = max_workers
        self.base_delay = base_delay
        self.random_delay_range = random_delay_range

        self._lock = threading.Lock()
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0
        self._total = 0

    def _normalize_input(
        self, items: list[str] | list[dict]
    ) -> tuple[list[dict], list[str]]:
        """Normalize a DOI list or paper list into a common shape."""
        papers: list[dict] = []
        if items and isinstance(items[0], dict):
            papers = items  # type: ignore[assignment]
            dois = [paper["doi"] for paper in papers if paper.get("doi")]  # type: ignore[index]
        else:
            papers = [{"doi": item} for item in items]
            dois = items  # type: ignore[assignment]
        return papers, dois

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

    def _create_thread_fetcher(self) -> PaperFetcher:
        """Create an isolated fetcher instance for each worker thread."""
        return PaperFetcher(
            cache_dir=str(self.fetcher.cache_dir),
            output_dir=str(self.fetcher.output_dir),
        )

    def _download_single_task(
        self, paper: dict[str, Any], fetcher: PaperFetcher, timeout: int = 30
    ) -> dict[str, Any]:
        """Download a single paper inside a worker thread."""
        try:
            time.sleep(self._get_delay())
            result = fetcher.pdf_downloader.download_paper(paper)
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
            }

    def _download_concurrent(self, papers: list[dict], timeout: int = 30) -> list[dict]:
        """Download papers concurrently and preserve input ordering."""
        self._total = len(papers)
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_paper = {}
            for paper in papers:
                thread_fetcher = self._create_thread_fetcher()
                future = executor.submit(
                    self._download_single_task, paper, thread_fetcher, timeout
                )
                future_to_paper[future] = paper

            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        {
                            "doi": paper.get("doi", ""),
                            "pmcid": paper.get("pmcid", ""),
                            "arxiv_id": paper.get("arxiv_id", ""),
                            "success": False,
                            "error": str(exc),
                        }
                    )

        identifier_to_result = {}
        for result in results:
            identifier = self._paper_identity(result)
            if identifier:
                identifier_to_result[identifier] = result

        ordered_results = []
        for paper in papers:
            identifier = self._paper_identity(paper)
            if identifier and identifier in identifier_to_result:
                ordered_results.append(identifier_to_result[identifier])
            else:
                ordered_results.append(
                    {
                        "doi": paper.get("doi", ""),
                        "pmcid": paper.get("pmcid", ""),
                        "arxiv_id": paper.get("arxiv_id", ""),
                        "success": False,
                        "error": "Not found",
                    }
                )

        return ordered_results

    def download_batch(
        self,
        items: list[str] | list[dict],
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """Download a batch of papers."""
        if not items:
            return []

        papers, dois = self._normalize_input(items)
        pmcid_count = sum(1 for paper in papers if paper.get("pmcid"))
        arxiv_count = sum(
            1 for paper in papers if paper.get("arxiv_id") or paper.get("pdf_url")
        )

        if not dois and not pmcid_count and not arxiv_count:
            self.logger.warning("没有有效的 DOI、PMCID 或 arXiv 标识符可以下载")
            return []

        return self._download_concurrent(papers, timeout)
