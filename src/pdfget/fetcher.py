#!/usr/bin/env python3
"""Search, metadata enrichment, and identifier resolution facade."""

import json
import time
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import requests

from .abstract_supplementor import AbstractSupplementor
from .base.ncbi_base import NCBIBaseModule
from .config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SOURCE,
    NCBI_API_KEY,
    NCBI_EMAIL,
    get_cache_dir,
)
from .doi_converter import DOIConverter
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher
from .utils.cache_manager import CacheManager
from .utils.error_handling import handle_ncbi_errors


class PaperFetcher(NCBIBaseModule):
    """Coordinate paper search, metadata enrichment, and identifier resolution."""

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        default_source: str | None = None,
        email: str = "",
        api_key: str = "",
    ):
        """
        初始化获取器

        Args:
            cache_dir: 缓存目录
            output_dir: PDF输出目录
            default_source: 默认数据源 (pubmed, europe_pmc)
            email: NCBI邮箱
            api_key: NCBI API密钥
        """
        # 使用配置中的默认值或传入的参数
        email = email or NCBI_EMAIL
        api_key = api_key or NCBI_API_KEY

        # 初始化NCBI基类
        super().__init__(session=requests.Session(), email=email, api_key=api_key)

        # 设置获取器特有属性（缓存目录默认使用 XDG 标准路径）
        self.cache_dir = Path(cache_dir) if cache_dir else get_cache_dir()
        self.output_dir = Path(output_dir)
        self.default_source = default_source or DEFAULT_SOURCE

        # 初始化缓存管理器
        self.cache_manager = CacheManager(cache_dir=self.cache_dir)

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化子模块
        self.searcher = PaperSearcher(
            self.session, email=self.email, api_key=self.api_key
        )
        self.pmcid_retriever = PMCIDRetriever(
            self.session, email=self.email, api_key=self.api_key
        )
        self.doi_converter = DOIConverter(
            self.session, email=self.email, api_key=self.api_key
        )
        self.abstract_supplementor = AbstractSupplementor(timeout=5, delay=0.2)

    def _get_cache_key(self, query: str, source: str) -> str:
        """获取缓存键"""
        return f"search:{source}:{query}"

    @handle_ncbi_errors(default_return=[])
    def search_papers(
        self,
        query: str,
        limit: int = 50,
        source: "str | None" = None,
        use_cache: bool = True,
        fetch_pmcid: bool = False,
    ) -> list[dict[Any, Any]]:
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
        source = source or self.default_source
        cache_key = self._get_cache_key(query, source)

        # 检查缓存
        if use_cache:
            cached_papers = self.cache_manager.get(cache_key, default=[])
            if cached_papers:
                self.logger.info(f"从缓存加载 {len(cached_papers)} 条结果")
                # 如果需要PMCID且缓存中没有，检查并添加
                if fetch_pmcid and not any(p.get("pmcid") for p in cached_papers):
                    cached_papers = self.add_pmcids(cached_papers)
                    # 更新缓存
                    self.cache_manager.set(
                        cache_key, cached_papers, ttl=3600
                    )  # 1小时TTL
                return cast(list[dict[Any, Any]], cached_papers)

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

        # 补充缺失的摘要（MVP版本：仅对Europe PMC数据源）
        if papers and (source == "europe_pmc"):
            self.logger.info("开始补充缺失的摘要...")
            original_abstract_count = sum(1 for p in papers if p.get("abstract"))
            papers = self.abstract_supplementor.supplement_abstracts_batch(papers)
            supplemented_count = (
                sum(1 for p in papers if p.get("abstract")) - original_abstract_count
            )
            if supplemented_count > 0:
                self.logger.info(f"成功补充 {supplemented_count} 个摘要")

        # 保存到缓存（包含PMCID和摘要信息）
        if use_cache and papers:
            self.cache_manager.set(cache_key, papers, ttl=3600)  # 1小时TTL

        return cast(list[dict[Any, Any]], papers)

    def add_pmcids(
        self, papers: list[dict], use_fallback: bool | None = None
    ) -> list[dict]:
        """
        批量添加 PMCID

        Args:
            papers: 论文列表
            use_fallback: 是否使用逐个获取作为备选
                         如果为None，则使用配置文件中的PMCID_USE_FALLBACK值

        Returns:
            更新后的论文列表
        """
        self.logger.info(f"为 {len(papers)} 篇论文添加 PMCID")
        # 传递None让PMCIDRetriever自己使用配置的默认值
        return self.pmcid_retriever.process_papers(papers, use_fallback)

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        from .storage import LocalPDFStore

        search_cache = self.cache_manager.get_cache_info()

        return {
            "search_cache_count": search_cache["count"],
            "search_cache_size_bytes": search_cache["size_bytes"],
            "search_cache_size_mb": search_cache["size_mb"],
            "search_cache_dir": search_cache["directory"],
            "pdf_cache": LocalPDFStore(self.output_dir).cache_info(),
        }

    def clear_cache(self, search_cache: bool = True, pdf_cache: bool = False) -> None:
        """
        清理缓存

        Args:
            search_cache: 是否清理搜索缓存
            pdf_cache: 是否清理 PDF 缓存
        """
        if search_cache:
            self.cache_manager.clear()

        if pdf_cache:
            from .storage import LocalPDFStore

            deleted_count = LocalPDFStore(self.output_dir).cleanup_older_than(max_age_days=0)
            self.logger.info(f"清理了 {deleted_count} 个 PDF 文件")

    def _convert_pmids_to_pmcid_mapping(self, pmids: list[str]) -> dict[str, str]:
        """Convert PMIDs to a PMID -> PMCID mapping while preserving lookup identity."""
        if not pmids:
            return {}

        self.logger.info(f"开始转换 {len(pmids)} 个 PMID 为 PMCID")
        fake_papers = [{"pmid": pmid, "title": f"PMID: {pmid}"} for pmid in pmids]
        papers_with_pmcid = self.pmcid_retriever.process_papers(fake_papers)

        mapping: dict[str, str] = {}
        for paper in papers_with_pmcid:
            pmid = str(paper.get("pmid") or "")
            pmcid = str(paper.get("pmcid") or "")
            if pmid and pmcid:
                mapping[pmid] = pmcid

        success_rate = (len(mapping) / len(pmids) * 100) if pmids else 0
        self.logger.info(
            f"PMID 转换完成: {len(mapping)}/{len(pmids)} ({success_rate:.1f}%)"
        )
        return mapping

    def _convert_dois_to_pmcid_mapping(self, dois: list[str]) -> dict[str, str]:
        """Convert DOIs to a DOI -> PMCID mapping."""
        if not dois:
            return {}

        self.logger.info(f"开始转换 {len(dois)} 个 DOI 为 PMCID")
        doi_pmcid_mapping = self.doi_converter.batch_doi_to_pmcid(dois)

        mapping: dict[str, str] = {}
        for doi, pmcid in doi_pmcid_mapping.items():
            if pmcid:
                mapping[doi] = pmcid
                self.logger.debug(f"DOI转换成功: {doi} -> {pmcid}")
            else:
                self.logger.debug(f"DOI转换失败: {doi}")

        success_rate = (len(mapping) / len(dois) * 100) if dois else 0
        self.logger.info(
            f"DOI 转换完成: {len(mapping)}/{len(dois)} ({success_rate:.1f}%)"
        )
        return mapping

    def resolve_pmids(self, pmids: list[str]) -> dict[str, str]:
        """Resolve PMIDs to PMCIDs for download planning."""
        return self._convert_pmids_to_pmcid_mapping(pmids)

    def resolve_dois(self, dois: list[str]) -> dict[str, str]:
        """Resolve DOIs to PMCIDs for download planning."""
        return self._convert_dois_to_pmcid_mapping(dois)

    def export_results(
        self,
        papers: list[dict],
        format_type: str = "json",
        filename: "str | None" = None,
    ) -> str:
        """
        导出搜索结果

        Args:
            papers: 论文列表
            format_type: 导出格式 (json, csv, tsv)
            filename: 输出文件名（可选）

        Returns:
            输出文件路径
        """
        format_type = format_type.lower()
        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"papers_{timestamp}.{format_type}"

        output_path = self.cache_dir / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format_type == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
        elif format_type in ["csv", "tsv"]:
            import csv

            delimiter = "," if format_type == "csv" else "\t"
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                if papers:
                    writer = csv.DictWriter(
                        f, fieldnames=papers[0].keys(), delimiter=delimiter
                    )
                    writer.writeheader()
                    writer.writerows(papers)
        else:
            raise ValueError(f"不支持的格式: {format_type}")

        self.logger.info(f"结果已导出到: {output_path}")
        return str(output_path)

    def __enter__(self) -> "PaperFetcher":
        """支持上下文管理器"""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """退出时清理资源"""
        self.session.close()
