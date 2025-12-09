#!/usr/bin/env python3
"""
简化版文献获取器 - Linus风格
只做一件事：下载开放获取文献
遵循KISS原则：Keep It Simple, Stupid
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import DEFAULT_SOURCE, SOURCES
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
        default_source: str | None = None,
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
        self.default_source = default_source or DEFAULT_SOURCE
        self.sources = sources or SOURCES

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
        fetch_pmcid: bool = False,
    ) -> list[dict]:
        """
        搜索文献

        Args:
            query: 检索词
            limit: 返回数量限制
            source: 数据源
            use_cache: 是否使用缓存
            fetch_pmcid: 是否自动获取PMCID

        Returns:
            文献列表
        """
        # 检查缓存
        if use_cache:
            cache_file = self._get_cache_file(query, source or self.default_source)
            cached_papers = self._load_cache(cache_file)
            if cached_papers:
                self.logger.info(f"从缓存加载 {len(cached_papers)} 条结果")
                # 如果需要PMCID且缓存中没有，检查并添加
                if fetch_pmcid and not any(p.get("pmcid") for p in cached_papers):
                    cached_papers = self.add_pmcids(cached_papers)
                    # 更新缓存
                    self._save_cache(cache_file, cached_papers)
                return cached_papers

        # 执行搜索
        papers = self.searcher.search_papers(query, limit, source)

        # 自动获取PMCID（如果需要且是PubMed数据源）
        if (
            fetch_pmcid
            and papers
            and (
                source == "pubmed"
                or (source is None and self.default_source == "pubmed")
            )
        ):
            papers = self.add_pmcids(papers)

        # 保存到缓存（包含PMCID信息）
        if use_cache and papers:
            cache_file = self._get_cache_file(query, source or self.default_source)
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
def quick_search(query: str, limit: int = 20, source: str | None = None) -> list[dict]:
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
        return fetcher.search_papers(query, limit, source or DEFAULT_SOURCE)
