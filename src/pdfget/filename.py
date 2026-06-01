"""
统一的 PDF 文件名生成工具

所有下载路径（PMC OA 直接 PDF、tar.gz 提取、Europe PMC 回退）
都使用此函数确保文件名一致：
  - 有 DOI → {PMCID}_{clean_doi}.pdf
  - 无 DOI → {PMCID}.pdf
"""

import re


def make_pdf_filename(pmcid: str, doi: str | None = None) -> str:
    """生成安全的 PDF 文件名。

    Args:
        pmcid: PMCID（如 "PMC123456"）
        doi: DOI 字符串，可为 None 或空字符串

    Returns:
        安全的文件名字符串，如 "PMC123456_101186s12916020016904.pdf" 或 "PMC123456.pdf"
    """
    if not doi:
        return f"{pmcid}.pdf"

    # 移除 .pdf 后缀（防止双重后缀）
    clean = doi
    if clean.lower().endswith(".pdf"):
        clean = clean[:-4]

    # 只保留字母和数字
    safe = re.sub(r"[^a-zA-Z0-9]", "", clean)
    safe = safe[:50]  # 截断过长 DOI

    # 清洗后为空则回退到纯 PMCID
    if not safe:
        return f"{pmcid}.pdf"

    return f"{pmcid}_{safe}.pdf"
