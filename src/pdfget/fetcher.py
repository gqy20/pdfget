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

    def __init__(self, cache_dir: str = "data/cache"):
        """
        初始化获取器

        Args:
            cache_dir: 缓存目录
        """
        self.logger = logging.getLogger("PaperFetcher")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 简单的HTTP会话
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; PaperFetcher/1.0)"
        })

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
            query = query.replace(f'"{phrase}"', f'__PHRASE_{i}__')

        # 处理字段检索
        field_mappings = {
            'title:': 'TITLE:',
            'author:': 'AUTHOR:',
            'journal:': 'JOURNAL:',
            'abstract:': 'ABSTRACT:'
        }

        for user_field, pmc_field in field_mappings.items():
            query = query.replace(user_field, pmc_field)

        # 恢复短语，并添加必要的引号
        for i, phrase in enumerate(phrases):
            query = query.replace(f'__PHRASE_{i}__', f'"{phrase}"')

        # 处理布尔运算符（确保大写）
        query = query.replace(' and ', ' AND ').replace(' or ', ' OR ').replace(' not ', ' NOT ')

        return query.strip()

    def search_papers(self, query: str, limit: int = 50) -> list[dict]:
        """
        通过Europe PMC搜索文献

        Args:
            query: 检索词（支持高级语法）
            limit: 返回结果数量限制

        Returns:
            文献列表，包含DOI、标题、作者等信息
        """
        self.logger.info(f"🔍 搜索文献: {query}")

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
            "cursorMark": "*"
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
                    "authors": [a.strip() for a in record.get("authorString", "").split(",")] if record.get("authorString") else [],
                    "journal": journal_info.get("journal", {}).get("title", ""),
                    "year": record.get("pubYear", ""),
                    "doi": record.get("doi", ""),
                    "pmcid": record.get("pmcid", ""),
                    "pmid": record.get("pmid", ""),
                    "abstract": record.get("abstractText", ""),
                    "isOpenAccess": bool(record.get("pmcid")),  # 有PMCID通常表示开放获取
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
                    "hasSuppl": record.get("hasSuppl") == "Y"
                }
                papers.append(paper)

                self.logger.info(f"  📄 {i+1}/{min(len(results), limit)}: {paper['title'][:60]}...")

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

    def fetch_by_doi(self, doi: str, timeout: int = 30) -> dict:
        """
        通过DOI获取文献（简化版）

        策略：
        1. 只处理开放获取文献（有PMCID）
        2. 快速失败，不重试
        3. 简单缓存
        4. 不搞复杂的网络监控和自适应重试

        Args:
            doi: 文献DOI
            timeout: 超时时间

        Returns:
            获取结果字典
        """
        self.logger.info(f"🔍 获取文献: {doi}")

        # 检查缓存
        cached_result = self._get_cache(doi)
        if cached_result:
            self.logger.info("  📦 从缓存加载")
            return cached_result

        # 只使用Europe PMC（主要的开放获取源）
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
                return {"success": False, "error": "Not found in Europe PMC", "doi": doi}

            record = data["resultList"]["result"][0]
            pmcid = record.get("pmcid")

            if not pmcid:
                self.logger.info("  ⏭️ 无PMCID，非开放获取文献")
                return {"success": False, "error": "Not open access (no PMCID)", "doi": doi}

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
                    "journal": record.get("journalInfo", {}).get("journal", {}).get("title"),
                    "authors": [a.strip() for a in record.get("authorString", "").split(",")] if record.get("authorString") else [],
                    "year": record.get("pubYear"),
                    "abstract": record.get("abstractText")
                }

            # PDF下载失败，返回全文HTML链接
            return {
                "success": True,
                "doi": doi,
                "pmcid": pmcid,
                "full_text_url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/",
                "content_type": "html",
                "title": record.get("title"),
                "authors": [a.strip() for a in record.get("authorString", "").split(",")] if record.get("authorString") else [],
                "year": record.get("pubYear"),
                "abstract": record.get("abstractText")
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
            f"https://europepmc.org/articles/{pmcid}?pdf=render"
        ]

        for i, pdf_url in enumerate(pdf_urls):
            try:
                self.logger.debug(f"  📥 尝试PDF源 {i+1}: {pdf_url}")
                response = self.session.get(pdf_url, timeout=30, stream=True)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").lower()
                if "application/pdf" not in content_type:
                    continue

                # 保存文件
                safe_doi = "".join(c for c in doi if c.isalnum() or c in "-._")
                filename = f"{pmcid}_{safe_doi}.pdf"
                file_path = self.cache_dir / filename

                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                self.logger.info(f"  💾 PDF保存成功: {file_path}")
                return {"success": True, "path": str(file_path)}

            except Exception as e:
                self.logger.debug(f"  ⚠️ PDF源 {i+1} 失败: {str(e)}")
                continue

        return {"success": False, "error": "All PDF sources failed"}

    def _get_cache(self, doi: str) -> dict | None:
        """简单缓存检查"""
        cache_file = self.cache_dir / f"cache_{hashlib.md5(doi.encode()).hexdigest()}.json"

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
            cache_file = self.cache_dir / f"cache_{hashlib.md5(doi.encode()).hexdigest()}.json"
            result["timestamp"] = time.time()

            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)

        except Exception as e:
            self.logger.debug(f"缓存保存失败: {str(e)}")

    def fetch_batch(self, dois: list[str], delay: float = 1.0) -> list[dict]:
        """
        批量获取文献（简化版）

        Args:
            dois: DOI列表
            delay: 请求间延迟（秒）

        Returns:
            结果列表
        """
        self.logger.info(f"🚀 批量获取 {len(dois)} 篇文献")
        results = []

        for i, doi in enumerate(dois, 1):
            self.logger.info(f"\n📄 进度: {i}/{len(dois)}")

            try:
                result = self.fetch_by_doi(doi)
                results.append(result)
            except Exception as e:
                self.logger.error(f"获取文献失败 ({doi}): {e}")
                results.append({
                    "doi": doi,
                    "success": False,
                    "error": str(e)
                })

            # 简单延迟，避免被限制
            if i < len(dois):
                time.sleep(delay)

        # 统计结果
        success_count = sum(1 for r in results if r.get("success"))
        self.logger.info(f"\n📊 批量获取完成: {success_count}/{len(dois)} 成功")

        return results