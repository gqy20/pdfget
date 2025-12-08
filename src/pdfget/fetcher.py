#!/usr/bin/env python3
"""
简化版文献获取器 - Linus风格
只做一件事：下载开放获取文献
遵循KISS原则：Keep It Simple, Stupid
"""

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

import logging


class PaperFetcher:
    """简单文献获取器"""

    def __init__(
        self,
        cache_dir: str = "data/cache",
        output_dir: str = "data/pdfs",
        default_source: str = "pubmed",
        sources: list[str] | None = None,
    ):
        """
        初始化获取器

        Args:
            cache_dir: 缓存目录
            output_dir: PDF输出目录
            default_source: 默认数据源 (pubmed, europe_pmc)
            sources: 支持的数据源列表
        """
        self.logger = logging.getLogger("PaperFetcher")
        self.cache_dir = Path(cache_dir)
        self.output_dir = Path(output_dir)
        self.default_source = default_source
        self.sources = sources or ["pubmed", "europe_pmc"]

        # NCBI 配置
        self.ncbi_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.email = ""  # 可配置邮箱以提高请求限制
        self.api_key = ""  # 可选 API 密钥
        self.rate_limit = 3  # 每秒最多3次请求
        self._last_request_time = 0.0

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 简单的HTTP会话
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (compatible; PDFGet/1.0)"}
        )

    def parse_query(self, query: str) -> str:
        """
        解析高级检索词为Europe PMC格式

        支持的语法：
        - 布尔运算符：AND, OR, NOT
        - 字段检索：title:, author:, journal:
        - 短语检索："exact phrase"

        Args:
            query: 用户输入的检索词

        Returns:
            Europe PMC格式的检索词
        """
        # 处理短语检索（引号包围的内容）
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)

        # 临时替换短语为占位符
        for i, phrase in enumerate(phrases):
            query = query.replace(f'"{phrase}"', f"__PHRASE_{i}__")

        # 处理字段检索
        field_mappings = {
            "title:": "TITLE:",
            "author:": "AUTHOR:",
            "journal:": "JOURNAL:",
            "abstract:": "ABSTRACT:",
        }

        for user_field, pmc_field in field_mappings.items():
            query = query.replace(user_field, pmc_field)

        # 恢复短语，并添加必要的引号
        for i, phrase in enumerate(phrases):
            query = query.replace(f"__PHRASE_{i}__", f'"{phrase}"')

        # 处理布尔运算符（确保大写）
        query = (
            query.replace(" and ", " AND ")
            .replace(" or ", " OR ")
            .replace(" not ", " NOT ")
        )

        return query.strip()

    def parse_query_pubmed(self, query: str) -> str:
        """
        解析高级检索词为 PubMed 格式

        支持的语法：
        - 布尔运算符：AND, OR, NOT
        - 字段检索：title, author, journal, abstract, year, mesh
        - 短语检索："exact phrase"

        Args:
            query: 用户输入的检索词

        Returns:
            PubMed 格式的检索词
        """
        # 处理短语检索（引号包围的内容）
        phrase_pattern = r'"([^"]+)"'
        phrases = re.findall(phrase_pattern, query)

        # 临时替换短语为占位符
        for i, phrase in enumerate(phrases):
            query = query.replace(f'"{phrase}"', f"__PHRASE_{i}__")

        # 处理字段检索（PubMed 格式）
        field_mappings = {
            "title:": "[Title]",
            "author:": "[Author]",
            "journal:": "[Journal]",
            "abstract:": "[Abstract]",
            "year:": "[Date - Publication]",
            "mesh:": "[MeSH Terms]",
        }

        for user_field, pubmed_field in field_mappings.items():
            query = query.replace(user_field, pubmed_field)

        # 恢复短语，并添加必要的引号
        for i, phrase in enumerate(phrases):
            query = query.replace(f"__PHRASE_{i}__", f'"{phrase}"')

        # 处理布尔运算符（PubMed 大小写敏感）
        query = (
            query.replace(" and ", " AND ")
            .replace(" or ", " OR ")
            .replace(" not ", " NOT ")
        )

        return query.strip()

    def _rate_limit_pubmed(self) -> None:
        """处理 PubMed API 请求频率限制"""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < (1.0 / self.rate_limit):
            time.sleep((1.0 / self.rate_limit) - time_since_last)

        self._last_request_time = time.time()

    def search_papers(
        self, query: str, limit: int = 50, source: str | None = None
    ) -> list[dict]:
        """
        通过指定数据源搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制
            source: 数据源 (pubmed, europe_pmc, both)

        Returns:
            文献列表，包含DOI、标题、作者等信息
        """
        # 确定数据源
        source = source or self.default_source

        if source == "pubmed":
            return self.search_pubmed(query, limit)
        elif source == "europe_pmc":
            return self.search_europe_pmc(query, limit)
        elif source == "both":
            return self.search_both_sources(query, limit)
        else:
            raise ValueError(f"不支持的数据源: {source}")

    def search_europe_pmc(self, query: str, limit: int = 50) -> list[dict]:
        """
        通过Europe PMC搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制

        Returns:
            文献列表，包含DOI、标题、作者等信息
        """
        self.logger.info(f"🔍 搜索文献 (Europe PMC): {query}")

        # 解析检索词
        parsed_query = self.parse_query(query)
        self.logger.debug(f"  解析后: {parsed_query}")

        # 构建搜索URL
        search_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": parsed_query,
            "resulttype": "core",
            "format": "json",
            "pageSize": min(limit, 1000),  # Europe PMC限制最多1000条
            "cursorMark": "*",
        }

        try:
            response = self.session.get(search_url, params=params, timeout=30)  # type: ignore[arg-type]
            response.raise_for_status()

            data = response.json()

            if data.get("hitCount", 0) == 0:
                self.logger.info("  ❌ 未找到匹配的文献")
                return []

            # 处理结果
            papers = []
            results = data.get("resultList", {}).get("result", [])

            for i, record in enumerate(results[:limit]):
                # 获取期刊信息
                journal_info = record.get("journalInfo", {})

                paper = {
                    "title": record.get("title", ""),
                    "authors": [
                        a.strip() for a in record.get("authorString", "").split(",")
                    ]
                    if record.get("authorString")
                    else [],
                    "journal": journal_info.get("journal", {}).get("title", ""),
                    "year": record.get("pubYear", ""),
                    "doi": record.get("doi", ""),
                    "pmcid": record.get("pmcid", ""),
                    "pmid": record.get("pmid", ""),
                    "abstract": record.get("abstractText", ""),
                    "isOpenAccess": bool(
                        record.get("pmcid")
                    ),  # 有PMCID通常表示开放获取
                    "source": "Europe PMC",
                    # 新增的10个字段
                    "affiliation": record.get("affiliation", ""),
                    "volume": journal_info.get("volume", ""),
                    "issue": journal_info.get("issue", ""),
                    "pages": record.get("pageInfo", ""),
                    "license": record.get("license", ""),
                    "citedBy": record.get("citedByCount", 0),
                    "keywords": record.get("keywordList", []),
                    "meshTerms": record.get("meshHeadingList", []),
                    "grants": record.get("grantsList", []),
                    "hasData": record.get("hasData") == "Y",
                    "hasSuppl": record.get("hasSuppl") == "Y",
                }
                papers.append(paper)

                self.logger.info(
                    f"  📄 {i + 1}/{min(len(results), limit)}: {paper['title'][:60]}..."
                )

            self.logger.info(f"  ✅ 找到 {len(papers)} 篇文献")
            return papers

        except requests.exceptions.Timeout:
            self.logger.error("  ❌ 搜索超时")
            return []
        except requests.exceptions.ConnectionError:
            self.logger.error("  ❌ 连接失败")
            return []
        except Exception as e:
            self.logger.error(f"  ❌ 搜索失败: {str(e)}")
            return []

    def search_pubmed(self, query: str, limit: int = 50) -> list[dict]:
        """
        通过NCBI PubMed搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制

        Returns:
            文献列表，包含DOI、标题、作者等信息
        """
        self.logger.info(f"🔍 搜索文献 (PubMed): {query}")

        # 解析检索词
        parsed_query = self.parse_query_pubmed(query)
        self.logger.debug(f"  解析后: {parsed_query}")

        try:
            # 1. 使用 ESearch 获取 PMIDs
            self._rate_limit_pubmed()
            search_url = f"{self.ncbi_base_url}esearch.fcgi"
            search_params: dict[str, str | int] = {
                "db": "pubmed",
                "term": parsed_query,
                "retmode": "json",
                "retmax": limit,
            }

            if self.email:
                search_params["email"] = self.email
            if self.api_key:
                search_params["api_key"] = self.api_key

            response = self.session.get(search_url, params=search_params, timeout=30)
            response.raise_for_status()

            data = response.json()
            idlist = data.get("esearchresult", {}).get("idlist", [])

            if not idlist:
                self.logger.info("  ❌ 未找到匹配的文献")
                return []

            self.logger.info(f"  找到 {len(idlist)} 篇文献")

            # 2. 使用 ESummary 获取文献详情
            self._rate_limit_pubmed()
            summary_url = f"{self.ncbi_base_url}esummary.fcgi"
            summary_params = {
                "db": "pubmed",
                "id": ",".join(idlist),
                "retmode": "json",
            }

            if self.email:
                summary_params["email"] = self.email
            if self.api_key:
                summary_params["api_key"] = self.api_key

            response = self.session.get(summary_url, params=summary_params, timeout=30)
            response.raise_for_status()

            summary_data = response.json()
            result_data = summary_data.get("result", {})

            # 3. 使用 EFetch 获取详细信息（包括 PMCID）
            self._rate_limit_pubmed()
            fetch_url = f"{self.ncbi_base_url}efetch.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(idlist),
                "retmode": "xml",
                "rettype": "full",
            }

            if self.email:
                fetch_params["email"] = self.email
            if self.api_key:
                fetch_params["api_key"] = self.api_key

            try:
                response = self.session.get(fetch_url, params=fetch_params, timeout=30)
                response.raise_for_status()
                xml_data = response.text
            except Exception:
                xml_data = ""

            # 解析 XML 获取 PMCID
            import re

            pmid_to_pmcid = {}
            if xml_data:
                # 查找 PMCID 信息
                pmcid_pattern = r'<ArticleId IdType="pmc">([^<]+)</ArticleId>'
                pmid_pattern = r"<PMID.*?>(\d+)</PMID>"

                current_pmid = None
                for line in xml_data.split("\n"):
                    pmid_match = re.search(pmid_pattern, line)
                    if pmid_match:
                        current_pmid = pmid_match.group(1)

                    pmcid_match = re.search(pmcid_pattern, line)
                    if pmcid_match and current_pmid:
                        pmid_to_pmcid[current_pmid] = pmcid_match.group(1)

            # 处理结果
            papers = []
            for i, pmid in enumerate(idlist[:limit]):
                if pmid not in result_data:
                    continue

                record = result_data[pmid]

                # 提取 DOI
                doi = ""
                if "elocationid" in record:
                    # PubMed 中的 DOI 格式通常是 "doi: 10.xxxx/xxxxx"
                    doi_text = record["elocationid"]
                    if "doi:" in doi_text.lower():
                        doi = doi_text.split("doi:")[-1].strip()

                # 提取作者
                authors = []
                if "authors" in record:
                    authors = [author.get("name", "") for author in record["authors"]]

                # 提取年份
                year = ""
                if "pubdate" in record:
                    # PubMed 的 pubdate 格式通常是 "2023 Jan" 或 "2023 Jan 15"
                    year = record["pubdate"].split()[0]

                # 判断是否开放获取（如果有 PMC ID）
                pmcid = pmid_to_pmcid.get(pmid, record.get("pmcid", ""))
                is_open_access = bool(pmcid)

                paper = {
                    "title": record.get("title", ""),
                    "authors": authors,
                    "journal": record.get("source", ""),
                    "year": year,
                    "doi": doi,
                    "pmcid": pmcid,
                    "pmid": pmid,
                    "abstract": record.get("abstract", ""),
                    "isOpenAccess": is_open_access,
                    "source": "PubMed",
                    # 为了统一格式，添加其他字段
                    "affiliation": "",
                    "volume": record.get("volume", ""),
                    "issue": record.get("issue", ""),
                    "pages": record.get("pages", ""),
                    "license": "",
                    "citedBy": 0,
                    "keywords": [],
                    "meshTerms": record.get("meshheadinglist", []),
                    "grants": [],
                    "hasData": False,
                    "hasSuppl": False,
                }
                papers.append(paper)

                self.logger.info(
                    f"  📄 {i + 1}/{min(len(idlist), limit)}: {paper['title'][:60]}..."
                )

            self.logger.info(f"  ✅ 找到 {len(papers)} 篇文献")
            return papers

        except requests.exceptions.Timeout:
            self.logger.error("  ❌ 搜索超时")
            return []
        except requests.exceptions.ConnectionError:
            self.logger.error("  ❌ 连接失败")
            return []
        except Exception as e:
            self.logger.error(f"  ❌ 搜索失败: {str(e)}")
            return []

    def search_both_sources(self, query: str, limit: int = 50) -> list[dict]:
        """
        同时搜索两个数据源并合并结果

        Args:
            query: 检索词
            limit: 每个数据源返回结果数量限制

        Returns:
            去重后的文献列表
        """
        self.logger.info(f"🔍 搜索文献 (两个数据源): {query}")

        all_papers = []

        # 并行搜索两个数据源
        pubmed_limit = limit // 2
        europe_limit = limit - pubmed_limit

        # 搜索 PubMed
        try:
            pubmed_papers = self.search_pubmed(query, pubmed_limit)
            all_papers.extend(pubmed_papers)
        except Exception as e:
            self.logger.warning(f"PubMed 搜索失败: {e}")

        # 搜索 Europe PMC
        try:
            europe_papers = self.search_europe_pmc(query, europe_limit)
            all_papers.extend(europe_papers)
        except Exception as e:
            self.logger.warning(f"Europe PMC 搜索失败: {e}")

        # 去重
        deduplicated = self._deduplicate_papers(all_papers)

        # 如果超过限制，按数据源优先级排序
        if len(deduplicated) > limit:
            deduplicated = self._deduplicate_with_priority(deduplicated)[:limit]

        self.logger.info(f"  ✅ 找到 {len(deduplicated)} 篇文献（去重后）")
        return deduplicated

    def _deduplicate_papers(self, papers: list[dict]) -> list[dict]:
        """根据 DOI 去重论文"""
        seen_dois = set()
        deduplicated = []

        for paper in papers:
            doi = paper.get("doi", "")
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                deduplicated.append(paper)
            elif not doi:
                # 没有 DOI 的论文根据 PMID 去重
                pmid = paper.get("pmid", "")
                if pmid and pmid not in [p.get("pmid", "") for p in deduplicated]:
                    deduplicated.append(paper)

        return deduplicated

    def _deduplicate_with_priority(self, papers: list[dict]) -> list[dict]:
        """
        按数据源优先级去重，PubMed 优先
        """
        # 按 DOI 分组
        doi_groups: dict[str, list[dict]] = {}
        for paper in papers:
            doi = paper.get("doi", "")
            if doi:
                if doi not in doi_groups:
                    doi_groups[doi] = []
                doi_groups[doi].append(paper)

        # 对每个组，优先选择 PubMed 的论文
        deduplicated = []
        seen_dois = set()

        for paper in papers:
            doi = paper.get("doi", "")
            if not doi or doi in seen_dois:
                continue

            # 如果有重复，选择 PubMed 的
            group = doi_groups.get(doi, [paper])
            pubmed_paper = next((p for p in group if p.get("source") == "PubMed"), None)

            selected = pubmed_paper or group[0]
            if selected not in deduplicated:
                deduplicated.append(selected)
                seen_dois.add(doi)

        # 添加没有 DOI 的论文
        for paper in papers:
            if not paper.get("doi") and paper not in deduplicated:
                deduplicated.append(paper)

        return deduplicated

    def _standardize_paper_format(self, paper: dict, source: str) -> dict:
        """标准化论文格式"""
        standardized = {
            "title": paper.get("title", ""),
            "authors": [],
            "journal": "",
            "year": "",
            "doi": "",
            "pmcid": "",
            "pmid": "",
            "abstract": "",
            "isOpenAccess": False,
            "source": source,
            "affiliation": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "license": "",
            "citedBy": 0,
            "keywords": [],
            "meshTerms": [],
            "grants": [],
            "hasData": False,
            "hasSuppl": False,
        }

        if source == "Europe PMC":
            standardized.update(
                {
                    "authors": [
                        a.strip() for a in paper.get("authorString", "").split(",")
                    ]
                    if paper.get("authorString")
                    else [],
                    "journal": paper.get("journalInfo", {})
                    .get("journal", {})
                    .get("title", ""),
                    "doi": paper.get("doi", ""),
                    "pmcid": paper.get("pmcid", ""),
                    "pmid": paper.get("pmid", ""),
                    "abstract": paper.get("abstractText", ""),
                    "isOpenAccess": bool(paper.get("pmcid")),
                    "affiliation": paper.get("affiliation", ""),
                    "volume": paper.get("journalInfo", {}).get("volume", ""),
                    "issue": paper.get("journalInfo", {}).get("issue", ""),
                    "pages": paper.get("pageInfo", ""),
                    "citedBy": paper.get("citedByCount", 0),
                    "keywords": paper.get("keywordList", []),
                    "meshTerms": paper.get("meshHeadingList", []),
                }
            )
        elif source == "PubMed":
            # 提取 DOI
            doi = ""
            if "elocationid" in paper and "doi:" in paper["elocationid"].lower():
                doi = paper["elocationid"].split("doi:")[-1].strip()

            # 提取作者
            authors = []
            if "authors" in paper:
                authors = [author.get("name", "") for author in paper["authors"]]

            # 提取年份
            year = ""
            if "pubdate" in paper:
                year = paper["pubdate"].split()[0]
                # 使用年份避免未使用变量警告
                standardized["year"] = int(year) if year.isdigit() else 0

            standardized.update(
                {
                    "authors": authors,
                    "journal": paper.get("source", ""),
                    "doi": doi,
                    "pmcid": paper.get("pmcid", ""),
                    "pmid": paper.get("uid", ""),
                    "abstract": paper.get("abstract", ""),
                    "isOpenAccess": bool(paper.get("pmcid")),
                    "meshTerms": paper.get("meshheadinglist", []),
                }
            )

        return standardized

    def search_papers_with_fallback(
        self,
        query: str,
        primary: str = "pubmed",
        fallback: str = "europe_pmc",
        limit: int = 50,
    ) -> list[dict]:
        """
        带降级的搜索，主数据源失败时尝试备用数据源
        """
        try:
            return self.search_papers(query, limit, source=primary)
        except Exception as e:
            self.logger.warning(f"{primary} 搜索失败，尝试 {fallback}: {e}")
            try:
                return self.search_papers(query, limit, source=fallback)
            except Exception as e2:
                self.logger.error(f"两个数据源都失败: {e2}")
                return []

    def fetch_by_doi(
        self, doi: str, timeout: int = 30, pmcid: str | None = None
    ) -> dict:
        """
        通过DOI获取文献（简化版）

        策略：
        1. 如果有PMCID，直接下载
        2. 否则使用 Europe PMC 搜索PMCID
        3. 快速失败，不重试
        4. 简单缓存
        5. 不搞复杂的网络监控和自适应重试

        Args:
            doi: 文献DOI
            timeout: 超时时间
            pmcid: 可选的PMCID（如果已知）

        Returns:
            获取结果字典
        """
        self.logger.info(f"🔍 获取文献: {doi}")

        # 检查缓存
        cached_result = self._get_cache(doi)
        if cached_result:
            self.logger.info("  📦 从缓存加载")
            return cached_result

        # 如果有PMCID，直接尝试下载
        if pmcid:
            self.logger.info(f"  📄 使用已知PMCID: {pmcid}")
            pdf_result = self._download_pdf(pmcid, doi)

            if pdf_result["success"]:
                result = {
                    "success": True,
                    "doi": doi,
                    "pmcid": pmcid,
                    "pdf_path": pdf_result["path"],
                    "content_type": "pdf",
                }
            else:
                # PDF下载失败，返回全文HTML链接
                result = {
                    "success": True,
                    "doi": doi,
                    "pmcid": pmcid,
                    "full_text_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
                    "content_type": "html",
                }
        else:
            # 没有PMCID，使用Europe PMC搜索
            result = self._fetch_from_pmc(doi, timeout)

        # 缓存结果
        self._save_cache(doi, result)

        if result.get("success"):
            self.logger.info("  ✅ 获取成功")
        else:
            self.logger.info(f"  ❌ 获取失败: {result.get('error', 'Unknown error')}")

        return result

    def _fetch_from_pmc(self, doi: str, timeout: int) -> dict:
        """从Europe PMC获取文献"""
        try:
            # 搜索PMCID
            search_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:{quote(doi)}&resulttype=core&format=json"
            self.logger.debug(f"  🔍 Europe PMC URL: {search_url}")

            response = self.session.get(search_url, timeout=timeout)
            response.raise_for_status()

            data = response.json()
            if data.get("hitCount", 0) == 0:
                return {
                    "success": False,
                    "error": "Not found in Europe PMC",
                    "doi": doi,
                }

            record = data["resultList"]["result"][0]
            pmcid = record.get("pmcid")

            if not pmcid:
                self.logger.info("  ⏭️ 无PMCID，非开放获取文献")
                return {
                    "success": False,
                    "error": "Not open access (no PMCID)",
                    "doi": doi,
                }

            self.logger.info(f"  📄 找到PMCID: {pmcid}")

            # 尝试下载PDF
            pdf_result = self._download_pdf(pmcid, doi)

            if pdf_result["success"]:
                return {
                    "success": True,
                    "doi": doi,
                    "pmcid": pmcid,
                    "pdf_path": pdf_result["path"],
                    "content_type": "pdf",
                    "title": record.get("title"),
                    "journal": record.get("journalInfo", {})
                    .get("journal", {})
                    .get("title"),
                    "authors": [
                        a.strip() for a in record.get("authorString", "").split(",")
                    ]
                    if record.get("authorString")
                    else [],
                    "year": record.get("pubYear"),
                    "abstract": record.get("abstractText"),
                }

            # PDF下载失败，返回全文HTML链接
            return {
                "success": True,
                "doi": doi,
                "pmcid": pmcid,
                "full_text_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
                "content_type": "html",
                "title": record.get("title"),
                "authors": [
                    a.strip() for a in record.get("authorString", "").split(",")
                ]
                if record.get("authorString")
                else [],
                "year": record.get("pubYear"),
                "abstract": record.get("abstractText"),
            }

        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout", "doi": doi}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection error", "doi": doi}
        except Exception as e:
            return {"success": False, "error": str(e), "doi": doi}

    def _download_pdf(self, pmcid: str, doi: str) -> dict:
        """下载PDF文件"""
        # 尝试几个常见的PDF URL
        pdf_urls = [
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/",
            f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/{pmcid}.pdf",
            f"https://europepmc.org/articles/{pmcid}?pdf=render",
        ]

        for i, pdf_url in enumerate(pdf_urls):
            try:
                self.logger.debug(f"  📥 尝试PDF源 {i + 1}: {pdf_url}")
                response = self.session.get(pdf_url, timeout=30, stream=True)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()
                if "application/pdf" not in content_type:
                    continue

                # 保存文件
                safe_doi = "".join(c for c in doi if c.isalnum() or c in "-._")
                filename = f"{pmcid}_{safe_doi}.pdf"
                file_path = self.output_dir / filename

                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                self.logger.info(f"  💾 PDF保存成功: {file_path}")
                return {"success": True, "path": str(file_path)}

            except Exception as e:
                self.logger.debug(f"  ⚠️ PDF源 {i + 1} 失败: {str(e)}")
                continue

        return {"success": False, "error": "All PDF sources failed"}

    def _get_cache(self, doi: str) -> dict | None:
        """简单缓存检查"""
        cache_file = (
            self.cache_dir / f"cache_{hashlib.md5(doi.encode()).hexdigest()}.json"
        )

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)

                # 检查PDF文件是否还存在
                if data.get("pdf_path") and not Path(data["pdf_path"]).exists():
                    self.logger.debug("缓存的PDF文件不存在，清除缓存")
                    cache_file.unlink()
                    return None

                # 检查缓存是否过期（24小时）
                if time.time() - data.get("timestamp", 0) > 86400:
                    self.logger.debug("缓存已过期")
                    cache_file.unlink()
                    return None

                return data  # type: ignore

            except Exception as e:
                self.logger.debug(f"缓存读取失败: {str(e)}")
                cache_file.unlink()
                return None

        return None

    def _save_cache(self, doi: str, result: dict) -> None:
        """保存缓存"""
        try:
            cache_file = (
                self.cache_dir / f"cache_{hashlib.md5(doi.encode()).hexdigest()}.json"
            )
            result["timestamp"] = time.time()

            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)

        except Exception as e:
            self.logger.debug(f"缓存保存失败: {str(e)}")

    def fetch_batch(
        self, dois: list[str] | list[dict], delay: float = 1.0
    ) -> list[dict]:
        """
        批量获取文献（简化版）

        Args:
            dois: DOI列表或论文信息列表
            delay: 请求间延迟（秒）

        Returns:
            结果列表
        """
        # 检查输入格式
        papers: list[dict] = []
        if dois and isinstance(dois[0], dict):
            # 输入是论文信息列表
            papers = dois  # type: ignore
            dois = [p["doi"] for p in papers if p.get("doi")]  # type: ignore
        else:
            # 输入是DOI列表，没有PMCID信息
            papers = [{"doi": d} for d in dois]

        self.logger.info(f"🚀 批量获取 {len(dois)} 篇文献")
        results = []

        for i, paper in enumerate(papers, 1):
            doi = paper["doi"] if isinstance(paper, dict) else paper
            pmcid = paper.get("pmcid") if isinstance(paper, dict) else None

            self.logger.info(f"\n📄 进度: {i}/{len(papers)}")

            try:
                result = self.fetch_by_doi(str(doi), pmcid=pmcid)
                results.append(result)
            except Exception as e:
                self.logger.error(f"获取文献失败 ({doi}): {e}")
                results.append({"doi": doi, "success": False, "error": str(e)})

            # 简单延迟，避免被限制
            if i < len(papers):
                time.sleep(delay)

        # 统计结果
        success_count = sum(1 for r in results if r.get("success"))
        self.logger.info(f"\n📊 批量获取完成: {success_count}/{len(dois)} 成功")

        return results
