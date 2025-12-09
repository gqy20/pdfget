#!/usr/bin/env python3
"""
测试 PMCID CSV 读取功能
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.pdfget.fetcher import PaperFetcher


class TestPMCIDCSV:
    """测试 PMCID CSV 功能"""

    @pytest.fixture
    def fetcher(self):
        """创建 PaperFetcher 实例"""
        return PaperFetcher()

    def test_normalize_pmcid_with_valid_formats(self, fetcher):
        """
        测试: 标准化不同格式的 PMCID
        """
        # 测试各种有效格式
        assert fetcher._normalize_pmcid("123456") == "PMC123456"
        assert fetcher._normalize_pmcid("PMC123456") == "PMC123456"
        assert fetcher._normalize_pmcid("  123456  ") == "PMC123456"
        assert fetcher._normalize_pmcid("\tPMC123456\n") == "PMC123456"

    def test_normalize_pmcid_with_invalid_formats(self, fetcher):
        """
        测试: 处理无效格式的 PMCID
        """
        # 测试各种无效格式
        assert fetcher._normalize_pmcid("") == ""
        assert fetcher._normalize_pmcid("   ") == ""
        assert fetcher._normalize_pmcid("ABC123") == ""
        assert fetcher._normalize_pmcid("PM-123456") == ""
        assert fetcher._normalize_pmcid("123-456") == ""

    def test_read_pmcid_from_csv_simple_list(self, fetcher):
        """
        测试: 读取简单的 PMCID 列表（无标题行）
        """
        # 创建临时 CSV 文件
        csv_content = "PMCID\n123456\n789012\n345678\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == ["PMC123456", "PMC789012", "PMC345678"]
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_with_header(self, fetcher):
        """
        测试: 读取带标题行的 CSV 文件
        """
        csv_content = (
            "PMCID,Title,Author\n123456, Paper 1, Author A\n789012,Paper 2,Author B\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == ["PMC123456", "PMC789012"]
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_with_pmc_prefix(self, fetcher):
        """
        测试: CSV 中已包含 PMC 前缀
        """
        csv_content = "PMCID\nPMC123456\nPMC789012\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == ["PMC123456", "PMC789012"]
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_empty_file(self, fetcher):
        """
        测试: 读取空文件
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == []
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_with_empty_lines(self, fetcher):
        """
        测试: 处理包含空行的 CSV 文件
        """
        csv_content = "PMCID\n123456\n\n789012\n\n\n345678\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == ["PMC123456", "PMC789012", "PMC345678"]
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_with_invalid_entries(self, fetcher):
        """
        测试: 跳过无效的 PMCID 条目
        """
        csv_content = "PMCID\n123456\nINVALID\nPMC789012\nABC123\n345678\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            pmcid_list = fetcher._read_pmcid_from_csv(temp_path)
            assert pmcid_list == ["PMC123456", "PMC789012", "PMC345678"]
        finally:
            Path(temp_path).unlink()

    def test_read_pmcid_from_csv_file_not_found(self, fetcher):
        """
        测试: 文件不存在时抛出异常
        """
        with pytest.raises(FileNotFoundError):
            fetcher._read_pmcid_from_csv("nonexistent.csv")

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv(self, mock_manager_class, fetcher):
        """
        测试: 从 CSV 文件下载论文
        """
        # Mock UnifiedDownloadManager 实例
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock download_batch 返回结果
        mock_manager.download_batch.return_value = [
            {
                "pmcid": "PMC123456",
                "title": "PMCID: PMC123456",
                "source": "direct_pmcid",
                "download_path": "/path/to/pmc123456.pdf",
                "success": True,
            },
            {
                "pmcid": "PMC789012",
                "title": "PMCID: PMC789012",
                "source": "direct_pmcid",
                "download_path": "/path/to/pmc789012.pdf",
                "success": True,
            },
        ]

        # 创建临时 CSV 文件
        csv_content = "PMCID\n123456\n789012\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # 调用下载方法
            results = fetcher.download_from_pmcid_csv(
                temp_path, limit=None, max_workers=10
            )

            # 验证结果
            assert len(results) == 2

            # 验证创建了 UnifiedDownloadManager
            mock_manager_class.assert_called_once()

            # 验证调用了 download_batch
            mock_manager.download_batch.assert_called_once()

            # 获取 download_batch 的调用参数
            call_args = mock_manager.download_batch.call_args
            papers = call_args[0][0]  # 第一个位置参数

            # 验证论文格式
            assert len(papers) == 2
            assert papers[0]["pmcid"] == "PMC123456"
            assert papers[0]["title"] == "PMCID: PMC123456"
            assert papers[0]["source"] == "direct_pmcid"
            assert papers[1]["pmcid"] == "PMC789012"
            assert papers[1]["title"] == "PMCID: PMC789012"
            assert papers[1]["source"] == "direct_pmcid"

        finally:
            Path(temp_path).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv_with_limit(self, mock_manager_class, fetcher):
        """
        测试: 带限制的下载
        """
        # Mock UnifiedDownloadManager 实例
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock download_batch 返回结果
        mock_manager.download_batch.return_value = []

        # 创建包含多个 PMCID 的 CSV 文件
        csv_content = "PMCID\n123456\n789012\n345678\n901234\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            # 限制只下载前 2 个
            fetcher.download_from_pmcid_csv(temp_path, limit=2)

            # 验证只传递了前 2 个论文
            call_args = mock_manager.download_batch.call_args
            papers = call_args[0][0]
            assert len(papers) == 2
            assert papers[0]["pmcid"] == "PMC123456"
            assert papers[1]["pmcid"] == "PMC789012"

        finally:
            Path(temp_path).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv_empty_file(self, mock_manager_class, fetcher):
        """
        测试: 从空 CSV 文件下载
        """
        # Mock UnifiedDownloadManager 实例
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock download_batch 返回结果
        mock_manager.download_batch.return_value = []

        # 创建空 CSV 文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            results = fetcher.download_from_pmcid_csv(temp_path)

            # 验证没有创建 UnifiedDownloadManager（因为空文件）
            mock_manager_class.assert_not_called()

            # 验证没有调用 download_batch
            mock_manager.download_batch.assert_not_called()

            # 验证返回空结果
            assert results == []

        finally:
            Path(temp_path).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv_only_invalid_entries(
        self, mock_manager_class, fetcher
    ):
        """
        测试: CSV 文件只包含无效条目
        """
        # Mock UnifiedDownloadManager 实例
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Mock download_batch 返回结果
        mock_manager.download_batch.return_value = []

        # 创建只包含无效条目的 CSV 文件
        csv_content = "INVALID\nABC123\nPM-\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            results = fetcher.download_from_pmcid_csv(temp_path)

            # 验证没有创建 UnifiedDownloadManager（因为空文件）
            mock_manager_class.assert_not_called()

            # 验证没有调用 download_batch
            mock_manager.download_batch.assert_not_called()

            # 验证返回空结果
            assert results == []

        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
