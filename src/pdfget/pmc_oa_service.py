"""
PMC OA Web Service 客户端

使用 PMC 官方 Open Access Web Service 下载 PDF 文件
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import requests

from .logger import get_logger


class PMCOAService:
    """PMC OA Web Service 客户端"""

    def __init__(self, output_dir: str, session: requests.Session):
        """
        初始化 PMC OA Service

        Args:
            output_dir: 输出目录
            session: requests.Session 实例
        """
        self.logger = get_logger(__name__)
        self.output_dir = Path(output_dir)
        self.session = session

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # OA Web Service URL
        self.oa_service_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"

    def _query_oa_service(self, pmcid: str) -> ET.Element | None:
        """
        查询 PMC OA Web Service

        Args:
            pmcid: PMCID (例如: PMC7446157)

        Returns:
            XML 响应的 Element 对象，失败返回 None
        """
        url = f"{self.oa_service_url}?id={pmcid}"
        self.logger.debug(f"Querying OA service for {pmcid}")

        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                self.logger.error(f"OA service returned {response.status_code}")
                return None

            # 解析 XML
            root = ET.fromstring(response.text)
            return root

        except requests.RequestException as e:
            self.logger.error(f"Error querying OA service for {pmcid}: {e}")
            return None
        except ET.ParseError as e:
            self.logger.error(f"Error parsing XML response for {pmcid}: {e}")
            return None

    def _extract_download_links(self, root: ET.Element) -> list[dict[str, str]]:
        """
        从 XML 响应中提取下载链接

        Args:
            root: XML 根元素

        Returns:
            下载链接列表，每个链接包含 format, href, updated 信息
        """
        links: list[dict[str, str]] = []

        # 检查错误
        error_elem = root.find(".//error")
        if error_elem is not None:
            code = error_elem.get("code", "unknown")
            message = error_elem.text or "Unknown error"
            self.logger.debug(f"OA service error: {code} - {message}")
            return links

        # 查找记录
        record = root.find(".//record")
        if record is None:
            self.logger.debug("No record found in OA response")
            return links

        # 获取所有链接
        for link_elem in record.findall("link"):
            format_type = link_elem.get("format", "")
            href = link_elem.get("href", "")
            updated = link_elem.get("updated", "")

            if href:
                # 转换 FTP 为 HTTPS
                href = href.replace(
                    "ftp://ftp.ncbi.nlm.nih.gov/", "https://ftp.ncbi.nlm.nih.gov/"
                )
                links.append({"format": format_type, "href": href, "updated": updated})

        return links

    def _download_file(
        self, url: str, output_path: str, description: str = "file"
    ) -> bool:
        """
        下载文件

        Args:
            url: 下载 URL
            output_path: 输出文件路径
            description: 文件描述

        Returns:
            下载成功返回 True，失败返回 False
        """
        self.logger.info(f"Downloading {description} from {url}")

        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # 确保父目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            self.logger.info(f"Successfully downloaded {description} to {output_path}")
            return True

        except requests.RequestException as e:
            self.logger.error(f"Failed to download {description}: {e}")
            return False
        except OSError as e:
            self.logger.error(f"Failed to save {description}: {e}")
            return False

    def _get_safe_filename(self, pmcid: str, doi: str) -> str:
        """
        生成安全的文件名

        Args:
            pmcid: PMCID
            doi: DOI

        Returns:
            安全的文件名
        """
        import re

        # 从 DOI 提取可用的字符
        if doi:
            # 移除 .pdf 后缀（如果有）
            if doi.lower().endswith(".pdf"):
                doi = doi[:-4]

            # 将第一个空格替换为's'，其他空格直接删除
            parts = doi.split(" ", 2)  # 最多分成3部分
            if len(parts) >= 2:
                safe_doi = parts[0] + "s" + "".join(parts[1:])
            else:
                safe_doi = parts[0] if parts else ""

            # 移除所有特殊字符，只保留字母和数字
            safe_doi = re.sub(r"[^a-zA-Z0-9]", "", safe_doi)
            safe_doi = safe_doi[:50]  # 限制长度
            # 确保不完全是空字符串
            if not safe_doi:
                safe_doi = "unknown"
        else:
            safe_doi = "unknown"

        # 组合文件名
        filename = f"{pmcid}_{safe_doi}.pdf"
        return filename

    def process_pmcid(self, pmcid: str, doi: str | None = None) -> bool:
        """
        处理单个 PMCID，下载可用的格式

        Args:
            pmcid: PMCID
            doi: DOI（可选，用于命名）

        Returns:
            成功返回 True，失败返回 False
        """
        self.logger.debug(f"Processing {pmcid}")

        # 查询 OA 服务
        xml_root = self._query_oa_service(pmcid)
        if xml_root is None:
            return False

        # 提取下载链接
        links = self._extract_download_links(xml_root)
        if not links:
            self.logger.warning(f"No download links found for {pmcid}")
            return False

        success = False

        # 按优先级下载：PDF > tar.gz
        pdf_links = [link for link in links if link["format"] == "pdf"]
        tgz_links = [link for link in links if link["format"] == "tgz"]

        # 尝试下载 PDF
        if pdf_links:
            pdf_link = pdf_links[0]
            pdf_name = self._get_safe_filename(pmcid, doi) if doi else f"{pmcid}.pdf"
            pdf_path = self.output_dir / pdf_name

            if self._download_file(pdf_link["href"], str(pdf_path), f"PDF for {pmcid}"):
                success = True

        # 如果没有 PDF 或 PDF 失败，尝试下载 tar.gz
        if not success and tgz_links:
            tgz_link = tgz_links[0]
            tgz_path = self.output_dir / f"{pmcid}.tar.gz"

            if self._download_file(
                tgz_link["href"], str(tgz_path), f"tar.gz for {pmcid}"
            ):
                # 尝试从 tar.gz 中提取 PDF
                extracted_pdf = self._extract_pdf_from_tgz(str(tgz_path), pmcid)
                if extracted_pdf:
                    success = True

        return success

    def _extract_pdf_from_tgz(self, tgz_path: str, pmcid: str) -> str | None:
        """
        从 tar.gz 文件中提取 PDF

        Args:
            tgz_path: tar.gz 文件路径
            pmcid: PMCID

        Returns:
            成功返回 PDF 文件路径，失败返回 None
        """
        try:
            import tarfile

            with tarfile.open(tgz_path, "r:gz") as tar:
                # 查找 PDF 文件
                pdf_files = [f for f in tar.getnames() if f.lower().endswith(".pdf")]

                if pdf_files:
                    # 使用第一个 PDF 文件
                    pdf_file = pdf_files[0]
                    tar.extract(pdf_file, path=self.output_dir)

                    # 获取提取的 PDF 路径
                    extracted_pdf = self.output_dir / pdf_file
                    if extracted_pdf.exists():
                        self.logger.info(f"Extracted PDF from tar.gz: {extracted_pdf}")
                        return str(extracted_pdf)

            self.logger.warning(f"No PDF found in tar.gz file: {tgz_path}")
            return None

        except (tarfile.TarError, OSError) as e:
            self.logger.error(f"Error extracting PDF from tar.gz: {e}")
            return None
