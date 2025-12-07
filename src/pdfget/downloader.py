#!/usr/bin/env python3
"""
并发下载器 - 提升PDF下载效率
使用线程池实现并发下载，同时保持API调用限制
"""

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable, Optional

from .fetcher import PaperFetcher


class ConcurrentDownloader:
    """并发下载管理器"""

    def __init__(
        self,
        max_workers: int = 3,
        base_delay: float = 1.0,
        random_delay_range: float = 0.5,
        fetcher: Optional[PaperFetcher] = None,
    ):
        """
        初始化并发下载器

        Args:
            max_workers: 最大并发线程数（默认3）
            base_delay: 基础延迟时间（秒）
            random_delay_range: 随机延迟范围（秒）
            fetcher: PaperFetcher实例（可选）
        """
        self.logger = logging.getLogger("ConcurrentDownloader")
        self.max_workers = max_workers
        self.base_delay = base_delay
        self.random_delay_range = random_delay_range

        # 为每个线程创建独立的fetcher实例（避免session冲突）
        if fetcher:
            self.base_fetcher = fetcher
        else:
            self.base_fetcher = PaperFetcher()

        # 线程安全的进度跟踪
        self._lock = threading.Lock()
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

    def _get_delay(self) -> float:
        """获取随机延迟时间，避免同步请求"""
        random_delay = random.uniform(0, self.random_delay_range)
        return self.base_delay + random_delay

    def _create_thread_fetcher(self) -> PaperFetcher:
        """为线程创建独立的fetcher实例"""
        # 复制基础配置，但创建新的session
        fetcher = PaperFetcher(
            cache_dir=str(self.base_fetcher.cache_dir),
            output_dir=str(self.base_fetcher.output_dir),
        )
        return fetcher

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

    def _download_single(
        self, doi: str, fetcher: PaperFetcher, timeout: int = 30
    ) -> Dict[str, Any]:
        """单个文献的下载任务"""
        try:
            # 添加随机延迟
            time.sleep(self._get_delay())

            result = fetcher.fetch_by_doi(doi, timeout=timeout)

            # 更新进度
            success = result.get("success", False)
            pdf_downloaded = bool(result.get("pdf_path"))
            self._update_progress(success, pdf_downloaded)

            return result

        except Exception as e:
            self.logger.debug(f"下载失败 ({doi}): {str(e)}")
            self._update_progress(False)
            return {"doi": doi, "success": False, "error": str(e)}

    def download_batch(
        self, dois: List[str], timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """
        并发批量下载文献

        Args:
            dois: DOI列表
            timeout: 单个请求超时时间

        Returns:
            下载结果列表
        """
        if not dois:
            return []

        self.logger.info(
            f"🚀 启动并发下载：{len(dois)} 篇文献，{self.max_workers} 个并发线程"
        )

        # 初始化进度跟踪
        self._total = len(dois)
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

        results = []

        # 使用线程池执行并发下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_doi = {}

            for doi in dois:
                # 为每个线程创建独立的fetcher
                thread_fetcher = self._create_thread_fetcher()
                future = executor.submit(
                    self._download_single, doi, thread_fetcher, timeout
                )
                future_to_doi[future] = doi

            # 收集结果（保持原始顺序）
            for future in as_completed(future_to_doi):
                doi = future_to_doi[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"并发下载异常 ({doi}): {str(e)}")
                    results.append({"doi": doi, "success": False, "error": str(e)})

        # 按原始DOI顺序重新排列结果
        doi_to_result = {r["doi"]: r for r in results}
        ordered_results = [
            doi_to_result.get(doi, {"doi": doi, "success": False, "error": "Not found"})
            for doi in dois
        ]

        # 最终统计
        self.logger.info("\n📊 并发下载完成:")
        self.logger.info(f"   总计: {len(ordered_results)}")
        self.logger.info(f"   成功: {self._successful}")
        self.logger.info(f"   PDF: {self._pdf_count}")
        self.logger.info(f"   失败: {self._failed}")
        self.logger.info(
            f"   成功率: {(self._successful / len(ordered_results)) * 100:.1f}%"
        )

        return ordered_results

    def download_with_progress_callback(
        self,
        dois: List[str],
        timeout: int = 30,
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        带进度回调的并发下载

        Args:
            dois: DOI列表
            timeout: 超时时间
            progress_callback: 进度回调函数 (completed, successful, pdf_count, total)

        Returns:
            下载结果列表
        """
        if not dois:
            return []

        self.logger.info(
            f"🚀 启动并发下载：{len(dois)} 篇文献，{self.max_workers} 个并发线程"
        )

        # 初始化进度跟踪
        self._total = len(dois)
        self._completed = 0
        self._successful = 0
        self._failed = 0
        self._pdf_count = 0

        results = []

        def update_progress_with_callback(
            success: bool = False, pdf_downloaded: bool = False
        ) -> None:
            """带回调的进度更新"""
            self._update_progress(success, pdf_downloaded)
            if progress_callback:
                progress_callback(
                    self._completed, self._successful, self._pdf_count, self._total
                )

        # 使用线程池执行并发下载，避免方法赋值
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_doi = {}

                for doi in dois:
                    thread_fetcher = self._create_thread_fetcher()
                    # 直接使用线程中的update_with_progress方法
                    future = executor.submit(
                        self._download_single_with_callback,
                        doi,
                        thread_fetcher,
                        timeout,
                        update_progress_with_callback,
                    )
                    future_to_doi[future] = doi

                for future in as_completed(future_to_doi):
                    doi = future_to_doi[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        self.logger.error(f"并发下载异常 ({doi}): {str(e)}")
                        results.append({"doi": doi, "success": False, "error": str(e)})

            # 按原始顺序排列结果
            doi_to_result = {r["doi"]: r for r in results}
            ordered_results = [
                doi_to_result.get(
                    doi, {"doi": doi, "success": False, "error": "Not found"}
                )
                for doi in dois
            ]

            # 最终统计和最后一次回调
            self.logger.info("\n📊 并发下载完成:")
            self.logger.info(f"   总计: {len(ordered_results)}")
            self.logger.info(f"   成功: {self._successful}")
            self.logger.info(f"   PDF: {self._pdf_count}")
            self.logger.info(f"   失败: {self._failed}")
            self.logger.info(
                f"   成功率: {(self._successful / len(ordered_results)) * 100:.1f}%"
            )

            if progress_callback:
                progress_callback(
                    self._completed, self._successful, self._pdf_count, self._total
                )

            return ordered_results

        finally:
            pass

    def _download_single_with_callback(
        self,
        doi: str,
        thread_fetcher: PaperFetcher,
        timeout: int,
        progress_callback: Callable[[], None],
    ) -> Dict[str, Any]:
        """带回调的单个文献下载（用于并发下载）"""
        try:
            # 添加随机延迟避免API限制
            delay = self._get_delay()
            time.sleep(delay)

            # 获取文献信息
            paper_info = thread_fetcher.fetch_by_doi(doi, timeout)
            if not paper_info:
                progress_callback()
                return {"doi": doi, "success": False, "error": "文献信息获取失败"}

            result = {"doi": doi, "success": True, "paper_info": paper_info}

            # 更新进度
            progress_callback()

            return result

        except Exception as e:
            progress_callback()
            self.logger.error(f"下载异常 ({doi}): {str(e)}")
            return {"doi": doi, "success": False, "error": str(e)}
