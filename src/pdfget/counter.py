#!/usr/bin/env python3
"""PMCID统计器 - 并行统计开放获取文献数量"""

import hashlib
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

from . import config
from .config import (
    AVG_PDF_SIZE_MB,
    COUNT_BATCH_SIZE,
    COUNT_MAX_WORKERS,
    NCBI_API_KEY,
    NCBI_EMAIL,
    PUBMED_MAX_RESULTS,
    get_cache_dir,
)
from .logger import get_logger
from .retry import retry_with_backoff


class PMCIDCounter:
    """PMCID统计器"""

    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        cache_dir: str | None = None,
        source: str = "pubmed",
        fetcher: Any = None,
    ) -> None:
        """初始化计数器

        Args:
            email: NCBI API邮箱（可选）
            api_key: NCBI API密钥（可选）
            cache_dir: 缓存目录（可选，默认使用 get_cache_dir()）
            source: 数据源（"pubmed" 或 "europe_pmc"）
            fetcher: PaperFetcher实例（可选）
        """
        self.email = email or NCBI_EMAIL
        self.api_key = api_key or NCBI_API_KEY
        self.source = source
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        # 使用传入的cache_dir或 get_cache_dir()
        self.cache_dir = Path(cache_dir) if cache_dir else get_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 如果提供了fetcher，直接使用；否则创建新的
        if fetcher:
            self.fetcher = fetcher
        else:
            from .fetcher import PaperFetcher

            self.fetcher = PaperFetcher(
                default_source=source,
                cache_dir=str(self.cache_dir),
                email=self.email,
                api_key=self.api_key,
            )

        # 设置请求头
        self.session.headers.update(config.HEADERS)

        # NCBI API基础URL
        self.ncbi_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def _fetch_batch_pmcid(
        self, batch_pmids: list[str], batch_num: int, total_batches: int
    ) -> tuple[int, int]:
        """获取一批PMIDs中是否有PMCID的统计（带重试）

        Args:
            batch_pmids: PMIDs列表
            batch_num: 批次号
            total_batches: 总批次数

        Returns:
            (有PMCID的文献数, 总文献数)
        """
        fetch_url = f"{self.ncbi_base_url}efetch.fcgi"

        params = {
            "db": "pubmed",
            "id": ",".join(batch_pmids),
            "retmode": "xml",
            "rettype": "full",
        }

        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        # 随机延迟，避免所有线程同时请求
        time.sleep(random.uniform(0.05, 0.15))

        # 使用重试机制（使用默认的5次重试和固定等待时间梯度）
        @retry_with_backoff()
        def _fetch() -> str:
            response = self.session.get(
                fetch_url, params=params, timeout=config.TIMEOUT
            )
            response.raise_for_status()
            return response.text

        try:
            xml = _fetch()

            # 按 PubmedArticle 分割
            article_pattern = r"<PubmedArticle>(.*?)</PubmedArticle>"
            articles = re.findall(article_pattern, xml, re.DOTALL)

            # 统计这批中有多少文章有PMCID
            batch_with_pmcid = sum(
                1 for article in articles if '<ArticleId IdType="pmc">' in article
            )

            self.logger.debug(
                f"批次 {batch_num:2d}/{total_batches} - 有PMCID: {batch_with_pmcid:3d}/{len(articles):3d}"
            )

            return batch_with_pmcid, len(articles)

        except Exception as e:
            self.logger.warning(
                f"批次 {batch_num:2d}/{total_batches} 重试后仍失败: {str(e)[:50]}..."
            )
            return 0, len(batch_pmids)

    def _get_cache_file(self, query: str, source: str = "pubmed") -> Path:
        """获取缓存文件路径"""
        content = f"{query}:{source}".encode()
        hash_key = hashlib.md5(content).hexdigest()
        return self.cache_dir / f"search_{hash_key}.json"

    def _load_cache(self, query: str) -> list[dict] | None:
        """加载 PaperFetcher 的搜索缓存"""
        # 尝试多个可能的源
        sources = ["pubmed", "europe_pmc"]
        for source in sources:
            cache_file = self._get_cache_file(query, source)
            if cache_file.exists():
                try:
                    with open(cache_file, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list) and data:
                            self.logger.info(f"从 {source} 缓存加载 {len(data)} 条结果")
                            return data
                except Exception as e:
                    self.logger.warning(f"读取缓存失败 {cache_file}: {str(e)}")

        return None

    def _statistics_from_cache(self, papers: list[dict]) -> dict:
        """从缓存的文献列表生成统计信息"""
        total = len(papers)
        with_pmcid = sum(1 for p in papers if p.get("pmcid"))
        without_pmcid = total - with_pmcid
        rate = (with_pmcid / total) * 100 if total > 0 else 0

        # 估算总文献数（如果有更多信息，可以使用）
        total_available = total  # 简化处理，实际可以从搜索API获取

        return {
            "query": getattr(self, "_current_query", ""),
            "total": total_available,
            "checked": total,
            "with_pmcid": with_pmcid,
            "without_pmcid": without_pmcid,
            "rate": rate,
            "estimated_size_mb": with_pmcid * AVG_PDF_SIZE_MB,
            "elapsed_seconds": 0,  # 从缓存加载，耗时为0
            "processing_speed": 0.0,  # 从缓存加载，速度设为0
            "from_cache": True,
        }

    def _rate_limit(self) -> None:
        """PubMed API速率限制"""
        # 免费用户：3请求/秒
        # 有API密钥：10请求/秒
        if self.api_key:
            time.sleep(0.1)  # 10请求/秒
        else:
            time.sleep(0.34)  # 约3请求/秒

    def count_pmcid(
        self,
        query: str,
        limit: int = 5000,
        use_cache: bool = True,
        trigger_search: bool = True,
        source: str | None = None,
    ) -> dict:
        """统计查询结果中有PMCID的文献数量

        Args:
            query: 搜索查询
            limit: 最大结果数
            use_cache: 是否使用缓存
            trigger_search: 如果没有缓存是否触发搜索创建缓存
            source: 数据源（"pubmed" 或 "europe_pmc"），覆盖初始化时的设置

        Returns:
            统计结果字典
        """
        # 使用传入的 source 或初始化时的 source
        actual_source = source or self.source

        self.logger.info(f"🔍 统计PMCID: {query} (数据源: {actual_source})")
        self._current_query = query

        # 对于 Europe PMC，直接使用搜索结果中的 PMCID
        if actual_source == "europe_pmc":
            return self._count_pmcid_from_europe_pmc(query, limit)

        # 1. 首先检查缓存
        if use_cache:
            cached_papers = self._load_cache(query)
            if cached_papers:
                self.logger.info("✅ 使用缓存数据生成统计")
                return self._statistics_from_cache(cached_papers)

        # 2. 如果没有缓存且不触发搜索，只做基本统计
        if not trigger_search:
            self.logger.info("📊 执行基本统计（不创建缓存）")
            return self._count_without_cache(query, limit)

        # 3. 触发搜索以创建缓存
        self.logger.info("📥 无缓存，触发搜索以生成缓存...")
        try:
            # 动态导入避免循环依赖
            from .fetcher import PaperFetcher

            fetcher = PaperFetcher(
                cache_dir=str(self.cache_dir), default_source="pubmed"
            )

            # 搜索并缓存结果
            papers = fetcher.search_papers(query, limit=limit, fetch_pmcid=True)

            if papers:
                self.logger.info(f"✅ 搜索并缓存了 {len(papers)} 篇文献")
                return self._statistics_from_cache(papers)
            else:
                self.logger.warning("⚠ 未找到文献")
                return self._count_without_cache(query, limit)

        except Exception as e:
            self.logger.error(f"触发搜索失败: {str(e)}")
            self.logger.info("📊 回退到基本统计模式")
            return self._count_without_cache(query, limit)

    def _count_without_cache(self, query: str, limit: int = 5000) -> dict:
        """不使用缓存的原始统计方法（原有逻辑）"""
        # 1. 获取PMID列表
        search_url = f"{self.ncbi_base_url}esearch.fcgi"
        search_params: dict[str, str | int] = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": min(limit, PUBMED_MAX_RESULTS),  # PubMed单次最多返回10000条
        }

        if self.email:
            search_params["email"] = self.email
        if self.api_key:
            search_params["api_key"] = self.api_key

        response = self.session.get(
            search_url,
            params=search_params,
            timeout=float(config.TIMEOUT),
        )
        response.raise_for_status()

        search_data = response.json()
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        total_available = int(search_data.get("esearchresult", {}).get("count", 0))

        self.logger.info(f"📊 总文献数: {total_available}")
        self.logger.info(f"   获取的PMID数: {len(pmids)}")

        if not pmids:
            return {
                "query": query,
                "total": 0,
                "checked": 0,
                "with_pmcid": 0,
                "without_pmcid": 0,
                "rate": 0.0,
                "estimated_size_mb": 0,
                "elapsed_seconds": 0,
            }

        # 2. 分批并行处理
        batch_size = COUNT_BATCH_SIZE
        max_workers = COUNT_MAX_WORKERS
        batches = [pmids[i : i + batch_size] for i in range(0, len(pmids), batch_size)]

        self.logger.info(
            f"🚀 使用并行处理，共 {len(batches)} 批，每批 {batch_size} 个PMID"
        )
        self.logger.info(f"   使用 {max_workers} 个线程并行处理")

        start_time = time.time()
        total_with_pmcid = 0
        total_checked = 0

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_batch = {
                executor.submit(self._fetch_batch_pmcid, batch, i + 1, len(batches)): i
                + 1
                for i, batch in enumerate(batches)
            }

            # 收集结果
            for future in as_completed(future_to_batch):
                batch_num = future_to_batch[future]
                try:
                    batch_count, batch_articles = future.result()
                    total_with_pmcid += batch_count
                    total_checked += batch_articles
                except Exception as e:
                    self.logger.error(f"批次 {batch_num} 处理异常: {e}")

        elapsed = time.time() - start_time

        # 3. 计算结果
        rate = (total_with_pmcid / total_checked) * 100 if total_checked > 0 else 0
        avg_pdf_size = AVG_PDF_SIZE_MB  # MB
        estimated_size_mb = total_with_pmcid * avg_pdf_size

        # 返回统计信息
        return {
            "query": query,
            "total": total_available,
            "checked": total_checked,
            "with_pmcid": total_with_pmcid,
            "without_pmcid": total_checked - total_with_pmcid,
            "rate": rate,
            "estimated_size_mb": estimated_size_mb,
            "elapsed_seconds": elapsed,
            "processing_speed": total_checked / elapsed if elapsed > 0 else 0,
        }

    def _count_pmcid_from_europe_pmc(self, query: str, limit: int) -> dict:
        """从 Europe PMC 搜索结果统计 PMCID"""
        start_time = time.time()

        # 直接使用 fetcher 搜索（已经包含 PMCID）
        papers = self.fetcher.search_papers(
            query,
            limit=limit,
            source="europe_pmc",
            use_cache=True,
            fetch_pmcid=False,  # 不需要额外获取 PMCID
        )

        # 统计 PMCID
        with_pmcid = sum(1 for p in papers if p.get("pmcid"))
        without_pmcid = len(papers) - with_pmcid

        elapsed = time.time() - start_time

        self.logger.info("📊 Europe PMC 统计完成:")
        self.logger.info(f"   获取文献: {len(papers)} 篇")
        self.logger.info(f"   有PMCID: {with_pmcid} 篇")
        self.logger.info(f"   无PMCID: {without_pmcid} 篇")
        pmcid_rate = (with_pmcid / len(papers) * 100) if papers else 0
        self.logger.info(f"   PMCID率: {pmcid_rate:.1f}%")
        self.logger.info(f"   耗时: {elapsed:.1f} 秒")

        # 返回统计信息
        return {
            "query": query,
            "total": len(papers),  # Europe PMC 不返回总数，只返回实际获取的数量
            "checked": len(papers),
            "with_pmcid": with_pmcid,
            "without_pmcid": without_pmcid,
            "rate": (with_pmcid / len(papers) * 100) if papers else 0,
            "estimated_size_mb": with_pmcid * AVG_PDF_SIZE_MB,
            "elapsed_seconds": elapsed,
            "processing_speed": len(papers) / elapsed if elapsed > 0 else 0,
        }
