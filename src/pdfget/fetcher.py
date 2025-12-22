#!/usr/bin/env python3
"""
简化版文献获取器 - Linus风格
只做一件事：下载开放获取文献
遵循KISS原则：Keep It Simple, Stupid
"""

import json
import time
from pathlib import Path
from typing import Any, cast

import requests

from .abstract_supplementor import AbstractSupplementor
from .base.ncbi_base import NCBIBaseModule
from .config import (
    DEFAULT_SOURCE,
    NCBI_API_KEY,
    NCBI_EMAIL,
    SOURCES,
)
from .doi_converter import DOIConverter
from .downloader import PDFDownloader
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher
from .utils.cache_manager import CacheManager
from .utils.error_handling import handle_ncbi_errors


class PaperFetcher(NCBIBaseModule):
    """简单文献获取器"""

    def __init__(
        self,
        cache_dir: str = "data/cache",
        output_dir: str = "data/pdfs",
        default_source: str | None = None,
        sources: "list[str] | None" = None,
        email: str = "",
        api_key: str = "",
    ):
        """
        初始化获取器

        Args:
            cache_dir: 缓存目录
            output_dir: PDF输出目录
            default_source: 默认数据源 (pubmed, europe_pmc)
            sources: 支持的数据源列表
            email: NCBI邮箱
            api_key: NCBI API密钥
        """
        # 使用配置中的默认值或传入的参数
        email = email or NCBI_EMAIL
        api_key = api_key or NCBI_API_KEY

        # 初始化NCBI基类
        super().__init__(session=requests.Session(), email=email, api_key=api_key)

        # 设置获取器特有属性
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)
        self.default_source = default_source or DEFAULT_SOURCE
        self.sources = sources or SOURCES

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

    def _normalize_pmcid(self, pmcid: str) -> str:
        """
        标准化 PMCID 格式

        Args:
            pmcid: 原始 PMCID

        Returns:
            标准化的 PMCID（PMC前缀+数字），空字符串表示无效
        """
        from .utils.identifier_utils import IdentifierUtils

        normalized = IdentifierUtils.normalize_pmcid(pmcid)
        return f"PMC{normalized}" if normalized else ""

    def _detect_id_type(self, identifier: str) -> str:
        """
        自动检测标识符类型

        Args:
            identifier: 标识符字符串

        Returns:
            标识符类型: 'pmcid', 'pmid', 'doi', 'unknown'
        """
        from .utils.identifier_utils import IdentifierUtils

        return IdentifierUtils.detect_identifier_type(identifier)

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
                'dois': [DOI列表]
            }
        """
        import csv
        import os

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        identifiers: dict[str, list[str]] = {"pmcids": [], "pmids": [], "dois": []}

        with open(csv_path, encoding="utf-8") as f:
            csv_reader = csv.reader(f)

            # 读取第一行作为表头
            header = next(csv_reader, None)
            if header is None:
                return identifiers

            # 查找标识符列的索引
            id_col_index = 0  # 默认第一列
            if header:
                for i, col in enumerate(header):
                    if col.strip().lower() == id_column.lower():
                        id_col_index = i
                        break

            # 读取数据行
            for row in csv_reader:
                if not row:  # 跳过空行
                    continue

                if id_col_index < len(row):
                    identifier = row[id_col_index].strip()

                    if not identifier:  # 跳过空标识符
                        continue

                    # 检测标识符类型并分类
                    id_type = self._detect_id_type(identifier)

                    if id_type == "pmcid":
                        # 标准化 PMCID 格式
                        normalized = self._normalize_pmcid(identifier)
                        if normalized:
                            identifiers["pmcids"].append(normalized)
                    elif id_type == "pmid":
                        identifiers["pmids"].append(identifier)
                    elif id_type == "doi":
                        identifiers["dois"].append(identifier)
                    # 忽略 'unknown' 类型

        self.logger.info(
            f"从 CSV 读取标识符: PMCID={len(identifiers['pmcids'])}, "
            f"PMID={len(identifiers['pmids'])}, DOI={len(identifiers['dois'])}"
        )

        return identifiers

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
        import csv
        import os

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")

        pmcid_list = []

        with open(csv_path, encoding="utf-8") as f:
            csv_reader = csv.reader(f)

            # 读取第一行作为表头
            header = next(csv_reader, None)

            # 如果没有表头，假设第一列就是PMCID
            if header is None:
                return []

            # 查找PMCID列的索引
            pmcid_col_index = 0  # 默认第一列
            if header:
                # 尝试查找列名
                for i, col in enumerate(header):
                    if col.strip().lower() == pmcid_column.lower():
                        pmcid_col_index = i
                        break

            # 读取数据行
            for row in csv_reader:
                if not row:  # 空行
                    continue

                if pmcid_col_index < len(row):
                    # 尝试标准化 PMCID
                    pmcid = self._normalize_pmcid(row[pmcid_col_index])
                    if pmcid:
                        pmcid_list.append(pmcid)

        return pmcid_list

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
        # 1. 读取并解析 CSV 文件
        pmcid_list = self._read_pmcid_from_csv(csv_path, pmcid_column)

        # 2. 转换为标准论文格式
        papers = [
            {"pmcid": pmcid, "title": f"PMCID: {pmcid}", "source": "direct_pmcid"}
            for pmcid in pmcid_list
        ]

        # 3. 应用 limit 限制
        if limit is not None and limit > 0:
            papers = papers[:limit]

        # 4. 如果没有论文，直接返回空列表
        if not papers:
            return []

        # 5. 使用统一下载管理器下载
        from .manager import UnifiedDownloadManager

        download_manager = UnifiedDownloadManager(fetcher=self, max_workers=max_workers)

        return download_manager.download_batch(papers)

    def _convert_pmids_to_pmcids(self, pmids: list[str]) -> list[str]:
        """
        将 PMID 列表转换为 PMCID 列表

        Args:
            pmids: PMID 列表

        Returns:
            PMCID 列表（只包含成功转换的）
        """
        if not pmids:
            return []

        self.logger.info(f"开始转换 {len(pmids)} 个 PMID 为 PMCID")

        # 构建伪论文列表（只包含 PMID）
        fake_papers = [{"pmid": pmid, "title": f"PMID: {pmid}"} for pmid in pmids]

        # 使用 PMCIDRetriever 批量获取 PMCID
        papers_with_pmcid = self.pmcid_retriever.process_papers(fake_papers)

        # 提取成功获得 PMCID 的记录
        pmcids = []
        for paper in papers_with_pmcid:
            pmcid = paper.get("pmcid", "")
            if pmcid:
                pmcids.append(pmcid)

        success_rate = (len(pmcids) / len(pmids) * 100) if pmids else 0
        self.logger.info(
            f"PMID 转换完成: {len(pmcids)}/{len(pmids)} ({success_rate:.1f}%)"
        )

        return pmcids

    def _convert_dois_to_pmcids(self, dois: list[str]) -> list[str]:
        """
        将 DOI 列表转换为 PMCID 列表

        Args:
            dois: DOI 列表

        Returns:
            PMCID 列表（只包含成功转换的）
        """
        if not dois:
            return []

        self.logger.info(f"开始转换 {len(dois)} 个 DOI 为 PMCID")

        # 使用 DOIConverter 批量转换
        doi_pmcid_mapping = self.doi_converter.batch_doi_to_pmcid(dois)

        # 提取成功获得 PMCID 的记录
        pmcids = []
        for doi, pmcid in doi_pmcid_mapping.items():
            if pmcid:
                pmcids.append(pmcid)
                self.logger.debug(f"DOI转换成功: {doi} -> {pmcid}")
            else:
                self.logger.debug(f"DOI转换失败: {doi}")

        success_rate = (len(pmcids) / len(dois) * 100) if dois else 0
        self.logger.info(
            f"DOI 转换完成: {len(pmcids)}/{len(dois)} ({success_rate:.1f}%)"
        )

        return pmcids

    def download_from_identifiers(
        self,
        csv_path: str,
        id_column: str = "ID",
        limit: int | None = None,
        max_workers: int = 1,
    ) -> list[dict]:
        """
        从 CSV 文件读取混合类型标识符（PMCID/PMID/DOI）并下载 PDF

        Args:
            csv_path: CSV 文件路径
            id_column: 标识符列名（默认 "ID"）
            limit: 限制下载数量
            max_workers: 最大并发数

        Returns:
            下载结果列表
        """
        # 1. 读取并分类标识符
        identifiers = self._read_identifiers_from_csv(csv_path, id_column)

        # 2. 转换 PMID 为 PMCID
        pmcids_from_pmids = []
        if identifiers["pmids"]:
            self.logger.info(f"发现 {len(identifiers['pmids'])} 个 PMID，开始转换...")
            pmcids_from_pmids = self._convert_pmids_to_pmcids(identifiers["pmids"])

        # 3. 合并所有 PMCID
        all_pmcids = identifiers["pmcids"] + pmcids_from_pmids

        # 4. 转换 DOI 为 PMCID
        pmcids_from_dois = []
        if identifiers["dois"]:
            self.logger.info(f"发现 {len(identifiers['dois'])} 个 DOI，开始转换...")
            pmcids_from_dois = self._convert_dois_to_pmcids(identifiers["dois"])

        # 5. 合并所有 PMCID（包括DOI转换得到的）
        all_pmcids = all_pmcids + pmcids_from_dois

        # 6. 构建论文列表
        papers = [
            {"pmcid": pmcid, "title": f"PMCID: {pmcid}", "source": "mixed_identifiers"}
            for pmcid in all_pmcids
        ]

        # 6. 应用 limit 限制
        if limit is not None and limit > 0:
            papers = papers[:limit]

        if not papers:
            self.logger.warning("没有有效的 PMCID 可以下载")
            return []

        self.logger.info(f"准备下载 {len(papers)} 篇文献（PMCID）")

        # 7. 使用统一下载管理器下载
        from .manager import UnifiedDownloadManager

        download_manager = UnifiedDownloadManager(fetcher=self, max_workers=max_workers)

        return download_manager.download_batch(papers)

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
    ) -> list[dict]:
        """
        统一的输入处理入口

        自动判断输入类型并调用相应的处理逻辑

        Args:
            input_value: 输入值（文件路径/标识符/逗号分隔列表）
            column: CSV列名（可选，None时自动检测）
            limit: 下载数量限制
            max_workers: 并发线程数

        Returns:
            下载结果列表
        """
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

            # 使用现有的download_from_identifiers方法
            return self.download_from_identifiers(
                csv_path=input_value,
                id_column=column,
                limit=limit,
                max_workers=max_workers,
            )

        elif input_type in ["single", "multiple"]:
            # 直接输入的标识符
            identifiers = self._parse_identifier_string(input_value)

            if not identifiers:
                raise ValueError(f"未找到有效的标识符: {input_value}")

            self.logger.info(f"检测到 {len(identifiers)} 个标识符")

            # 分类标识符
            classified: dict[str, list[str]] = {"pmcids": [], "pmids": [], "dois": []}

            for identifier in identifiers:
                id_type = self._detect_id_type(identifier)

                if id_type == "pmcid":
                    normalized = self._normalize_pmcid(identifier)
                    if normalized:
                        classified["pmcids"].append(normalized)
                elif id_type == "pmid":
                    classified["pmids"].append(identifier)
                elif id_type == "doi":
                    classified["dois"].append(identifier)

            # 转换PMID为PMCID
            pmcids_from_pmids = []
            if classified["pmids"]:
                pmcids_from_pmids = self._convert_pmids_to_pmcids(classified["pmids"])

            # 处理DOI转换
            pmcids_from_dois = []
            if classified["dois"]:
                self.logger.info(f"开始转换 {len(classified['dois'])} 个DOI到PMCID")
                pmcids_from_dois = self._convert_dois_to_pmcids(classified["dois"])

            # 合并所有PMCID
            all_pmcids = classified["pmcids"] + pmcids_from_pmids + pmcids_from_dois

            if not all_pmcids:
                self.logger.warning("没有找到可下载的PMCID")
                return []

            # 构建论文列表
            papers = [
                {"pmcid": pmcid, "title": f"PMCID: {pmcid}"} for pmcid in all_pmcids
            ]

            # 应用限制
            if limit:
                papers = papers[:limit]

            # 下载
            from .manager import UnifiedDownloadManager

            download_manager = UnifiedDownloadManager(
                fetcher=self, max_workers=max_workers
            )
            return download_manager.download_batch(papers)

        else:
            raise ValueError(f"未知的输入类型: {input_type}")

    def __enter__(self) -> "PaperFetcher":
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
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
