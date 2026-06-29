"""
标识符处理工具

提供统一的标识符检测、验证和标准化功能。
"""

import re


class IdentifierUtils:
    """标识符工具类"""

    # 标识符类型
    TYPE_PMID = "pmid"
    TYPE_PMCID = "pmcid"
    TYPE_DOI = "doi"
    TYPE_ARXIV = "arxiv"
    TYPE_UNKNOWN = "unknown"

    @staticmethod
    def detect_identifier_type(identifier: str) -> str:
        """
        检测标识符类型

        Args:
            identifier: 标识符字符串

        Returns:
            标识符类型：'pmid', 'pmcid', 'doi', 'arxiv', 'unknown'
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

        # arXiv 检测
        if IdentifierUtils.validate_arxiv_id(identifier):
            return IdentifierUtils.TYPE_ARXIV

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
    def validate_arxiv_id(identifier: str) -> bool:
        """验证 arXiv ID 格式。"""
        normalized = identifier.strip() if identifier else ""
        if not normalized:
            return False

        if normalized.lower().startswith("arxiv:"):
            normalized = normalized[6:].strip()

        new_style_pattern = r"^\d{4}\.\d{4,5}(v\d+)?$"
        old_style_pattern = r"^[a-z\-]+(\.[A-Z]{2})?/\d{7}(v\d+)?$"
        return bool(
            re.match(new_style_pattern, normalized)
            or re.match(old_style_pattern, normalized)
        )

    @staticmethod
    def normalize_arxiv_id(identifier: str) -> str | None:
        """标准化 arXiv ID。"""
        normalized = identifier.strip() if identifier else ""
        if not normalized:
            return None

        if normalized.lower().startswith("arxiv:"):
            normalized = normalized[6:].strip()

        return normalized if IdentifierUtils.validate_arxiv_id(normalized) else None
