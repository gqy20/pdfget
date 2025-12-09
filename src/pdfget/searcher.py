"""
文献搜索模块

支持从多个数据源搜索学术论文
"""

import re
from typing import Any

import requests

from .config import DEFAULT_SOURCE, RATE_LIMIT
from .logger import get_logger


class PaperSearcher:
    """文献搜索器"""

    def __init__(self, session: requests.Session, email: str = "", api_key: str = ""):
        """
        初始化文献搜索器

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

        # Europe PMC 配置
        self.europe_pmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest"

        # 默认搜索源
        self.default_source = DEFAULT_SOURCE

    def _rate_limit(self) -> None:
        """处理 NCBI API 请求频率限制"""
        import time

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < (1.0 / self.rate_limit):
            time.sleep((1.0 / self.rate_limit) - time_since_last)

        self.last_request_time = time.time()

    def _parse_query_pubmed(self, query: str) -> str:
        """
        解析 PubMed 查询语法

        Args:
            query: 原始查询字符串

        Returns:
            解析后的 PubMed 查询字符串
        """
        # 处理年份过滤器 (year:2020 -> 2020[pdat])
        if "year:" in query:
            year_match = re.search(r"year:(\d{4})", query)
            if year_match:
                year = year_match.group(1)
                query = query.replace(f"year:{year}", f"{year}[pdat]")

        # 处理期刊过滤器 (journal:Nature -> "Nature"[TA])
        if "journal:" in query:
            journal_match = re.search(r"journal:([^\s]+)", query)
            if journal_match:
                journal = journal_match.group(1)
                query = query.replace(f"journal:{journal}", f'"{journal}"[TA]')

        # 处理作者过滤器 (author:Smith -> Smith[AU])
        if "author:" in query:
            author_match = re.search(r"author:([^\s]+)", query)
            if author_match:
                author = author_match.group(1)
                query = query.replace(f"author:{author}", f"{author}[AU]")

        return query

    def _parse_query_europepmc(self, query: str) -> str:
        """
        解析 Europe PMC 查询语法

        Args:
            query: 原始查询字符串

        Returns:
            解析后的 Europe PMC 查询字符串
        """
        # Europe PMC 支持更自然的查询语法，大部分情况下可以直接使用
        # 这里可以添加特定的转换逻辑

        # 处理年份过滤器
        if "year:" in query:
            year_match = re.search(r"year:(\d{4})", query)
            if year_match:
                year = year_match.group(1)
                query = query.replace(f"year:{year}", f"FIRST_PDATE:{year}")

        return query

    def _normalize_paper_data(
        self, paper: dict[str, Any], source: str
    ) -> dict[str, Any]:
        """
        标准化论文数据格式

        Args:
            paper: 原始论文数据
            source: 数据源

        Returns:
            标准化后的论文数据
        """
        normalized = {
            "pmid": paper.get("pmid", ""),
            "doi": paper.get("doi", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "journal": paper.get("journal", ""),
            "year": paper.get("year", ""),
            "abstract": paper.get("abstract", ""),
            "source": source,
        }

        # 处理作者字段 - 确保是列表
        if isinstance(normalized["authors"], str):
            normalized["authors"] = [normalized["authors"]]

        # 处理年份 - 只保留四位数字
        if normalized["year"]:
            year_match = re.search(r"\d{4}", str(normalized["year"]))
            if year_match:
                normalized["year"] = year_match.group()
            else:
                normalized["year"] = ""

        return normalized

    def _search_pubmed_api(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        执行 PubMed API 搜索

        Args:
            query: 查询字符串
            limit: 结果数量限制

        Returns:
            搜索结果列表
        """
        try:
            # 应用速率限制
            self._rate_limit()

            # 第一步：使用 ESearch 获取 PMIDs
            search_url = f"{self.base_url}esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": limit,
            }

            if self.email:
                search_params["email"] = self.email
            if self.api_key:
                search_params["api_key"] = self.api_key

            self.logger.debug(f"PubMed ESearch 查询: {query}")
            search_response = self.session.get(
                search_url,
                params=search_params,
                timeout=30,  # type: ignore[arg-type]
            )
            search_response.raise_for_status()

            search_data = search_response.json()
            pmids = search_data.get("esearchresult", {}).get("idlist", [])

            if not pmids:
                self.logger.debug("PubMed 搜索未找到结果")
                return []

            # 第二步：使用 ESummary 获取详细信息
            self._rate_limit()

            summary_url = f"{self.base_url}esummary.fcgi"
            summary_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            }

            if self.email:
                summary_params["email"] = self.email
            if self.api_key:
                summary_params["api_key"] = self.api_key

            summary_response = self.session.get(
                summary_url,
                params=summary_params,
                timeout=30,  # type: ignore[arg-type]
            )
            summary_response.raise_for_status()

            summary_data = summary_response.json()
            papers = []

            for pmid in pmids:
                if pmid in summary_data.get("result", {}):
                    article_data = summary_data["result"][pmid]

                    # 提取作者
                    authors = []
                    if "authors" in article_data:
                        for author in article_data["authors"]:
                            if "name" in author:
                                authors.append(author["name"])

                    # 提取期刊信息
                    year = ""
                    if "pubdate" in article_data:
                        pubdate = article_data["pubdate"]
                        # 提取年份
                        year_match = re.search(r"\d{4}", pubdate)
                        if year_match:
                            year = year_match.group()

                    # 提取DOI
                    doi = ""
                    if "articleids" in article_data:
                        for aid in article_data["articleids"]:
                            if aid.get("idtype") == "doi":
                                doi = aid.get("value", "")
                                break

                    # 构建论文数据
                    paper: dict[str, Any] = {
                        "pmid": pmid,
                        "doi": doi,
                        "title": article_data.get("title", ""),
                        "authors": authors,
                        "journal": article_data.get("fulljournalname", ""),
                        "year": year,
                        "abstract": "",  # ESummary 不包含摘要，需要 EFetch
                    }

                    papers.append(self._normalize_paper_data(paper, "pubmed"))

            self.logger.debug(f"PubMed 搜索返回 {len(papers)} 条结果")
            return papers

        except requests.exceptions.Timeout:
            self.logger.error("PubMed 搜索超时")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PubMed 搜索请求失败: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"PubMed 搜索出错: {str(e)}")
            return []

    def _search_europepmc_api(
        self, query: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        执行 Europe PMC API 搜索

        Args:
            query: 查询字符串
            limit: 结果数量限制

        Returns:
            搜索结果列表
        """
        try:
            # 使用 Europe PMC REST API
            search_url = f"{self.europe_pmc_url}/search"
            params = {
                "query": query,
                "resulttype": "core",
                "format": "json",
                "pageSize": min(limit, 100),  # Europe PMC 限制每页最多100条
                "cursor": "*",
                "synonym": "true",
                "fields": "pmid,doi,title,authorString,journalTitle,pubYear,abstractText,pmcid",  # 明确请求PMCID字段
            }

            self.logger.debug(f"Europe PMC 查询: {query}")
            response = self.session.get(search_url, params=params, timeout=30)  # type: ignore[arg-type]
            response.raise_for_status()

            data = response.json()
            papers = []

            if "resultList" in data and "result" in data["resultList"]:
                for item in data["resultList"]["result"]:
                    # 提取作者
                    authors = []
                    if "authorString" in item:
                        authors = [
                            a.strip()
                            for a in item["authorString"].split(";")
                            if a.strip()
                        ]

                    # 提取期刊和年份
                    journal = item.get("journalTitle", "")
                    year = ""
                    if "pubYear" in item:
                        year = str(item["pubYear"])

                    # 构建论文数据
                    paper: dict[str, Any] = {
                        "pmid": item.get("pmid", ""),
                        "doi": item.get("doi", ""),
                        "title": item.get("title", ""),
                        "authors": authors,
                        "journal": journal,
                        "year": year,
                        "abstract": item.get("abstractText", ""),
                        "pmcid": item.get("pmcid", ""),  # 添加PMCID字段
                    }

                    papers.append(self._normalize_paper_data(paper, "europe_pmc"))

            self.logger.debug(f"Europe PMC 搜索返回 {len(papers)} 条结果")
            return papers[:limit]  # 确保不超过请求的限制

        except requests.exceptions.Timeout:
            self.logger.error("Europe PMC 搜索超时")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Europe PMC 搜索请求失败: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Europe PMC 搜索出错: {str(e)}")
            return []

    def search_pubmed(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        通过 NCBI PubMed 搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制

        Returns:
            文献列表，包含 DOI、标题、作者等信息
        """
        self.logger.info(f"搜索文献 (PubMed): {query}")

        # 解析检索词
        parsed_query = self._parse_query_pubmed(query)
        if parsed_query != query:
            self.logger.debug(f"解析后的查询: {parsed_query}")

        # 执行搜索
        papers = self._search_pubmed_api(parsed_query, limit)

        if papers:
            self.logger.info(f"  ✓ 找到 {len(papers)} 篇文献")
        else:
            self.logger.warning("  ⚠ 未找到匹配的文献")

        return papers

    def search_europepmc(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        通过 Europe PMC 搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制

        Returns:
            文献列表，包含 DOI、标题、作者等信息
        """
        self.logger.info(f"搜索文献 (Europe PMC): {query}")

        # 解析检索词
        parsed_query = self._parse_query_europepmc(query)
        if parsed_query != query:
            self.logger.debug(f"解析后的查询: {parsed_query}")

        # 执行搜索
        papers = self._search_europepmc_api(parsed_query, limit)

        if papers:
            self.logger.info(f"  ✓ 找到 {len(papers)} 篇文献")
        else:
            self.logger.warning("  ⚠ 未找到匹配的文献")

        return papers

    def search_all_sources(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        从所有可用源搜索文献

        Args:
            query: 检索词
            limit: 每个源的结果数量限制

        Returns:
            合并后的文献列表
        """
        all_papers = []

        # 搜索 PubMed
        pubmed_papers = self.search_pubmed(query, limit)
        all_papers.extend(pubmed_papers)

        # 搜索 Europe PMC
        europe_pmc_papers = self.search_europepmc(query, limit)
        all_papers.extend(europe_pmc_papers)

        # 去重（基于 PMID）
        seen_pmids: set[str] = set()
        unique_papers: list[dict[str, Any]] = []
        for paper in all_papers:
            if paper["pmid"] and paper["pmid"] not in seen_pmids:
                seen_pmids.add(paper["pmid"])
                unique_papers.append(paper)
            elif not paper["pmid"]:  # 没有 PMID 的文章保留
                unique_papers.append(paper)

        return unique_papers

    def search_papers(
        self, query: str, limit: int = 50, source: str | None = None
    ) -> list[dict[str, Any]]:
        """
        通过指定数据源搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制
            source: 数据源 (pubmed, europe_pmc, both)

        Returns:
            文献列表，包含 DOI、标题、作者等信息
        """
        # 确定数据源
        source = source or self.default_source

        if source == "pubmed":
            return self.search_pubmed(query, limit)
        elif source == "europe_pmc":
            return self.search_europepmc(query, limit)
        elif source == "both":
            return self.search_all_sources(query, limit)
        else:
            self.logger.warning(f"未知的数据源: {source}，使用默认源")
            return self.search_pubmed(query, limit)
