"""
标识符处理工具

提供统一的标识符检测、验证和标准化功能。
"""

import re
from typing import Literal


class IdentifierUtils:
    """标识符工具类"""

    # 标识符类型
    TYPE_PMID = "pmid"
    TYPE_PMCID = "pmcid"
    TYPE_DOI = "doi"
    TYPE_UNKNOWN = "unknown"

    @staticmethod
    def detect_identifier_type(identifier: str) -> str:
        """
        检测标识符类型

        Args:
            identifier: 标识符字符串

        Returns:
            标识符类型：'pmid', 'pmcid', 'doi', 'unknown'
        """
        if not identifier:
            return IdentifierUtils.TYPE_UNKNOWN

        identifier = identifier.strip()

        # PMCID检测
        if identifier.lower().startswith("pmc"):
            # 移除PMC前缀后检查是否为数字
            pmcid_part = identifier[3:]
            if pmcid_part.isdigit() and 1 <= len(pmcid_part) <= 8:
                return IdentifierUtils.TYPE_PMCID

        # DOI检测
        if identifier.startswith("10.") and "/" in identifier and len(identifier) > 8:
                return IdentifierUtils.TYPE_DOI

        # PMID检测
        if identifier.isdigit() and 6 <= len(identifier) <= 10:
            return IdentifierUtils.TYPE_PMID

        return IdentifierUtils.TYPE_UNKNOWN

    @staticmethod
    def normalize_pmcid(pmcid: str) -> str | None:
        """
        标准化PMCID

        Args:
            pmcid: PMCID字符串（可能带PMC前缀）

        Returns:
            标准化的PMCID（不含PMC前缀），或None（如果无效）
        """
        if not pmcid:
            return None

        pmcid = pmcid.strip()

        # 移除PMC前缀（不区分大小写）
        if pmcid.lower().startswith("pmc"):
            pmcid = pmcid[3:]

        # 验证是否为有效数字
        if pmcid.isdigit() and 1 <= len(pmcid) <= 8:
            return pmcid

        return None

    @staticmethod
    def validate_pmcid(pmcid: str) -> bool:
        """
        验证PMCID格式

        Args:
            pmcid: PMCID字符串

        Returns:
            是否为有效的PMCID
        """
        if not pmcid:
            return False

        pmcid = pmcid.strip()

        # 检查PMC前缀
        if pmcid.lower().startswith("pmc"):
            pmcid = pmcid[3:]

        # 验证是否为1-8位数字
        return pmcid.isdigit() and 1 <= len(pmcid) <= 8

    @staticmethod
    def validate_pmid(pmid: str) -> bool:
        """
        验证PMID格式

        Args:
            pmid: PMID字符串

        Returns:
            是否为有效的PMID
        """
        if not pmid:
            return False

        pmid = pmid.strip()

        # PMID应为6-10位数字
        return pmid.isdigit() and 6 <= len(pmid) <= 10

    @staticmethod
    def validate_doi(doi: str) -> bool:
        """
        验证DOI格式

        Args:
            doi: DOI字符串

        Returns:
            是否为有效的DOI
        """
        if not doi:
            return False

        doi = doi.strip()

        # DOI基本格式：10.开头，包含/，最小长度8
        if not doi.startswith("10.") or "/" not in doi or len(doi) < 8:
            return False

        # 简单的DOI格式验证
        doi_pattern = r"^10\.\d+/.+$"
        return bool(re.match(doi_pattern, doi))

    @staticmethod
    def clean_identifier_string(identifier: str) -> str:
        """
        清理标识符字符串

        Args:
            identifier: 原始标识符字符串

        Returns:
            清理后的标识符字符串
        """
        if not identifier:
            return ""

        # 去除首尾空白字符和换行符
        return identifier.strip()

    @staticmethod
    def parse_identifier_list(identifiers: str) -> list[str]:
        """
        解析标识符列表

        Args:
            identifiers: 逗号分隔的标识符字符串

        Returns:
            标识符列表
        """
        if not identifiers:
            return []

        # 分割并清理每个标识符
        result = []
        for identifier in identifiers.split(","):
            cleaned = IdentifierUtils.clean_identifier_string(identifier)
            if cleaned:
                result.append(cleaned)

        return result

    @staticmethod
    def classify_identifiers(identifiers: list[str]) -> dict[str, list[str]]:
        """
        分类标识符

        Args:
            identifiers: 标识符列表

        Returns:
            分类后的标识符字典
        """
        classified: dict[str, list[str]] = {"pmcid": [], "pmid": [], "doi": [], "unknown": []}

        for identifier in identifiers:
            id_type = IdentifierUtils.detect_identifier_type(identifier)
            classified[id_type].append(identifier)

        return classified

    @staticmethod
    def extract_pmcid_number(pmcid: str) -> str | None:
        """
        从PMCID中提取数字部分

        Args:
            pmcid: PMCID字符串

        Returns:
            数字部分，或None（如果无效）
        """
        return IdentifierUtils.normalize_pmcid(pmcid)

    @staticmethod
    def format_pmcid(pmcid: str, with_prefix: bool = True) -> str:
        """
        格式化PMCID

        Args:
            pmcid: PMCID数字部分
            with_prefix: 是否包含PMC前缀

        Returns:
            格式化的PMCID
        """
        if not pmcid:
            return ""

        pmcid = pmcid.strip()

        # 确保只保留数字部分
        pmcid = re.sub(r"[^\d]", "", pmcid)

        if not pmcid:
            return ""

        if with_prefix and not pmcid.startswith("PMC"):
            return f"PMC{pmcid}"

        return pmcid

    @staticmethod
    def is_pmcid_with_prefix(pmcid: str) -> bool:
        """
        检查PMCID是否包含前缀

        Args:
            pmcid: PMCID字符串

        Returns:
            是否包含PMC前缀
        """
        return pmcid.lower().startswith("pmc") if pmcid else False

    @staticmethod
    def remove_pmcid_prefix(pmcid: str) -> str:
        """
        移除PMCID前缀

        Args:
            pmcid: PMCID字符串

        Returns:
            不含前缀的PMCID
        """
        if pmcid and IdentifierUtils.is_pmcid_with_prefix(pmcid):
            return pmcid[3:]
        return pmcid

    @staticmethod
    def add_pmcid_prefix(pmcid: str) -> str:
        """
        添加PMCID前缀

        Args:
            pmcid: PMCID字符串

        Returns:
            带PMC前缀的PMCID
        """
        if pmcid and not IdentifierUtils.is_pmcid_with_prefix(pmcid):
            return f"PMC{pmcid}"
        return pmcid
