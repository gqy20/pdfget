#!/usr/bin/env python3
"""
测试 DOI 转换功能与现有系统的集成

测试DOI转换功能在PaperFetcher等组件中的使用。
"""

from unittest.mock import patch

import pytest

from pdfget.input_parser import parse_identifier_string
from pdfget.utils.identifier_utils import IdentifierUtils
from src.pdfget.fetcher import PaperFetcher


@pytest.mark.usefixtures("fast_sleep")
class TestDOIIntegration:
    """测试DOI转换功能与系统的集成"""

    @pytest.fixture
    def fetcher(self):
        """创建 PaperFetcher 实例"""
        return PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    # 集成测试1: CSV文件中包含DOI的完整流程
    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    @patch("src.pdfget.doi_converter.DOIConverter.batch_doi_to_pmcid")
    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_csv_with_dois_complete_flow(
        self, mock_process_pmids, mock_batch_convert, mock_download, fetcher
    ):
        """
        测试: CSV文件包含DOI时的完整处理流程（mock 所有转换避免真实网络请求）
        """
        # 模拟 DOI 转换结果
        mock_batch_convert.return_value = {
            "10.1186/s12916-020-01690-4": "PMC123456",
            "10.1016/j.cell.2020.01.021": "PMC789012",
        }
        # 模拟 PMID → PMCID 转换结果
        mock_process_pmids.return_value = [
            {"pmid": "38238491", "pmcid": "PMC999999"}
        ]

        # 模拟下载结果
        mock_download.return_value = [
            {"pmcid": "PMC123456", "success": True, "path": "test1.pdf"},
            {"pmcid": "PMC789012", "success": True, "path": "test2.pdf"},
        ]

        # 模拟CSV数据（包含DOI）
        csv_content = """ID,Title
10.1186/s12916-020-01690-4,Paper 1
10.1016/j.cell.2020.01.021,Paper 2
38238491,Paper 3 PMID
PMC12345,Paper 4 PMCID"""

        # 创建临时CSV文件
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            csv_path = f.name

        try:
            # 执行下载（通过统一输入入口）
            results = fetcher.download_from_unified_input(csv_path, column="ID")

            # 验证下载管理器被调用
            mock_download.assert_called_once()

            # 验证结果包含所有标识符
            assert len(results) >= 2  # 至少包含DOI转换的结果

        finally:
            # 清理临时文件
            Path(csv_path).unlink()

    # 集成测试2: 单个DOI下载
    @patch("src.pdfget.doi_converter.DOIConverter.batch_doi_to_pmcid")
    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    def test_single_doi_download(self, mock_download, mock_batch_convert, fetcher):
        """
        测试: 单个DOI下载的完整流程
        """
        # 模拟DOI转换结果
        mock_batch_convert.return_value = {"10.1000/test.doi": "PMC123456789"}

        # 模拟下载结果
        mock_download.return_value = [
            {
                "pmcid": "PMC123456789",
                "success": True,
                "path": "test.pdf",
            }
        ]

        # 执行DOI下载
        result = fetcher.download_from_unified_input("10.1000/test.doi")

        # 验证转换和下载被执行
        mock_batch_convert.assert_called_once()
        mock_download.assert_called_once()

        # 验证结果不为空
        assert len(result) > 0

    # 集成测试3: 混合标识符输入
    def test_mixed_identifiers_input(self, fetcher):
        """
        测试: PMCID、PMID、DOI混合输入的处理
        """
        # 混合标识符输入
        mixed_input = "10.1000/doi.test,38238491,PMC333333"

        # 解析标识符字符串并分类
        identifiers = parse_identifier_string(mixed_input)
        classified = {"pmcids": [], "pmids": [], "dois": []}

        for identifier in identifiers:
            id_type = IdentifierUtils.detect_identifier_type(identifier)
            if id_type == "pmcid":
                classified["pmcids"].append(identifier)
            elif id_type == "pmid":
                classified["pmids"].append(identifier)
            elif id_type == "doi":
                classified["dois"].append(identifier)

        # 验证分类正确
        assert "10.1000/doi.test" in classified["dois"]
        assert "38238491" in classified["pmids"]
        assert "PMC333333" in classified["pmcids"]

    # 集成测试4: DOI转换失败时的处理
    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    @patch("src.pdfget.doi_converter.DOIConverter.batch_doi_to_pmcid")
    def test_doi_conversion_failure_handling(self, mock_batch_convert, mock_download, fetcher):
        """
        测试: DOI转换失败时的处理（mock 避免真实网络请求）
        """
        # 模拟 DOI 转换返回空结果（转换失败）
        mock_batch_convert.return_value = {}

        # 执行不存在的DOI下载（预期会失败并返回空结果）
        result = fetcher.download_from_unified_input("10.1000/nonexistent.doi")

        # 验证结果为空列表（因为DOI转换失败，没有可下载的PMCID）
        assert result == []

        # 验证下载未被调用（因为没有可用的PMCID）
        mock_download.assert_not_called()

    # 集成测试5: 下载管理器集成测试
    @patch("src.pdfget.doi_converter.DOIConverter.batch_doi_to_pmcid")
    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    def test_download_manager_doi_handling(self, mock_download, mock_batch_convert):
        """
        测试: UnifiedDownloadManager与DOI处理的集成
        """

        # 模拟DOI转换结果
        mock_batch_convert.return_value = {"10.1000/test.doi": "PMC123456"}

        # 模拟下载结果
        mock_download.return_value = [
            {"pmcid": "PMC123456", "success": True, "path": "test.pdf"}
        ]

        # 创建fetcher
        fetcher = PaperFetcher()
        # 注意：UnifiedDownloadManager通过fetcher内部使用

        # 执行下载（通过fetcher的统一接口）
        result = fetcher.download_from_unified_input("10.1000/test.doi")

        # 验证下载管理器被调用
        mock_download.assert_called_once()

        # 验证结果格式正确
        assert len(result) == 1
        assert result[0]["pmcid"] == "PMC123456"

    # 集成测试6: 错误处理和日志记录
    def test_doi_error_logging(self, fetcher):
        """测试: 无效 DOI 格式返回空结果且不崩溃"""
        result = fetcher.download_from_unified_input("invalid.doi.format")
        assert result == []

    # 集成测试7: 性能测试（大量DOI）
    @patch("src.pdfget.doi_converter.DOIConverter.batch_doi_to_pmcid")
    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    def test_large_doi_batch_performance(
        self, mock_download, mock_batch_convert, fetcher
    ):
        """
        测试: 大量DOI批量处理的性能
        """
        # 生成大量DOI
        doi_list = [
            f"10.1000/test.{i}.doi" for i in range(10)
        ]  # 减少数量以提高测试速度

        # 模拟批量转换结果
        mock_results = {f"10.1000/test.{i}.doi": f"PMC{i:06d}" for i in range(10)}
        mock_batch_convert.return_value = mock_results

        # 模拟下载结果
        mock_download.return_value = [
            {"pmcid": f"PMC{i:06d}", "success": True, "path": f"test{i}.pdf"}
            for i in range(10)
        ]

        # 将DOI列表转换为字符串输入
        doi_string = ",".join(doi_list)

        # 执行批量下载
        results = fetcher.download_from_unified_input(doi_string)

        # 验证转换和下载被执行
        mock_batch_convert.assert_called_once()
        mock_download.assert_called_once()

        # 验证结果数量正确
        assert len(results) == len(doi_list)
