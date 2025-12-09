#!/usr/bin/env python3
"""PMCID统计器 - 并行统计开放获取文献数量"""

import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from . import config
from .config import AVG_PDF_SIZE_MB, PUBMED_MAX_RESULTS
from .logger import get_logger


class PMCIDCounter:
    """PMCID统计器"""

    def __init__(self, email: str | None = None, api_key: str | None = None):
        """初始化计数器

        Args:
            email: NCBI API邮箱（可选）
            api_key: NCBI API密钥（可选）
        """
        self.email = email
        self.api_key = api_key
        self.logger = get_logger(__name__)
        self.session = requests.Session()

        # 设置请求头
        self.session.headers.update(config.HEADERS)

        # NCBI API基础URL
        self.ncbi_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def _fetch_batch_pmcid(
        self, batch_pmids: list[str], batch_num: int, total_batches: int
    ) -> tuple[int, int]:
        """获取一批PMIDs中是否有PMCID的统计

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

        try:
            response = self.session.get(
                fetch_url, params=params, timeout=config.TIMEOUT
            )
            response.raise_for_status()
            xml = response.text

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
                f"批次 {batch_num:2d}/{total_batches} 错误: {str(e)[:50]}..."
            )
            return 0, len(batch_pmids)

    def _rate_limit(self) -> None:
        """PubMed API速率限制"""
        # 免费用户：3请求/秒
        # 有API密钥：10请求/秒
        if self.api_key:
            time.sleep(0.1)  # 10请求/秒
        else:
            time.sleep(0.34)  # 约3请求/秒

    def count_pmcid(self, query: str, limit: int = 5000) -> dict:
        """统计查询结果中有PMCID的文献数量

        Args:
            query: 搜索查询
            limit: 最大结果数

        Returns:
            统计结果字典
        """
        self.logger.info(f"🔍 统计PMCID: {query}")

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
            timeout=config.TIMEOUT,  # type: ignore[arg-type]
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
        batch_size = config.COUNT_BATCH_SIZE
        max_workers = config.COUNT_MAX_WORKERS
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
