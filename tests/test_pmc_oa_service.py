#!/usr/bin/env python3
"""
测试 PMC OA Web Service 功能

这个测试文件遵循TDD原则，先写测试，再实现代码。
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
import requests


class TestPMCOAService:
    """测试 PMCOAService 类 - 我们需要实现的类"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        return Mock(spec=requests.Session)

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        """创建临时目录"""
        return tmp_path / "pdfs"

    def test_init(self, session, tmp_dir):
        """
        测试: PMCOAService 初始化

        测试目标：
        - 创建 PMCOAService 实例
        - 确保输出目录被创建
        """
        # 这个测试会在我们实现 PMCOAService 类后启用
        from src.pdfget.pmc_oa_service import PMCOAService

        # 确保目录不存在
        assert not tmp_dir.exists()

        # 创建实例
        service = PMCOAService(str(tmp_dir), session)

        # 验证属性
        assert service.output_dir == tmp_dir
        assert service.session == session
        assert (
            service.oa_service_url
            == "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
        )

        # 验证目录被创建
        assert tmp_dir.exists()

    def test_query_oa_service_success(self):
        """
        测试: 成功查询 OA service

        测试目标：
        - 发送HTTP请求到OA service
        - 解析XML响应
        - 返回Element对象
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        # 创建模拟的 session 和响应
        session = Mock(spec=requests.Session)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <responseDate>2025-12-09 02:00:00</responseDate>
    <request id="PMC7446157">https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC7446157</request>
    <records returned-count="1" total-count="1">
        <record id="PMC7446157" citation="BMC Med. 2020 Aug 25; 18:225" license="CC BY" retracted="no">
            <link format="tgz" updated="2024-03-28 17:25:11" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/59/36/PMC7446157.tar.gz" />
        </record>
    </records>
</OA>"""
        session.get.return_value = mock_response

        # 创建服务实例
        service = PMCOAService("/tmp", session)

        # 执行查询
        result = service._query_oa_service("PMC7446157")

        # 验证结果
        assert result is not None
        assert isinstance(result, ET.Element)
        assert result.tag == "OA"

        # 验证请求参数
        session.get.assert_called_once_with(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC7446157",
            timeout=30,
        )

    def test_query_oa_service_http_error(self):
        """
        测试: OA service HTTP 错误

        测试目标：
        - 处理HTTP错误状态码
        - 返回 None
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        mock_response = Mock()
        mock_response.status_code = 404
        session.get.return_value = mock_response

        service = PMCOAService("/tmp", session)
        result = service._query_oa_service("PMC7446157")

        assert result is None

    def test_extract_download_links_pdf_only(self):
        """
        测试: 提取 PDF 下载链接

        测试目标：
        - 解析XML中的PDF链接
        - 将FTP转换为HTTPS
        - 返回链接信息
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <records>
        <record id="PMC7927990">
            <link format="pdf" updated="2021-03-03 14:52:19" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/1d/5a/106863.PMC7927990.pdf" />
        </record>
    </records>
</OA>"""
        root = ET.fromstring(xml_content)

        links = service._extract_download_links(root)

        assert len(links) == 1
        assert links[0]["format"] == "pdf"
        assert (
            links[0]["href"]
            == "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/1d/5a/106863.PMC7927990.pdf"
        )
        assert links[0]["updated"] == "2021-03-03 14:52:19"

    def test_extract_download_links_tgz_only(self):
        """
        测试: 提取 tar.gz 下载链接

        测试目标：
        - 解析XML中的tar.gz链接
        - 将FTP转换为HTTPS
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <records>
        <record id="PMC7446157">
            <link format="tgz" updated="2024-03-28 17:25:11" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/59/36/PMC7446157.tar.gz" />
        </record>
    </records>
</OA>"""
        root = ET.fromstring(xml_content)

        links = service._extract_download_links(root)

        assert len(links) == 1
        assert links[0]["format"] == "tgz"
        assert (
            links[0]["href"]
            == "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/59/36/PMC7446157.tar.gz"
        )

    def test_extract_download_links_not_open_access(self):
        """
        测试: 非开放获取文章

        测试目标：
        - 识别OA service错误响应
        - 返回空列表
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <error code="idIsNotOpenAccess">identifier 'PMC8026279' is not Open Access</error>
</OA>"""
        root = ET.fromstring(xml_content)

        links = service._extract_download_links(root)

        assert len(links) == 0

    def test_download_file_success(self):
        """
        测试: 成功下载文件

        测试目标：
        - 发送GET请求
        - 流式保存文件
        - 创建必要的目录
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        # 模拟响应
        mock_response = Mock()
        mock_response.iter_content.return_value = [
            b"pdf content chunk 1",
            b"pdf content chunk 2",
        ]
        mock_response.raise_for_status.return_value = None
        session.get.return_value = mock_response

        # 模拟文件保存
        output_path = "/tmp/test.pdf"
        with (
            patch("builtins.open", mock_open()) as mock_file,
            patch.object(Path, "mkdir"),
        ):
            result = service._download_file("https://example.com/file.pdf", output_path)

            assert result is True
            mock_file.assert_called_once_with(output_path, "wb")
            # 验证写入内容
            mock_file().write.assert_any_call(b"pdf content chunk 1")
            mock_file().write.assert_any_call(b"pdf content chunk 2")

    def test_process_pmcid_with_pdf(self):
        """
        测试: 处理有 PDF 格式的 PMCID

        测试目标：
        - 查询OA service
        - 下载PDF
        - 使用安全的文件名
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        # 模拟完整的流程
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <records>
        <record id="PMC7927990">
            <link format="pdf" href="ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/1d/5a/106863.PMC7927990.pdf" />
        </record>
    </records>
</OA>"""

        with (
            patch.object(service, "_query_oa_service") as mock_query,
            patch.object(service, "_download_file") as mock_download,
        ):
            mock_query.return_value = ET.fromstring(mock_xml)
            mock_download.return_value = True

            result = service.process_pmcid("PMC7927990", doi="10.1000/test.doi")

            assert result is True
            mock_download.assert_called_once()

            # 验证文件名
            call_args = mock_download.call_args
            assert "PMC7927990" in call_args[0][1]  # 输出文件名包含PMCID

    def test_process_pmcid_not_open_access(self):
        """
        测试: 处理非开放获取的 PMCID

        测试目标：
        - 识别非开放获取
        - 不尝试下载
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService("/tmp", session)

        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<OA>
    <error code="idIsNotOpenAccess">identifier 'PMC8026279' is not Open Access</error>
</OA>"""

        with (
            patch.object(service, "_query_oa_service") as mock_query,
            patch.object(service, "_download_file") as mock_download,
        ):
            mock_query.return_value = ET.fromstring(mock_xml)

            result = service.process_pmcid("PMC8026279")

            assert result is False
            mock_download.assert_not_called()

    def test_extract_pdf_from_tgz_selects_main_paper_by_nxml_match(self, tmp_path):
        """
        测试: 从 tar.gz 中提取 PDF 时，应选择与 .nxml 同名的正文 PDF，
             而非第一个（可能是补充材料）。

        复现 Issue #1 的场景：压缩包中第一个 PDF 是补充材料。
        """
        import tarfile
        import io

        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService(str(tmp_path), session)

        # 构造一个模拟的 tar.gz，包含：
        # - .nxml 正文文件: article.nxml
        # - 第一个 PDF（补充材料）: supp_fig1.pdf
        # - 第二个 PDF（正文）: article.pdf ← 应该选这个
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name in [b"article.nxml", b"supp_fig1.pdf", b"article.pdf"]:
                info = tarfile.TarInfo(name=name.decode())
                info.size = len(b"dummy content")
                tar.addfile(info, io.BytesIO(b"dummy content"))

        buffer.seek(0)
        tgz_path = str(tmp_path / "test.tar.gz")
        Path(tgz_path).write_bytes(buffer.getvalue())

        result = service._extract_pdf_from_tgz(tgz_path, "PMC123", doi="10.1000/test")

        assert result is not None
        assert result.endswith("PMC123_101000test.pdf")  # 统一命名格式（选了 article.pdf）

    def test_extract_pdf_from_tgz_fallback_to_first_when_no_nxml(self, tmp_path):
        """
        测试: 压缩包中没有 .nxml 文件时，回退到选择第一个 PDF。
        """
        import tarfile
        import io

        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService(str(tmp_path), session)

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name in [b"only_file.pdf", b"other.pdf"]:
                info = tarfile.TarInfo(name=name.decode())
                info.size = len(b"dummy")
                tar.addfile(info, io.BytesIO(b"dummy"))

        buffer.seek(0)
        tgz_path = str(tmp_path / "test2.tar.gz")
        Path(tgz_path).write_bytes(buffer.getvalue())

        result = service._extract_pdf_from_tgz(tgz_path, "PMC456")

        assert result is not None
        assert result.endswith("PMC456.pdf")  # 无 DOI → 统一为 PMCID.pdf

    def test_extract_pdf_from_tgz_no_matching_pdf_falls_back(self, tmp_path):
        """
        测试: 有 .nxml 但没有同名 PDF 时，回退到第一个 PDF。
        """
        import tarfile
        import io

        from src.pdfget.pmc_oa_service import PMCOAService

        session = Mock(spec=requests.Session)
        service = PMCOAService(str(tmp_path), session)

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            for name in [b"paper.nxml", b"unrelated.pdf", b"another.pdf"]:
                info = tarfile.TarInfo(name=name.decode())
                info.size = len(b"x")
                tar.addfile(info, io.BytesIO(b"x"))

        buffer.seek(0)
        tgz_path = str(tmp_path / "test3.tar.gz")
        Path(tgz_path).write_bytes(buffer.getvalue())

        result = service._extract_pdf_from_tgz(tgz_path, "PMC789", doi="10.1000/x")

        assert result is not None
        assert result.endswith("PMC789_101000x.pdf")  # 统一命名格式（回退到第一个 PDF）

    @pytest.mark.integration
    def test_integration_real_api_call(self):
        """
        集成测试: 真实API调用

        这个测试需要网络连接，可以用 -m "not integration" 跳过
        """
        from src.pdfget.pmc_oa_service import PMCOAService

        # 使用真实的session（但这个测试可能因为网络问题失败）
        session = requests.Session()
        session.headers.update({"User-Agent": "test-pmc-oa-service/1.0"})

        service = PMCOAService("/tmp", session)

        # 测试一个已知开放获取的文章
        xml_root = service._query_oa_service("PMC7927990")

        assert xml_root is not None
        assert xml_root.tag == "OA"

        # 提取链接
        links = service._extract_download_links(xml_root)
        assert len(links) > 0

        # 应该有PDF链接
        pdf_links = [link for link in links if link["format"] == "pdf"]
        assert len(pdf_links) > 0
        assert pdf_links[0]["href"].startswith("https://ftp.ncbi.nlm.nih.gov")
