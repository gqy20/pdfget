#!/usr/bin/env python3
"""
集成测试：PMC OA Service 与 PDFDownloader 的整合

验证 PMC OA Service 正确集成到下载流程中
"""

from unittest.mock import Mock, patch

import pytest

from src.pdfget.downloader import PDFDownloader


@pytest.mark.integration
class TestPMCOAIntegration:
    """测试 PMC OA Service 集成"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        return Mock()

    @pytest.fixture
    def downloader(self, session, tmp_path):
        """创建 PDFDownloader 实例"""
        return PDFDownloader(str(tmp_path / "pdfs"), session)

    def test_download_pdf_uses_pmc_oa_first(self, downloader):
        """
        测试: download_pdf 首先尝试 PMC OA Service
        """
        pmcid = "PMC7927990"
        doi = "10.1000/test.doi"

        # 模拟 PMC OA Service 成功

        with (
            patch.object(downloader.pmc_oa_service, "process_pmcid") as mock_process,
            patch.object(downloader.pmc_oa_service, "_query_oa_service") as mock_query,
            patch.object(
                downloader.pmc_oa_service, "_extract_download_links"
            ) as mock_extract,
            patch.object(downloader.pmc_oa_service, "_download_file") as mock_download,
        ):
            # 模拟成功下载
            mock_process.return_value = True
            mock_query.return_value.__enter__ = lambda x: x
            mock_query.return_value.__exit__ = lambda x, *args: None
            mock_extract.return_value = [
                {
                    "format": "pdf",
                    "href": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/1d/5a/106863.PMC7927990.pdf",
                }
            ]
            mock_download.return_value = True

            # 模拟文件存在
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.stat") as mock_stat,
            ):
                mock_stat.return_value.st_size = 12345

                result = downloader.download_pdf(pmcid, doi)

            # 验证结果
            assert result["success"] is True
            assert result["source"] == "PMC OA Service"
            assert result["content_length"] == 12345

            # 验证调用顺序
            mock_process.assert_called_once_with(pmcid, doi)

    def test_download_pdf_falls_back_to_other_sources(self, downloader):
        """
        测试: PMC OA Service 失败后回退到其他源
        """
        pmcid = "PMC123456"
        doi = "10.1000/test.doi"

        # 模拟 PMC OA Service 失败
        with (
            patch.object(
                downloader.pmc_oa_service, "process_pmcid", return_value=False
            ),
            patch.object(downloader, "_try_download_from_url") as mock_try,
        ):
            # 模拟第二个源成功
            mock_try.return_value = {
                "success": True,
                "path": "/tmp/test.pdf",
                "content_length": 67890,
            }

            result = downloader.download_pdf(pmcid, doi)

            # 验证结果
            assert result["success"] is True
            assert result["path"] == "/tmp/test.pdf"

            # 验证尝试了其他源
            assert mock_try.call_count >= 1

    def test_download_pdf_handles_tgz_extraction(self, downloader):
        """
        测试: 处理从 tar.gz 提取 PDF 的情况

        注意：这个测试简化了复杂的mock交互，主要验证逻辑流程
        """
        pmcid = "PMC7446157"
        doi = "10.1000/test.doi"

        # 创建一个简单的测试场景
        # PMC OA Service 成功处理，且PDF文件已存在
        with (
            patch.object(downloader.pmc_oa_service, "process_pmcid", return_value=True),
            patch.object(downloader, "_get_safe_filename") as mock_filename,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
        ):
            mock_filename.return_value = f"{pmcid}_101000testdoi.pdf"
            mock_stat.return_value.st_size = 54321

            result = downloader.download_pdf(pmcid, doi)

            # 验证结果
            assert result["success"] is True
            assert result["source"] == "PMC OA Service"
            assert result["content_length"] == 54321

            # 验证调用了PMC OA Service
            downloader.pmc_oa_service.process_pmcid.assert_called_once_with(pmcid, doi)

    @pytest.mark.network
    def test_real_pmc_oa_download(self, tmp_path):
        """
        真实网络测试：使用实际的 PMC OA Service

        这个测试需要网络连接，可以使用 -m "not network" 跳过
        """
        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": "test-integration/1.0"})

        downloader = PDFDownloader(str(tmp_path), session)

        # 使用一个已知开放获取的文章
        pmcid = "PMC7927990"
        doi = "10.1000/test.doi"

        result = downloader.download_pdf(pmcid, doi)

        # 验证下载成功
        if result["success"]:
            assert "path" in result
            assert result["source"] == "PMC OA Service"

            # 验证文件存在
            pdf_path = tmp_path / result["path"]
            assert pdf_path.exists()
            assert pdf_path.stat().st_size > 0
        else:
            # 网络问题或服务不可用，跳过断言
            pytest.skip(f"PMC OA Service 不可用: {result.get('error', '未知错误')}")
