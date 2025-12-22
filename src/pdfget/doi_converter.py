"""
DOI转换器模块

通过Europe PMC API和CrossRef API将DOI转换为PMCID。
采用TDD方式实现，专注于核心功能。
"""

import json
import time
from typing import Any

import requests

from .base.ncbi_base import NCBIBaseModule
from .config import (
    DOI_BATCH_SIZE,
    DOI_CROSSREF_EMAIL,
    DOI_CROSSREF_USER_AGENT,
    DOI_QUERY_TIMEOUT,
    DOI_RATE_LIMIT,
    DOI_USE_FALLBACK,
)
from .logger import get_logger
from .retry import retry_with_backoff
from .utils import IdentifierUtils


class DOIConverter(NCBIBaseModule):
    """DOI转换器 - 将DOI转换为PMCID"""

    # Europe PMC API端点
    EUROPEPMC_API_URL = "https://www.ebi.ac.uk/europepmc/api"
    DOI_QUERY_URL = f"{EUROPEPMC_API_URL}/search"

    # CrossRef API端点
    CROSSREF_API_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        session: requests.Session,
        email: str = "",
        api_key: str = "",
    ):
        """
        初始化DOI转换器

        Args:
            session: requests.Session实例
            email: NCBI API邮箱（可选，用于提高请求限制）
            api_key: NCBI API密钥（可选）
        """
        # 初始化NCBI基类（主要用于网络配置和日志）
        super().__init__(session=session, email=email, api_key=api_key)

        # 创建专门的速率限制器用于DOI查询
        from .utils import RateLimiter
        self.doi_rate_limiter = RateLimiter(rate_limit=DOI_RATE_LIMIT)

        # 简单的内存缓存，避免重复查询
        self._cache: dict[str, str | None] = {}

        # 公开API端点以供测试访问
        self.europepmc_doi_url = self.DOI_QUERY_URL

        self.logger.info("DOI转换器初始化完成")
        self.logger.debug(f"Europe PMC API: {self.DOI_QUERY_URL}")
        self.logger.debug(f"CrossRef API: {self.CROSSREF_API_URL}")

    def doi_to_pmcid(self, doi: str, use_fallback: bool = True) -> str | None:
        """
        将DOI转换为PMCID

        Args:
            doi: DOI字符串
            use_fallback: 是否在Europe PMC失败时使用CrossRef

        Returns:
            PMCID字符串，如果转换失败返回None
        """
        # 验证DOI格式
        if not IdentifierUtils.validate_doi(doi):
            self.logger.warning(f"无效的DOI格式: {doi}")
            return None

        # 检查缓存
        if doi in self._cache:
            cached_result = self._cache[doi]
            self.logger.debug(f"使用缓存结果: {doi} -> {cached_result}")
            return cached_result

        self.logger.debug(f"开始转换DOI到PMCID: {doi}")

        try:
            # 首先尝试Europe PMC API
            pmcid = self._query_europepmc_doi(doi)

            if pmcid:
                self._cache[doi] = pmcid
                return pmcid

            # 如果Europe PMC失败且允许使用备选方案，尝试CrossRef
            if use_fallback and DOI_USE_FALLBACK:
                self.logger.debug(f"Europe PMC无结果，尝试CrossRef: {doi}")
                pmcid = self._query_crossref_api(doi)

                if pmcid:
                    self._cache[doi] = pmcid
                    return pmcid

        except Exception as e:
            self.logger.error(f"DOI转换失败 ({doi}): {str(e)}")

        # 缓存失败结果（None）
        self._cache[doi] = None
        return None

    def _query_europepmc_doi(self, doi: str) -> str | None:
        """
        通过Europe PMC API查询DOI

        Args:
            doi: DOI字符串

        Returns:
            PMCID字符串，如果查询失败返回None
        """
        # 应用速率限制
        self.doi_rate_limiter.wait_for_rate_limit()

        # 构建查询参数
        params = {
            "query": f"doi:\"{doi}\"",
            "resulttype": "core",
            "format": "json",
        }

        try:
            # 发送请求
            response = self._make_request_with_retry(
                url=self.DOI_QUERY_URL,
                params=params,
                timeout=DOI_QUERY_TIMEOUT
            )

            if response and response.status_code == 200:
                data = response.json()
                return self._parse_europepmc_response(data, doi)
            else:
                self.logger.warning(f"Europe PMC API请求失败: {response.status_code if response else 'None'}")
                return None

        except Exception as e:
            self.logger.error(f"Europe PMC查询异常 ({doi}): {str(e)}")
            return None

    def _parse_europepmc_response(self, data: dict[str, Any], doi: str) -> str | None:
        """
        解析Europe PMC API响应

        Args:
            data: API响应数据
            doi: 原始DOI（用于验证）

        Returns:
            PMCID字符串，如果未找到返回None
        """
        try:
            results = data.get("resultList", {}).get("result", [])

            if not results:
                self.logger.debug(f"Europe PMC未找到结果: {doi}")
                return None

            # 遍历结果，寻找匹配的DOI
            for result in results:
                result_doi = result.get("doi", "")
                if result_doi.lower() == doi.lower():
                    pmcid = result.get("pmcid", "")
                    if pmcid:
                        self.logger.debug(f"Europe PMC找到PMCID: {doi} -> {pmcid}")
                        return pmcid

            self.logger.debug(f"Europe PMC结果中未找到匹配的DOI: {doi}")
            return None

        except Exception as e:
            self.logger.error(f"解析Europe PMC响应失败 ({doi}): {str(e)}")
            return None

    def _query_crossref_api(self, doi: str) -> str | None:
        """
        通过CrossRef API查询DOI（备选方案）

        注意：CrossRef API本身不直接返回PMCID，但可以获取论文信息，
        然后我们可以用这些信息再次查询Europe PMC。

        Args:
            doi: DOI字符串

        Returns:
            PMCID字符串，如果查询失败返回None
        """
        # 应用速率限制
        self.doi_rate_limiter.wait_for_rate_limit()

        # 构建请求头
        headers = {
            "User-Agent": DOI_CROSSREF_USER_AGENT,
            "Accept": "application/json",
        }
        if DOI_CROSSREF_EMAIL:
            headers["Mailto"] = DOI_CROSSREF_EMAIL

        try:
            response = self._make_request_with_retry(
                url=f"{self.CROSSREF_API_URL}/{doi}",
                headers=headers,
                timeout=DOI_QUERY_TIMEOUT
            )

            if response and response.status_code == 200:
                data = response.json()
                # 从CrossRef获取信息后，尝试用其他方式查找PMCID
                return self._extract_pmcid_from_crossref(data, doi)
            else:
                self.logger.warning(f"CrossRef API请求失败: {response.status_code if response else 'None'}")
                return None

        except Exception as e:
            self.logger.error(f"CrossRef查询异常 ({doi}): {str(e)}")
            return None

    def _extract_pmcid_from_crossref(self, data: dict[str, Any], doi: str) -> str | None:
        """
        从CrossRef响应中提取信息并查找PMCID

        Args:
            data: CrossRef API响应数据
            doi: 原始DOI

        Returns:
            PMCID字符串，如果找到返回None
        """
        try:
            # 提取论文标题，用于二次查询
            title = data.get("message", {}).get("title", [""])[0]
            authors = data.get("message", {}).get("author", [])

            if title:
                # 使用标题再次查询Europe PMC
                self.logger.debug(f"使用标题查询Europe PMC: {title}")
                return self._query_europepmc_by_title(title)

            return None

        except Exception as e:
            self.logger.error(f"从CrossRef提取信息失败 ({doi}): {str(e)}")
            return None

    def _query_europepmc_by_title(self, title: str) -> str | None:
        """
        通过标题查询Europe PMC（CrossRef备选方案的后续步骤）

        Args:
            title: 论文标题

        Returns:
            PMCID字符串，如果找到返回None
        """
        # 应用速率限制
        self.doi_rate_limiter.wait_for_rate_limit()

        params = {
            "query": f"title:\"{title}\"",
            "resulttype": "core",
            "format": "json",
        }

        try:
            response = self._make_request_with_retry(
                url=self.DOI_QUERY_URL,
                params=params,
                timeout=DOI_QUERY_TIMEOUT
            )

            if response and response.status_code == 200:
                data = response.json()
                results = data.get("resultList", {}).get("result", [])

                if results:
                    # 返回第一个有PMCID的结果
                    for result in results:
                        pmcid = result.get("pmcid", "")
                        if pmcid:
                            self.logger.debug(f"通过标题找到PMCID: {title} -> {pmcid}")
                            return pmcid

            return None

        except Exception as e:
            self.logger.error(f"通过标题查询失败 ({title}): {str(e)}")
            return None

    def batch_doi_to_pmcid(self, doi_list: list[str]) -> dict[str, str | None]:
        """
        批量转换DOI到PMCID

        Args:
            doi_list: DOI字符串列表

        Returns:
            DOI到PMCID的映射字典
        """
        results: dict[str, str | None] = {}

        self.logger.info(f"开始批量转换 {len(doi_list)} 个DOI")

        for i, doi in enumerate(doi_list, 1):
            self.logger.debug(f"处理DOI {i}/{len(doi_list)}: {doi}")

            # 使用单个转换方法（包含缓存）
            pmcid = self.doi_to_pmcid(doi, use_fallback=True)
            results[doi] = pmcid

            # 每处理一定数量后输出进度
            if i % DOI_BATCH_SIZE == 0:
                self.logger.info(f"已处理 {i}/{len(doi_list)} 个DOI")

        # 统计结果
        successful = sum(1 for pmcid in results.values() if pmcid is not None)
        self.logger.info(f"批量转换完成: {successful}/{len(doi_list)} 成功")

        return results

    def _make_request_with_retry(self, **kwargs) -> requests.Response | None:
        """
        带重试的请求方法

        Args:
            **kwargs: 传递给session.get的参数

        Returns:
            Response对象，如果所有重试都失败返回None
        """
        retry_decorator = retry_with_backoff(max_retries=3)

        @retry_decorator
        def _request():
            return self.session.get(**kwargs)

        try:
            return _request()
        except Exception as e:
            self.logger.error(f"请求失败（重试3次后仍失败）: {str(e)}")
            return None

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self.logger.debug("DOI转换器缓存已清空")

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        total = len(self._cache)
        successful = sum(1 for v in self._cache.values() if v is not None)
        failed = total - successful

        return {
            "total_entries": total,
            "successful_conversions": successful,
            "failed_conversions": failed,
            "success_rate": successful / total * 100 if total > 0 else 0,
        }