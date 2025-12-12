"""
摘要补充器 - 从 XML 获取缺失的摘要
"""

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests


class AbstractSupplementor:
    """摘要补充器，用于从 XML 获取缺失的摘要"""

    def __init__(self, timeout: int = 5, delay: float = 0.5):
        """
        初始化摘要补充器

        Args:
            timeout: 请求超时时间（秒）
            delay: 请求间隔（秒），避免请求过快
        """
        self.timeout = timeout
        self.delay = delay
        self.logger = logging.getLogger(__name__)
        self._cache: dict[str, str | None] = {}  # 简单的内存缓存

    def supplement_abstract(self, paper: dict[str, Any]) -> str | None:
        """
        为单篇论文补充摘要

        Args:
            paper: 论文字典，包含 pmcid 和 abstract 字段

        Returns:
            补充的摘要文本，如果无法补充则返回 None
        """
        pmcid = paper.get("pmcid", "").strip()
        abstract = paper.get("abstract", "").strip()

        # 如果已有摘要或无 PMCID，不需要补充
        if abstract or not pmcid:
            return None

        # 检查缓存
        cached_abstract: str | None = self._cache.get(pmcid)
        if pmcid in self._cache:
            return cached_abstract

        # 从 XML 获取摘要
        try:
            xml_url = (
                f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            )
            self.logger.debug(f"获取 XML: {pmcid}")

            response = requests.get(xml_url, timeout=self.timeout)
            response.raise_for_status()

            extracted_abstract = self._extract_abstract_from_xml(response.text)

            # 缓存结果（包括 None）
            self._cache[pmcid] = extracted_abstract

            if extracted_abstract:
                self.logger.debug(
                    f"成功提取摘要: {pmcid} ({len(extracted_abstract)} 字符)"
                )

            return extracted_abstract

        except requests.exceptions.Timeout:
            self.logger.warning(f"获取 XML 超时: {pmcid}")
            self._cache[pmcid] = None
            return None
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"获取 XML 失败: {pmcid} - {str(e)}")
            self._cache[pmcid] = None
            return None
        except Exception as e:
            self.logger.error(f"解析 XML 错误: {pmcid} - {str(e)}")
            self._cache[pmcid] = None
            return None
        finally:
            # 添加延迟避免请求过快
            if self.delay > 0:
                time.sleep(self.delay)

    def supplement_abstracts_batch(
        self, papers: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        批量补充摘要

        Args:
            papers: 论文列表

        Returns:
            更新后的论文列表
        """
        updated_papers = []

        for paper in papers:
            updated_paper = paper.copy()
            new_abstract = self.supplement_abstract(paper)

            if new_abstract:
                updated_paper["abstract"] = new_abstract
                updated_paper["abstract_source"] = "xml"
            elif "abstract_source" not in updated_paper:
                updated_paper["abstract_source"] = (
                    "api" if updated_paper.get("abstract") else "none"
                )

            updated_papers.append(updated_paper)

        return updated_papers

    def _extract_abstract_from_xml(self, xml_content: str) -> str | None:
        """
        从 XML 内容中提取摘要

        Args:
            xml_content: XML 字符串

        Returns:
            提取的摘要文本，如果没有摘要则返回 None
        """
        try:
            root = ET.fromstring(xml_content)
            abstract_elem = root.find(".//abstract")

            if abstract_elem is not None:
                # 收集所有文本
                text_parts = []
                for elem in abstract_elem.iter():
                    if elem.text:
                        text_parts.append(elem.text)
                    if elem.tail:
                        text_parts.append(elem.tail)

                # 合并并清理文本
                abstract_text = " ".join(text_parts)
                # 清理多余的空白
                abstract_text = re.sub(r"\s+", " ", abstract_text.strip())

                return abstract_text if abstract_text else None

            return None

        except ET.ParseError as e:
            self.logger.warning(f"XML 解析错误: {str(e)}")
            return None
