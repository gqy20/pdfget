#!/usr/bin/env python3
"""
简化版文献获取器 - Linus风格
只做一件事：下载开放获取文献
遵循KISS原则：Keep It Simple, Stupid
"""

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
    DOWNLOAD_BASE_DELAY,
    NCBI_API_KEY,
    NCBI_EMAIL,
    get_cache_dir,
)
from .doi_converter import DOIConverter
from .download_plan import DownloadPlan, build_download_plan, ready_papers
from .downloader import PDFDownloader
from .paper_schema import normalize_paper_record
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher
from .utils.cache_manager import CacheManager
from .utils.error_handling import handle_ncbi_errors
from .utils.identifier_utils import IdentifierUtils


class PaperFetcher(NCBIBaseModule):
    """简单文献获取器"""

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
        self.pdf_downloader = PDFDownloader(str(self.output_dir), self.session)
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
                return cached_papers  # type: ignore[no-any-return]

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
        search_cache = self.cache_manager.get_cache_info()

        return {
            "search_cache_count": search_cache["count"],
            "search_cache_size_bytes": search_cache["size_bytes"],
            "search_cache_size_mb": search_cache["size_mb"],
            "search_cache_dir": search_cache["directory"],
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
            self.cache_manager.clear()

        if pdf_cache:
            deleted_count = self.pdf_downloader.cleanup_old_pdfs(max_age_days=0)
            self.logger.info(f"清理了 {deleted_count} 个 PDF 文件")

    def _read_identifiers_from_csv(
        self, csv_path: str, id_column: str = "ID"
    ) -> dict[str, list[str]]:
        """
        从 CSV 文件读取混合类型的标识符列表

        Args:
            csv_path: CSV 文件路径
            id_column: 标识符列名

        Returns:
            字典，包含分类后的标识符:
            {
                'pmcids': [PMCID列表],
                'pmids': [PMID列表],
                'dois': [DOI列表],
                'arxiv_ids': [arXiv ID 列表]
            }
        """
        identifiers: dict[str, list[str]] = {
            "pmcids": [],
            "pmids": [],
            "dois": [],
            "arxiv_ids": [],
        }

        for identifier in self._read_identifier_values_from_csv(csv_path, id_column):
            id_type = IdentifierUtils.detect_identifier_type(identifier)
            if id_type == "pmcid":
                normalized_pmcid = IdentifierUtils.format_pmcid(identifier)
                if normalized_pmcid:
                    identifiers["pmcids"].append(normalized_pmcid)
            elif id_type == "pmid":
                identifiers["pmids"].append(identifier)
            elif id_type == "doi":
                identifiers["dois"].append(identifier)
            elif id_type == "arxiv":
                normalized_arxiv_id = IdentifierUtils.normalize_arxiv_id(identifier)
                if normalized_arxiv_id:
                    identifiers["arxiv_ids"].append(normalized_arxiv_id)

        self.logger.info(
            f"从 CSV 读取标识符: PMCID={len(identifiers['pmcids'])}, "
            f"PMID={len(identifiers['pmids'])}, DOI={len(identifiers['dois'])}, "
            f"arXiv={len(identifiers['arxiv_ids'])}"
        )

        return identifiers

    def _read_identifier_values_from_csv(
        self, csv_path: str, id_column: str = "ID"
    ) -> list[str]:
        """Read raw identifier values from a CSV column while preserving row order."""
        import csv
        import os

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        values: list[str] = []
        with open(csv_path, encoding="utf-8") as f:
            csv_reader = csv.reader(f)
            header = next(csv_reader, None)
            if header is None:
                return values

            id_col_index = 0
            for i, col in enumerate(header):
                if col.strip().lower() == id_column.lower():
                    id_col_index = i
                    break

            for row in csv_reader:
                if not row or id_col_index >= len(row):
                    continue
                identifier = row[id_col_index].strip()
                if identifier:
                    values.append(identifier)

        return values

    def _read_pmcid_from_csv(
        self, csv_path: str, pmcid_column: str = "PMCID"
    ) -> list[str]:
        """
        从 CSV 文件读取 PMCID 列表

        Args:
            csv_path: CSV 文件路径
            pmcid_column: PMCID 列名（默认 "PMCID"）

        Returns:
            有效的 PMCID 列表
        """
        pmcids = []
        for identifier in self._read_identifier_values_from_csv(csv_path, pmcid_column):
            pmcid = IdentifierUtils.format_pmcid(identifier)
            if pmcid:
                pmcids.append(pmcid)
        return pmcids

    def download_from_pmcid_csv(
        self,
        csv_path: str,
        limit: int | None = None,
        max_workers: int = 1,
        pmcid_column: str = "PMCID",
    ) -> list[dict]:
        """
        从 CSV 文件读取 PMCID 列表并下载 PDF

        Args:
            csv_path: CSV 文件路径
            limit: 限制下载数量
            max_workers: 最大并发数
            pmcid_column: PMCID 列名（默认 "PMCID"）

        Returns:
            下载结果列表
        """
        pmcid_list = self._read_pmcid_from_csv(csv_path, pmcid_column)
        papers = self._build_papers_from_identifiers_in_order(pmcid_list)

        if limit is not None and limit > 0:
            papers = papers[:limit]

        if not papers:
            return []

        from .manager import UnifiedDownloadManager

        download_manager = UnifiedDownloadManager(
            fetcher=self,
            max_workers=max_workers,
        )
        return download_manager.download_batch(papers)

    def _convert_pmids_to_pmcids(self, pmids: list[str]) -> list[str]:
        """
        将 PMID 列表转换为 PMCID 列表

        Args:
            pmids: PMID 列表

        Returns:
            PMCID 列表（只包含成功转换的）
        """
        mapping = self._convert_pmids_to_pmcid_mapping(pmids)
        return [mapping[pmid] for pmid in pmids if pmid in mapping]

    def _convert_dois_to_pmcids(self, dois: list[str]) -> list[str]:
        """
        将 DOI 列表转换为 PMCID 列表

        Args:
            dois: DOI 列表

        Returns:
            PMCID 列表（只包含成功转换的）
        """
        mapping = self._convert_dois_to_pmcid_mapping(dois)
        return [mapping[doi] for doi in dois if doi in mapping]

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

    def _build_papers_from_identifiers_in_order(
        self, identifiers: list[str]
    ) -> list[dict]:
        """Build downloadable paper records in the same order as user input."""
        entries: list[tuple[str, str]] = []
        pmids: list[str] = []
        dois: list[str] = []

        for identifier in identifiers:
            id_type = IdentifierUtils.detect_identifier_type(identifier)
            if id_type == "pmcid":
                normalized_pmcid = IdentifierUtils.format_pmcid(identifier)
                if normalized_pmcid:
                    entries.append(("pmcid", normalized_pmcid))
            elif id_type == "pmid":
                entries.append(("pmid", identifier))
                pmids.append(identifier)
            elif id_type == "doi":
                entries.append(("doi", identifier))
                dois.append(identifier)
            elif id_type == "arxiv":
                normalized_arxiv_id = IdentifierUtils.normalize_arxiv_id(identifier)
                if normalized_arxiv_id:
                    entries.append(("arxiv", normalized_arxiv_id))

        pmid_to_pmcid = self._convert_pmids_to_pmcid_mapping(pmids)
        doi_to_pmcid = self._convert_dois_to_pmcid_mapping(dois)

        papers: list[dict] = []
        for id_type, value in entries:
            if id_type == "pmcid":
                papers.append(
                    normalize_paper_record(
                        {
                            "pmcid": value,
                            "title": f"PMCID: {value}",
                            "source": "direct_pmcid",
                        },
                        "direct_pmcid",
                        matched_by="pmcid",
                    )
                )
            elif id_type == "pmid":
                pmcid = pmid_to_pmcid.get(value)
                if pmcid:
                    papers.append(
                        normalize_paper_record(
                            {
                                "pmid": value,
                                "pmcid": pmcid,
                                "title": f"PMID: {value}",
                                "source": "mixed_identifiers",
                            },
                            "mixed_identifiers",
                            matched_by="pmid",
                        )
                    )
            elif id_type == "doi":
                pmcid = doi_to_pmcid.get(value)
                if pmcid:
                    papers.append(
                        normalize_paper_record(
                            {
                                "doi": value,
                                "pmcid": pmcid,
                                "title": f"DOI: {value}",
                                "source": "mixed_identifiers",
                            },
                            "mixed_identifiers",
                            matched_by="doi",
                        )
                    )
            elif id_type == "arxiv":
                papers.append(
                    normalize_paper_record(
                        {
                            "arxiv_id": value,
                            "title": f"arXiv: {value}",
                            "source": "direct_arxiv",
                        },
                        "direct_arxiv",
                        matched_by="arxiv_id",
                    )
                )

        return papers

    def download_from_identifiers(
        self,
        csv_path: str,
        id_column: str = "ID",
        limit: int | None = None,
        max_workers: int = 1,
        base_delay: float | None = None,
    ) -> list[dict]:
        """
        从 CSV 文件读取混合类型标识符（PMCID/PMID/DOI）并下载 PDF

        Args:
            csv_path: CSV 文件路径
            id_column: 标识符列名（默认 "ID"）
            limit: 限制下载数量
            max_workers: 最大并发数
            base_delay: 基础延迟时间（秒，None时使用默认值）

        Returns:
            下载结果列表
        """
        identifiers = self._read_identifier_values_from_csv(csv_path, id_column)
        papers = self._build_papers_from_identifiers_in_order(identifiers)

        if limit is not None and limit > 0:
            papers = papers[:limit]

        if not papers:
            self.logger.warning("没有有效的标识符可以下载")
            return []

        self.logger.info(f"准备下载 {len(papers)} 篇文献")

        # 7. 使用统一下载管理器下载
        from .manager import UnifiedDownloadManager

        download_manager = UnifiedDownloadManager(
            fetcher=self,
            max_workers=max_workers,
            base_delay=base_delay if base_delay is not None else DOWNLOAD_BASE_DELAY,
        )

        return download_manager.download_batch(papers)

    def export_results(
        self,
        papers: list[dict],
        format_type: str = "json",
        filename: "str | None" = None,
        **kwargs: str,
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
        if "format" in kwargs:
            format_type = kwargs.pop("format")
        if kwargs:
            unexpected = ", ".join(kwargs)
            raise TypeError(f"不支持的参数: {unexpected}")

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

    def _detect_input_type(self, input_str: str) -> str:
        """
        检测输入类型

        Args:
            input_str: 输入字符串

        Returns:
            'csv_file': CSV文件路径
            'single': 单个标识符
            'multiple': 多个标识符（逗号分隔）
            'invalid': 无效输入
        """
        import os

        # 检查空输入
        if not input_str or not input_str.strip():
            return "invalid"

        input_str = input_str.strip()

        # 检查是否是文件路径
        if os.path.exists(input_str):
            return "csv_file"

        # 检查是否包含逗号（多个标识符）
        if "," in input_str:
            return "multiple"

        # 单个标识符
        return "single"

    def _auto_detect_column(self, csv_path: str) -> str | None:
        """
        自动检测CSV列名

        优先级: ID > PMCID > doi > pmid > 第一列

        Args:
            csv_path: CSV文件路径

        Returns:
            检测到的列名，如果文件为空返回None
        """
        import csv

        priority_columns = ["ID", "PMCID", "doi", "pmid"]

        try:
            with open(csv_path, encoding="utf-8") as f:
                csv_reader = csv.reader(f)
                header = next(csv_reader, None)

                if header is None or not header:
                    return None

                # 大小写不敏感的列名映射
                header_map = {col.upper(): col for col in header}

                # 按优先级查找
                for priority_col in priority_columns:
                    if priority_col.upper() in header_map:
                        return header_map[priority_col.upper()]

                # 都没找到，返回第一列
                return header[0] if header else None

        except Exception as e:
            self.logger.error(f"自动检测列名失败: {e}")
            return None

    def _parse_identifier_string(self, id_str: str) -> list[str]:
        """
        解析标识符字符串

        支持：
        - 单个: "PMC123456"
        - 多个: "PMC123456,38238491,10.1038/xxx"

        Args:
            id_str: 标识符字符串

        Returns:
            标识符列表
        """
        if not id_str or not id_str.strip():
            return []

        # 按逗号分隔
        identifiers = [s.strip() for s in id_str.split(",")]

        # 过滤掉空字符串
        identifiers = [s for s in identifiers if s]

        return identifiers

    def download_from_unified_input(
        self,
        input_value: str,
        column: str | None = None,
        limit: int | None = None,
        max_workers: int = 1,
        base_delay: float | None = None,
    ) -> list[dict]:
        """
        统一的输入处理入口

        自动判断输入类型并调用相应的处理逻辑

        Args:
            input_value: 输入值（文件路径/标识符/逗号分隔列表）
            column: CSV列名（可选，None时自动检测）
            limit: 下载数量限制
            max_workers: 并发线程数
            base_delay: 基础延迟时间（秒，None时使用默认值）

        Returns:
            下载结果列表
        """
        plan = self.build_download_plan_from_unified_input(
            input_value=input_value,
            column=column,
            limit=limit,
        )
        papers = ready_papers(plan)
        if not papers:
            self.logger.warning("没有找到可下载的标识符")
            return []

        from .manager import UnifiedDownloadManager

        download_manager = UnifiedDownloadManager(
            fetcher=self,
            max_workers=max_workers,
            base_delay=base_delay if base_delay is not None else DOWNLOAD_BASE_DELAY,
        )
        return download_manager.download_batch(papers)

    def build_download_plan_from_unified_input(
        self,
        input_value: str,
        column: str | None = None,
        limit: int | None = None,
    ) -> DownloadPlan:
        """Build a download plan from a CSV path or identifier string."""
        # 检测输入类型
        input_type = self._detect_input_type(input_value)

        if input_type == "invalid":
            raise ValueError(f"无效的输入: {input_value}")

        if input_type == "csv_file":
            # CSV文件输入
            self.logger.info(f"检测到CSV文件输入: {input_value}")

            # 如果未指定列名，自动检测
            if column is None:
                detected_column = self._auto_detect_column(input_value)
                if detected_column:
                    self.logger.info(f"自动检测到列名: {detected_column}")
                    column = detected_column
                else:
                    raise ValueError(f"无法自动检测CSV列名: {input_value}")

            identifiers = self._read_identifier_values_from_csv(input_value, column)
            papers = self._build_papers_from_identifiers_in_order(identifiers)
            if limit is not None and limit > 0:
                papers = papers[:limit]
            return build_download_plan(papers, source="unified_input")

        elif input_type in ["single", "multiple"]:
            # 直接输入的标识符
            identifiers = self._parse_identifier_string(input_value)

            if not identifiers:
                raise ValueError(f"未找到有效的标识符: {input_value}")

            self.logger.info(f"检测到 {len(identifiers)} 个标识符")
            papers = self._build_papers_from_identifiers_in_order(identifiers)

            # 应用限制
            if limit:
                papers = papers[:limit]

            return build_download_plan(papers, source="unified_input")

        else:
            raise ValueError(f"未知的输入类型: {input_type}")

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


# 便捷函数
def quick_search(
    query: str, limit: int = 20, source: str | None = None
) -> list[dict[Any, Any]]:
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
        return cast(
            list[dict[Any, Any]],
            fetcher.search_papers(query, limit, source or DEFAULT_SOURCE),
        )
