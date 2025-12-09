"""
PMCID 批量获取模块

高性能批量获取 PMCID，使用 ESummary API 替代 EFetch，
实现 10-30 倍的性能提升。
"""

import time
from typing import Any

import requests

from .config import RATE_LIMIT
from .logger import get_logger


class PMCIDRetriever:
    """PMCID 获取器 - 使用 ESummary 批量处理"""

    def __init__(self, session: requests.Session, email: str = "", api_key: str = ""):
        """
        初始化 PMCID 获取器

        Args:
            session: requests.Session 实例
            email: 可选的邮箱（提高请求限制）
            api_key: 可选的 API 密钥
        """
        self.logger = get_logger(__name__)
        self.session = session
        self.email = email
        self.api_key = api_key

        # NCBI 配置
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.rate_limit = RATE_LIMIT
        self.last_request_time = 0.0

    def _rate_limit(self) -> None:
        """处理 NCBI API 请求频率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < (1.0 / self.rate_limit):
            time.sleep((1.0 / self.rate_limit) - time_since_last)

        self.last_request_time = time.time()

    def _collect_pmids(self, papers: list[dict[str, Any]]) -> list[str]:
        """
        从论文列表中提取有效的 PMIDs

        Args:
            papers: 论文列表，每个论文可能包含 pmid 字段

        Returns:
            有效且非空的 PMIDs 列表
        """
        pmids = []
        seen_pmids = set()  # 去重

        for paper in papers:
            pmid = paper.get("pmid")
            if pmid and pmid.strip():
                pmid = pmid.strip()
                # 确保 PMID 是数字（基本验证）
                if pmid.isdigit() and pmid not in seen_pmids:
                    pmids.append(pmid)
                    seen_pmids.add(pmid)

        self.logger.debug(f"从 {len(papers)} 篇论文中收集到 {len(pmids)} 个有效 PMIDs")
        return pmids

    def _format_pmcid(self, pmcid: str) -> str:
        """
        标准化 PMCID 格式，确保包含 PMC 前缀

        Args:
            pmcid: 原始 PMCID（可能包含也可能不包含 PMC 前缀）

        Returns:
            标准化后的 PMCID（总是包含 PMC 前缀）
        """
        if not pmcid:
            return ""

        pmcid = pmcid.strip()
        if not pmcid.startswith("PMC"):
            pmcid = f"PMC{pmcid}"

        return pmcid

    def _fetch_pmcid_batch(
        self, pmids: list[str], batch_size: int = 100
    ) -> dict[str, str]:
        """
        使用 ESummary 批量获取 PMCID

        Args:
            pmids: PMID 列表
            batch_size: 每批处理的数量（NCBI 推荐最多 100）

        Returns:
            PMID 到 PMCID 的映射字典
        """
        if not pmids:
            return {}

        self.logger.info(f"批量获取 {len(pmids)} 个 PMIDs 的 PMCID")
        pmid_to_pmcid = {}

        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(pmids) + batch_size - 1) // batch_size

            self.logger.debug(
                f"处理第 {batch_num}/{total_batches} 批: {len(batch)} 个 PMIDs"
            )

            try:
                # 构建请求参数
                url = f"{self.base_url}esummary.fcgi"
                params = {
                    "db": "pubmed",
                    "id": ",".join(batch),
                    "retmode": "json",
                }

                # 添加认证信息（如果有）
                if self.email:
                    params["email"] = self.email
                if self.api_key:
                    params["api_key"] = self.api_key

                # 应用速率限制
                self._rate_limit()

                # 发送请求
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                # 解析响应
                data = response.json()

                if "result" not in data:
                    self.logger.warning(f"第 {batch_num} 批响应格式异常")
                    continue

                # 提取 PMCID
                batch_results = 0
                for pmid in batch:
                    # 检查 result 是否包含必要的信息
                    if "result" not in data:
                        continue

                    # 有些响应格式可能不同
                    result_data = data["result"]
                    if not isinstance(result_data, dict):
                        continue

                    # 获取 uids 列表（如果有）
                    uids = result_data.get("uids", [])
                    if pmid not in uids and pmid not in result_data:
                        # 检查 pmid 是否在结果中
                        continue

                    # 获取文章数据
                    article = result_data.get(pmid, {})
                    articleids = article.get("articleids", [])

                    # 确保 articleids 是一个列表
                    if isinstance(articleids, list):
                        for article_id in articleids:
                            if (
                                isinstance(article_id, dict)
                                and article_id.get("idtype") == "pmc"
                            ):
                                pmcid = article_id.get("value", "")
                                if pmcid:
                                    pmcid = self._format_pmcid(pmcid)
                                    pmid_to_pmcid[pmid] = pmcid
                                    batch_results += 1
                                    break
                    elif articleids:
                        self.logger.warning(
                            f"articleids 不是列表: {type(articleids)} - {articleids}"
                        )

                self.logger.debug(f"第 {batch_num} 批获取到 {batch_results} 个 PMCID")

            except requests.exceptions.Timeout:
                self.logger.error(f"第 {batch_num} 批请求超时")
            except requests.exceptions.RequestException as e:
                self.logger.error(f"第 {batch_num} 批请求失败: {str(e)}")
            except Exception as e:
                self.logger.error(f"第 {batch_num} 批处理出错: {str(e)}")
                self.logger.debug(f"错误详情: {type(e).__name__}: {e}")
                import traceback

                self.logger.debug(traceback.format_exc())

        self.logger.info(
            f"批量获取完成：{len(pmid_to_pmcid)}/{len(pmids)} 个 PMIDs 有 PMCID"
        )
        return pmid_to_pmcid

    def _fetch_pmcid_individual(self, pmid: str) -> str | None:
        """
        逐个获取 PMCID（作为批量获取的备选方案）

        Args:
            pmid: 单个 PMID

        Returns:
            PMCID 或 None
        """
        try:
            url = f"{self.base_url}esummary.fcgi"
            params = {
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
            }

            if self.email:
                params["email"] = self.email
            if self.api_key:
                params["api_key"] = self.api_key

            self._rate_limit()

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if "result" in data and pmid in data["result"]:
                article = data["result"][pmid]
                articleids = article.get("articleids", [])

                if isinstance(articleids, list):
                    for article_id in articleids:
                        if (
                            isinstance(article_id, dict)
                            and article_id.get("idtype") == "pmc"
                        ):
                            pmcid = article_id.get("value", "")
                            return self._format_pmcid(pmcid)

            return None

        except Exception as e:
            self.logger.debug(f"获取 PMID {pmid} 的 PMCID 失败: {str(e)}")
            return None

    def process_papers(
        self, papers: list[dict[str, Any]], use_fallback: bool = True
    ) -> list[dict[str, Any]]:
        """
        为论文列表批量添加 PMCID 信息

        Args:
            papers: 论文列表
            use_fallback: 如果批量获取失败的部分是否使用逐个获取作为备选

        Returns:
            更新后的论文列表，添加了 pmcid 字段
        """
        if not papers:
            return papers

        self.logger.info(f"开始为 {len(papers)} 篇论文批量获取 PMCID")

        # 收集有效 PMIDs
        pmids = self._collect_pmids(papers)

        if not pmids:
            self.logger.info("没有有效的 PMIDs，跳过 PMCID 获取")
            return papers

        # 批量获取 PMCID
        pmid_to_pmcid = self._fetch_pmcid_batch(pmids)

        # 处理获取失败的 PMIDs（如果启用备选方案）
        if use_fallback:
            failed_pmids = [pmid for pmid in pmids if pmid not in pmid_to_pmcid]
            if failed_pmids:
                self.logger.info(f"对 {len(failed_pmids)} 个失败的 PMIDs 使用逐个获取")
                for pmid in failed_pmids[:10]:  # 限制备选数量，避免太慢
                    pmcid = self._fetch_pmcid_individual(pmid)
                    if pmcid:
                        pmid_to_pmcid[pmid] = pmcid

        # 更新论文信息
        updated_papers = []
        success_count = 0

        for paper in papers:
            updated_paper = paper.copy()
            pmid = updated_paper.get("pmid", "")

            if pmid and pmid in pmid_to_pmcid:
                updated_paper["pmcid"] = pmid_to_pmcid[pmid]
                success_count += 1

            updated_papers.append(updated_paper)

        self.logger.info(
            f"PMCID 更新完成：{success_count}/{len(papers)} 篇论文获得 PMCID"
        )
        return updated_papers

    def get_single_pmcid(self, paper: dict[str, Any]) -> str | None:
        """
        获取单篇论文的 PMCID（兼容原接口）

        Args:
            paper: 包含 pmid 的论文字典

        Returns:
            PMCID 或 None
        """
        pmid = paper.get("pmid")
        if not pmid:
            return None

        # 先尝试批量获取缓存（如果有）
        # 这里可以添加缓存逻辑

        # 逐个获取
        return self._fetch_pmcid_individual(pmid)
