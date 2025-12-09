#!/usr/bin/env python3
"""
简化版文献获取器 - Linus风格
只做一件事：下载开放获取文献
遵循KISS原则：Keep It Simple, Stupid
"""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

from .downloader import PDFDownloader
from .logger import get_logger
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher


class PaperFetcher:
    """简单文献获取器"""

    def __init__(
        self,
        cache_dir: str = "data/cache",
        output_dir: str = "data/pdfs",
        default_source: str = "pubmed",
        sources: "list[str] | None" = None,
    ):
        """
        初始化获取器

        Args:
            cache_dir: 缓存目录
            output_dir: PDF输出目录
            default_source: 默认数据源 (pubmed, europe_pmc)
            sources: 支持的数据源列表
        """
        self.logger = get_logger(__name__)
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)
        self.default_source = default_source
        self.sources = sources or ["pubmed", "europe_pmc"]

        # 确保目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建 requests session
        self.session = requests.Session()

        # 初始化子模块
        self.searcher = PaperSearcher(self.session)
        self.pmcid_retriever = PMCIDRetriever(self.session)
        self.pdf_downloader = PDFDownloader(str(self.output_dir), self.session)

        # NCBI 配置（用于缓存）
        self.email = ""  # 可配置邮箱以提高请求限制
        self.api_key = ""  # 可选 API 密钥

    def _get_cache_file(self, query: str, source: str) -> Path:
        """获取缓存文件路径"""
        content = f"{query}:{source}".encode()
        hash_key = hashlib.md5(content).hexdigest()
        return self.cache_dir / f"search_{hash_key}.json"

    def _load_cache(self, cache_file: Path) -> list[dict[str, Any]] | None:
        """加载搜索缓存"""
        try:
            if cache_file.exists():
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    # 确保 data 是正确的类型
                    if isinstance(data, list):
                        return data
                    return []
        except Exception as e:
            self.logger.error(f"读取缓存失败 {cache_file}: {str(e)}")
        return None

    def _save_cache(self, cache_file: Path, papers: list[dict]) -> None:
        """保存搜索缓存"""
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"保存缓存失败 {cache_file}: {str(e)}")

    def search_papers(
        self,
        query: str,
        limit: int = 50,
        source: "str | None" = None,
        use_cache: bool = True,
    ) -> list[dict]:
        """
        搜索文献

        Args:
            query: 检索词
            limit: 返回数量限制
            source: 数据源
            use_cache: 是否使用缓存

        Returns:
            文献列表
        """
        # 检查缓存
        if use_cache:
            cache_file = self._get_cache_file(query, source or self.default_source)
            cached_papers = self._load_cache(cache_file)
            if cached_papers:
                self.logger.info(f"从缓存加载 {len(cached_papers)} 条结果")
                return cached_papers

        # 执行搜索
        papers = self.searcher.search_papers(query, limit, source)

        # 保存到缓存
        if use_cache and papers:
            self._save_cache(cache_file, papers)

        return papers

    def add_pmcids(self, papers: list[dict], use_fallback: bool = True) -> list[dict]:
        """
        批量添加 PMCID

        Args:
            papers: 论文列表
            use_fallback: 是否使用逐个获取作为备选

        Returns:
            更新后的论文列表
        """
        self.logger.info(f"为 {len(papers)} 篇论文添加 PMCID")
        return self.pmcid_retriever.process_papers(papers, use_fallback)

    def fetch_by_doi(
        self, doi: str, pmcid: str | None = None, timeout: int = 30
    ) -> dict:
        """
        通过 DOI 获取文献

        Args:
            doi: DOI
            pmcid: 可选的 PMCID（如果已知）
            timeout: 请求超时时间

        Returns:
            获取结果字典
        """
        self.logger.info(f"获取文献: DOI={doi}")

        # 如果没有 PMCID，尝试通过 DOI 搜索
        if not pmcid:
            # 使用 DOI 作为查询词搜索
            papers = self.search_papers(doi, limit=1, source="europe_pmc")
            if papers:
                paper = papers[0]
                pmcid = paper.get("pmcid")
                if pmcid:
                    self.logger.info(f"找到 PMCID: {pmcid}")

        # 如果有 PMCID，尝试下载 PDF
        if pmcid:
            result = self.pdf_downloader.download_pdf(pmcid, doi)
            result["doi"] = doi
            result["pmcid"] = pmcid
            return result

        # 没有找到 PMCID 或下载失败
        return {
            "doi": doi,
            "pmcid": "",
            "success": False,
            "error": "未找到 PMCID 或无法下载",
            "pdf_path": None,
            "full_text_url": None,
        }

    def download_pdfs(
        self,
        papers: list[dict],
        skip_existing: bool = True,
        progress_callback: "Callable[[int, int, dict], None] | None" = None,
    ) -> dict:
        """
        批量下载 PDF

        Args:
            papers: 论文列表（需要包含 pmcid 字段）
            skip_existing: 跳过已存在的文件
            progress_callback: 进度回调函数

        Returns:
            下载结果统计
        """
        results: dict[str, Any] = {
            "total": len(papers),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        self.logger.info(f"开始下载 {len(papers)} 个 PDF")

        for i, paper in enumerate(papers):
            pmcid = paper.get("pmcid", "")
            doi = paper.get("doi", "")

            if not pmcid:
                self.logger.warning(
                    f"跳过没有 PMCID 的论文: {paper.get('title', 'Unknown')[:50]}"
                )
                results["failed"] += 1
                continue

            # 检查是否已存在
            if skip_existing and self.pdf_downloader.check_pdf_exists(pmcid, doi):
                results["skipped"] += 1
                continue

            # 下载 PDF
            download_result = self.pdf_downloader.download_if_not_exists(pmcid, doi)

            if download_result["success"]:
                results["success"] += 1
                self.logger.info(f"  ✓ [{i + 1}/{len(papers)}] {pmcid}")
            else:
                results["failed"] += 1
                error_msg = f"  ✗ [{i + 1}/{len(papers)}] {pmcid}: {download_result.get('error', 'Unknown error')}"
                self.logger.error(error_msg)
                results["errors"].append(error_msg)

            # 调用进度回调
            if progress_callback:
                progress_callback(i + 1, len(papers), results)

        # 输出统计
        self.logger.info(
            f"下载完成: 成功 {results['success']}, "
            f"失败 {results['failed']}, "
            f"跳过 {results['skipped']}"
        )

        return results

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        cache_files = list(self.cache_dir.glob("search_*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "search_cache_count": len(cache_files),
            "search_cache_size_bytes": total_size,
            "search_cache_size_mb": round(total_size / (1024 * 1024), 2),
            "pdf_cache": self.pdf_downloader.get_cache_info(),
        }

    def clear_cache(self, search_cache: bool = True, pdf_cache: bool = False) -> None:
        """
        清理缓存

        Args:
            search_cache: 是否清理搜索缓存
            pdf_cache: 是否清理 PDF 缓存
        """
        if search_cache:
            cache_files = list(self.cache_dir.glob("search_*.json"))
            for f in cache_files:
                f.unlink()
            self.logger.info(f"清理了 {len(cache_files)} 个搜索缓存文件")

        if pdf_cache:
            deleted_count = self.pdf_downloader.cleanup_old_pdfs(max_age_days=0)
            self.logger.info(f"清理了 {deleted_count} 个 PDF 文件")

    def export_results(
        self, papers: list[dict], format: str = "json", filename: "str | None" = None
    ) -> str:
        """
        导出搜索结果

        Args:
            papers: 论文列表
            format: 导出格式 (json, csv, tsv)
            filename: 输出文件名（可选）

        Returns:
            输出文件路径
        """
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"papers_{timestamp}.{format}"

        output_path = self.cache_dir / filename

        if format.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
        elif format.lower() in ["csv", "tsv"]:
            import csv

            delimiter = "," if format.lower() == "csv" else "\t"

            with open(output_path, "w", encoding="utf-8", newline="") as f:
                if papers:
                    writer = csv.DictWriter(
                        f, fieldnames=papers[0].keys(), delimiter=delimiter
                    )
                    writer.writeheader()
                    writer.writerows(papers)
        else:
            raise ValueError(f"不支持的格式: {format}")

        self.logger.info(f"结果已导出到: {output_path}")
        return str(output_path)

    def __enter__(self) -> "PaperFetcher":
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出时清理资源"""
        self.session.close()


# 便捷函数
def quick_search(query: str, limit: int = 20, source: str = "pubmed") -> list[dict]:
    """
    快速搜索文献

    Args:
        query: 搜索关键词
        limit: 结果数量
        source: 数据源

    Returns:
        文献列表
    """
    with PaperFetcher() as fetcher:
        return fetcher.search_papers(query, limit, source)


def quick_download(papers: list[dict], output_dir: str = "data/pdfs") -> dict:
    """
    快速下载 PDF

    Args:
        papers: 论文列表（需要包含 pmcid）
        output_dir: 输出目录

    Returns:
        下载结果统计
    """
    with PaperFetcher(output_dir=output_dir) as fetcher:
        return fetcher.download_pdfs(papers)
