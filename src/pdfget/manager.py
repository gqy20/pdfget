#!/usr/bin/env python3
"""
统一下载管理器
根据参数自动选择单线程或多线程下载策略
"""

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .config import DOWNLOAD_BASE_DELAY, DOWNLOAD_RANDOM_DELAY
from .fetcher import PaperFetcher
from .logger import get_logger


class UnifiedDownloadManager:
    """统一下载管理器，支持单线程和多线程下载"""

    def __init__(
        self,
        fetcher: PaperFetcher,
        max_workers: int = 1,
        base_delay: float = DOWNLOAD_BASE_DELAY,
        random_delay_range: float = DOWNLOAD_RANDOM_DELAY,
    ):
        """
        初始化下载管理器

        Args:
            fetcher: PaperFetcher实例
            max_workers: 最大并发线程数
            base_delay: 基础延迟时间（秒，从配置文件读取）
            random_delay_range: 随机延迟范围（秒，从配置文件读取）
        """
        self.logger = get_logger(__name__)
        self.fetcher = fetcher
        self.max_workers = max_workers
        self.base_delay = base_delay
        self.random_delay_range = random_delay_range

        # 线程安全的进度跟踪（仅多线程使用）
        self._lock = threading.Lock()
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0
        self._total = 0

    def _normalize_input(
        self, items: list[str] | list[dict]
    ) -> tuple[list[dict], list[str]]:
        """
        标准化输入格式

        Args:
            items: DOI列表或论文信息列表

        Returns:
            (论文信息列表, DOI列表)
        """
        papers: list[dict] = []
        if items and isinstance(items[0], dict):
            # 输入是论文信息列表
            papers = items  # type: ignore
            dois = [p["doi"] for p in papers if p.get("doi")]  # type: ignore
        else:
            # 输入是DOI列表
            papers = [{"doi": d} for d in items]
            dois = items  # type: ignore

        return papers, dois

    def _get_delay(self) -> float:
        """获取随机延迟时间，避免同步请求"""
        if self.random_delay_range > 0:
            random_delay = random.uniform(0, self.random_delay_range)
            return self.base_delay + random_delay
        return self.base_delay

    def _update_progress(
        self, success: bool = False, pdf_downloaded: bool = False
    ) -> None:
        """线程安全的进度更新"""
        with self._lock:
            self._completed += 1
            if success:
                self._successful += 1
                if pdf_downloaded:
                    self._pdf_count += 1
            else:
                self._failed += 1

            # 简单的进度显示
            progress = (self._completed / self._total) * 100
            self.logger.info(
                f"  进度: {self._completed}/{self._total} ({progress:.1f}%) "
                f"成功: {self._successful} PDF: {self._pdf_count} 失败: {self._failed}"
            )

    def _create_thread_fetcher(self) -> PaperFetcher:
        """为线程创建独立的fetcher实例"""
        # 复制基础配置，但创建新的session
        fetcher = PaperFetcher(
            cache_dir=str(self.fetcher.cache_dir),
            output_dir=str(self.fetcher.output_dir),
        )
        return fetcher

    def _download_concurrent(self, papers: list[dict], timeout: int = 30) -> list[dict]:
        """
        多线程并发下载

        Args:
            papers: 论文信息列表
            timeout: 单个请求超时时间

        Returns:
            下载结果列表
        """
        self.logger.info(
            f"🚀 启动并发下载：{len(papers)} 篇文献，{self.max_workers} 个并发线程"
        )

        # 初始化进度跟踪
        self._total = len(papers)
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

        results = []

        # 使用线程池执行并发下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_identifier = {}

            for paper in papers:
                # 为每个线程创建独立的fetcher
                thread_fetcher = self._create_thread_fetcher()
                doi = paper.get("doi")
                pmcid = paper.get("pmcid")
                identifier = doi or pmcid  # 使用 DOI 或 PMCID 作为标识符

                future = executor.submit(
                    self._download_single_task,
                    doi,
                    pmcid,
                    thread_fetcher,
                    timeout,
                )
                future_to_identifier[future] = (doi, pmcid)

            # 收集结果
            for future in as_completed(future_to_identifier):
                doi, pmcid = future_to_identifier[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    identifier = doi or pmcid or "unknown"
                    self.logger.error(f"并发下载异常 ({identifier}): {str(e)}")
                    results.append(
                        {"doi": doi, "pmcid": pmcid, "success": False, "error": str(e)}
                    )

        # 按原始顺序重新排列结果
        # 创建一个标识符到结果的映射（优先使用DOI，其次是PMCID）
        identifier_to_result = {}
        for r in results:
            if r.get("doi"):
                identifier_to_result[r["doi"]] = r
            elif r.get("pmcid"):
                identifier_to_result[r["pmcid"]] = r

        # 按原始论文顺序排列结果
        ordered_results = []
        for paper in papers:
            doi = paper.get("doi")
            pmcid = paper.get("pmcid")
            identifier = doi or pmcid

            if identifier:
                lookup_result = identifier_to_result.get(identifier)
                if lookup_result:
                    ordered_results.append(lookup_result)
                else:
                    # 创建默认失败结果
                    ordered_results.append(
                        {
                            "doi": doi or "",
                            "pmcid": pmcid or "",
                            "success": False,
                            "error": "Not found",
                        }
                    )

        # 最终统计
        self.logger.info("\n📊 并发下载完成:")
        self.logger.info(f"   总计: {len(ordered_results)}")
        self.logger.info(f"   成功: {self._successful}")
        self.logger.info(f"   PDF: {self._pdf_count}")
        self.logger.info(f"   失败: {self._failed}")
        if len(ordered_results) > 0:
            self.logger.info(
                f"   成功率: {(self._successful / len(ordered_results)) * 100:.1f}%"
            )

        return ordered_results

    def _download_single_task(
        self, doi: str, pmcid: str | None, fetcher: PaperFetcher, timeout: int = 30
    ) -> dict[str, Any]:
        """单个文献的下载任务（线程池中的任务）"""
        try:
            # 添加随机延迟
            time.sleep(self._get_delay())

            # 直接使用PDFDownloader下载
            if pmcid:
                result = fetcher.pdf_downloader.download_pdf(pmcid, doi)
            else:
                # 如果没有PMCID，尝试搜索
                papers = fetcher.search_papers(doi, limit=1)
                if papers and papers[0].get("pmcid"):
                    pmcid = papers[0]["pmcid"]
                    result = fetcher.pdf_downloader.download_pdf(pmcid, doi)
                else:
                    result = {"success": False, "error": "No PMCID found"}

            # 添加必要的信息
            result["doi"] = doi
            result["pmcid"] = pmcid or ""

            # 更新进度
            success = result.get("success", False)
            pdf_downloaded = bool(result.get("path"))
            self._update_progress(success, pdf_downloaded)

            return result

        except Exception as e:
            self.logger.debug(f"下载失败 ({doi}): {str(e)}")
            self._update_progress(False)
            return {"doi": doi, "success": False, "error": str(e)}

    def download_batch(
        self,
        items: list[str] | list[dict],
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        """
        批量下载文献（使用并发下载）

        Args:
            items: DOI列表或论文信息列表
            timeout: 单个请求超时时间

        Returns:
            下载结果列表
        """
        if not items:
            return []

        # 标准化输入
        papers, dois = self._normalize_input(items)

        # 检查是否有 PMCID（即使没有 DOI 也可以下载）
        pmcid_count = sum(1 for p in papers if p.get("pmcid"))

        if not dois and not pmcid_count:
            self.logger.warning("⚠️ 没有有效的DOI或PMCID可以下载")
            return []

        # 总是使用并发下载（max_workers=1 时相当于单线程）
        return self._download_concurrent(papers, timeout)
