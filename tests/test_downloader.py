#!/usr/bin/env python3
"""
测试 PDF 下载模块
"""

from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from src.pdfget.downloader import PDFDownloader


class TestPDFDownloader:
    """测试 PDFDownloader 类"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        return Mock()

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        """创建临时目录"""
        return tmp_path / "pdfs"

    @pytest.fixture
    def downloader(self, session, tmp_dir):
        """创建 PDFDownloader 实例"""
        return PDFDownloader(str(tmp_dir), session)

    def test_get_safe_filename(self, downloader):
        """
        测试: 生成安全的文件名
        """
        test_cases = [
            ("PMC123456", "10.1000/test.doi", "PMC123456_101000testdoi.pdf"),
            (
                "PMC123456",
                "10.1000/test.doi?param=value",
                "PMC123456_101000testdoiparamvalue.pdf",
            ),
            ("PMC123456", "doi with spaces", "PMC123456_doiswithspaces.pdf"),
            ("PMC123456", "", "PMC123456_unknown.pdf"),
            ("PMC123456", None, "PMC123456_unknown.pdf"),
            (
                "PMC123456",
                "10.1000/very-long-doi-with-many-parts-should-be-truncated.pdf",
                "PMC123456_101000verylongdoiwithmanypartsshouldbetruncated.pdf",
            ),
        ]

        for pmcid, doi, expected in test_cases:
            result = downloader._get_safe_filename(pmcid, doi)
            assert result == expected

    @patch("builtins.open", new_callable=mock_open, read_data=b"pdf content")
    def test_save_pdf_success(self, mock_file, downloader):
        """
        测试: 成功保存 PDF
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"

        result = downloader._save_pdf(b"pdf content", pmcid, doi)

        assert result["success"] is True
        assert "path" in result
        assert Path(result["path"]).name == "PMC123456_101000test.pdf"

    def test_save_pdf_failure(self, downloader):
        """
        测试: 保存 PDF 失败
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"

        import unittest.mock

        with (
            unittest.mock.patch(
                "builtins.open", side_effect=OSError("Permission denied")
            ),
            unittest.mock.patch("pathlib.Path.mkdir"),
        ):
            result = downloader._save_pdf(b"pdf content", pmcid, doi)

        assert result["success"] is False
        assert "error" in result
        assert "path" in result

    @patch("src.pdfget.downloader.PDFDownloader._save_pdf")
    def test_try_download_from_url_success(self, mock_save, downloader):
        """
        测试: 成功从 URL 下载
        """
        url = "http://example.com/paper.pdf"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        # 模拟 session.get 返回
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.content = b"pdf data"

        downloader.session.get = Mock(return_value=mock_response)
        mock_save.return_value = {"success": True, "path": "/path/to/file.pdf"}

        result = downloader._try_download_from_url(url, pmcid, doi)

        assert result["success"] is True
        assert result["path"] == "/path/to/file.pdf"
        assert result["source_url"] == url
        assert result["content_type"] == "application/pdf"
        assert result["content_length"] == 8

    @patch("src.pdfget.downloader.PDFDownloader._save_pdf")
    def test_try_download_from_url_not_pdf(self, mock_save, downloader):
        """
        测试: URL 返回的不是 PDF
        """
        url = "http://example.com/paper.html"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "text/html"}
        downloader.session.get = Mock(return_value=mock_response)

        result = downloader._try_download_from_url(url, pmcid, doi)

        assert result["success"] is False
        assert "不是 PDF 文件" in result["error"]

    def test_download_pdf_success_first_source(self, downloader):
        """
        测试: 从第一个源成功下载
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"

        # Mock 成功的下载
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/path/to/file.pdf"}
        )

        result = downloader.download_pdf(pmcid, doi)

        assert result["success"] is True
        downloader._try_download_from_url.assert_called_once_with(
            downloader.pdf_sources[0].format(pmcid=pmcid), pmcid, doi
        )

    # 已删除 test_download_pdf_success_second_source，因为现在只有一个下载源

    def test_download_pdf_all_sources_failed(self, downloader):
        """
        测试: 所有源都失败
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"

        downloader._try_download_from_url = Mock(
            return_value={"success": False, "error": "Not found"}
        )

        result = downloader.download_pdf(pmcid, doi)

        assert result["success"] is False
        assert "所有 1 个 PDF 源都失败" in result["error"]
        assert downloader._try_download_from_url.call_count == len(
            downloader.pdf_sources
        )

    def test_check_pdf_exists(self, downloader, tmp_dir):
        """
        测试: 检查 PDF 是否存在
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"
        filename = downloader._get_safe_filename(pmcid, doi)
        file_path = tmp_dir / filename

        # 创建文件
        file_path.touch()

        result = downloader.check_pdf_exists(pmcid, doi)

        assert result is True

    def test_get_pdf_path_exists(self, downloader, tmp_dir):
        """
        测试: PDF 存在时获取路径
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"
        filename = downloader._get_safe_filename(pmcid, doi)
        file_path = tmp_dir / filename

        # 创建文件
        file_path.touch()

        result = downloader.get_pdf_path(pmcid, doi)

        assert result == str(file_path)

    def test_get_pdf_path_not_exists(self, downloader, tmp_dir):
        """
        测试: PDF 不存在时返回 None
        """
        pmcid = "PMC123456"
        doi = "10.1000/test"

        result = downloader.get_pdf_path(pmcid, doi)

        assert result is None

    @patch("src.pdfget.downloader.PDFDownloader.check_pdf_exists")
    @patch("src.pdfget.downloader.PDFDownloader.get_pdf_path")
    def test_download_if_not_exists_cached(
        self, mock_get_path, mock_exists, downloader
    ):
        """
        测试: PDF 已存在时直接返回
        """
        mock_exists.return_value = True
        mock_get_path.return_value = "/path/to/file.pdf"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        result = downloader.download_if_not_exists(pmcid, doi)

        assert result["success"] is True
        assert result["path"] == "/path/to/file.pdf"
        assert result["source"] == "cache"
        assert "PDF 已存在" in result["message"]

    @patch("src.pdfget.downloader.PDFDownloader.check_pdf_exists")
    @patch("src.pdfget.downloader.PDFDownloader.download_pdf")
    def test_download_if_not_exists_not_cached(
        self, mock_download, mock_exists, downloader
    ):
        """
        测试: PDF 不存在时下载
        """
        mock_exists.return_value = False
        mock_download.return_value = {"success": True, "path": "/path/to/file.pdf"}
        pmcid = "PMC123456"
        doi = "10.1000/test"

        result = downloader.download_if_not_exists(pmcid, doi)

        assert result["success"] is True
        mock_download.assert_called_once_with(pmcid, doi)

    def test_list_downloaded_pdfs(self, downloader, tmp_dir):
        """
        测试: 列出已下载的 PDF
        """
        # 创建一些测试文件
        files = [
            ("PMC123456_101000test.pdf", b"content1"),
            ("PMC789012_101001another.pdf", b"content2"),
        ]

        for filename, content in files:
            (tmp_dir / filename).write_bytes(content)

        pdfs = downloader.list_downloaded_pdfs()

        assert len(pdfs) == 2
        assert "PMC123456_101000test.pdf" in pdfs
        assert "PMC789012_101001another.pdf" in pdfs

        info = pdfs["PMC123456_101000test.pdf"]
        assert info["pmcid"] == "PMC123456"
        assert info["doi"] == "10.1000/test"
        assert info["size"] == 8

    @patch("time.time")
    def test_cleanup_old_pdfs(self, mock_time, downloader, tmp_dir):
        """
        测试: 清理旧 PDF 文件
        """
        # 设置时间
        current_time = 1000000  # 基准时间
        mock_time.return_value = current_time

        # 创建测试文件
        old_file = tmp_dir / "old.pdf"
        old_file.write_bytes(b"content")

        # 修改文件时间（30天前）
        import os

        old_time = current_time - (35 * 24 * 3600)  # 35天前
        os.utime(old_file, (old_time, old_time))

        new_file = tmp_dir / "new.pdf"
        new_file.write_bytes(b"content")
        # 保持当前时间

        deleted_count = downloader.cleanup_old_pdfs(max_age_days=30)

        assert deleted_count == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_get_cache_info(self, downloader):
        """
        测试: 获取缓存信息
        """
        # 添加已知的 PDF 源
        downloader.pdf_sources = ["source1", "source2", "source3"]

        # Mock list_downloaded_pdfs
        downloader.list_downloaded_pdfs = Mock(
            return_value={
                "file1.pdf": {"size": 1000},
                "file2.pdf": {"size": 2000},
                "file3.pdf": {"size": 3000},
            }
        )

        info = downloader.get_cache_info()

        assert info["file_count"] == 3
        assert info["total_size_bytes"] == 6000
        assert info["total_size_mb"] == 0.01
        assert info["pdf_sources"] == ["source1", "source2", "source3"]
        assert "output_dir" in info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
