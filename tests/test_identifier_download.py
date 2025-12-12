"""
测试基于混合标识符（PMCID/PMID/DOI）下载功能
"""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pdfget.fetcher import PaperFetcher


class TestIdentifierDetection:
    """测试标识符类型自动检测"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    def test_detect_pmcid(self):
        """测试：检测 PMCID 格式"""
        assert self.fetcher._detect_id_type("PMC10851947") == "pmcid"
        assert self.fetcher._detect_id_type("PMC123456") == "pmcid"
        assert self.fetcher._detect_id_type(" PMC10851947 ") == "pmcid"  # 带空格

    def test_detect_pmid(self):
        """测试：检测 PMID 格式（纯数字，6-10位）"""
        assert self.fetcher._detect_id_type("38238491") == "pmid"
        assert self.fetcher._detect_id_type("12345678") == "pmid"
        assert self.fetcher._detect_id_type(" 38238491 ") == "pmid"  # 带空格

    def test_detect_doi(self):
        """测试：检测 DOI 格式"""
        assert self.fetcher._detect_id_type("10.1038/s41586-024-07146-0") == "doi"
        assert self.fetcher._detect_id_type("10.1000/test") == "doi"
        assert self.fetcher._detect_id_type(" 10.1000/test ") == "doi"  # 带空格

    def test_detect_invalid(self):
        """测试：检测无效格式"""
        assert self.fetcher._detect_id_type("") == "unknown"
        assert self.fetcher._detect_id_type("invalid") == "unknown"
        assert self.fetcher._detect_id_type("12345") == "unknown"  # 太短
        assert self.fetcher._detect_id_type("12345678901") == "unknown"  # 太长

    def test_detect_edge_cases(self):
        """测试：边界情况"""
        # 最小有效 PMID (6位)
        assert self.fetcher._detect_id_type("123456") == "pmid"
        # 最大有效 PMID (10位)
        assert self.fetcher._detect_id_type("1234567890") == "pmid"
        # PMC 后缀无数字
        assert self.fetcher._detect_id_type("PMC") == "unknown"
        # DOI 前缀但格式不完整
        assert self.fetcher._detect_id_type("10.") == "unknown"


class TestCSVIdentifierReading:
    """测试从 CSV 读取混合标识符"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    def _create_temp_csv(self, data: list[list[str]]) -> str:
        """创建临时 CSV 文件"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerows(data)
            return f.name

    def test_read_pmcid_only_csv(self):
        """测试：读取仅包含 PMCID 的 CSV"""
        csv_data = [
            ["PMCID"],
            ["PMC10851947"],
            ["PMC10851948"],
            ["PMC10851949"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(
                csv_file, id_column="PMCID"
            )

            assert len(result["pmcids"]) == 3
            assert len(result["pmids"]) == 0
            assert len(result["dois"]) == 0
            assert "PMC10851947" in result["pmcids"]
            assert "PMC10851948" in result["pmcids"]
            assert "PMC10851949" in result["pmcids"]
        finally:
            Path(csv_file).unlink()

    def test_read_pmid_only_csv(self):
        """测试：读取仅包含 PMID 的 CSV"""
        csv_data = [
            ["PMID"],
            ["38238491"],
            ["38238492"],
            ["38238493"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(csv_file, id_column="PMID")

            assert len(result["pmids"]) == 3
            assert len(result["pmcids"]) == 0
            assert len(result["dois"]) == 0
            assert "38238491" in result["pmids"]
        finally:
            Path(csv_file).unlink()

    def test_read_doi_only_csv(self):
        """测试：读取仅包含 DOI 的 CSV"""
        csv_data = [
            ["DOI"],
            ["10.1038/s41586-024-07146-0"],
            ["10.1000/test1"],
            ["10.1000/test2"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(csv_file, id_column="DOI")

            assert len(result["dois"]) == 3
            assert len(result["pmcids"]) == 0
            assert len(result["pmids"]) == 0
            assert "10.1038/s41586-024-07146-0" in result["dois"]
        finally:
            Path(csv_file).unlink()

    def test_read_mixed_identifiers_csv(self):
        """测试：读取混合标识符的 CSV"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],
            ["38238491"],
            ["10.1038/s41586-024-07146-0"],
            ["PMC10851948"],
            ["38238492"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(csv_file, id_column="ID")

            assert len(result["pmcids"]) == 2
            assert len(result["pmids"]) == 2
            assert len(result["dois"]) == 1
            assert "PMC10851947" in result["pmcids"]
            assert "38238491" in result["pmids"]
            assert "10.1038/s41586-024-07146-0" in result["dois"]
        finally:
            Path(csv_file).unlink()

    def test_read_csv_with_empty_lines(self):
        """测试：处理包含空行的 CSV"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],
            [""],  # 空行
            ["38238491"],
            [""],  # 空行
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(csv_file, id_column="ID")

            # 应该跳过空行
            assert len(result["pmcids"]) == 1
            assert len(result["pmids"]) == 1
        finally:
            Path(csv_file).unlink()

    def test_read_csv_with_invalid_identifiers(self):
        """测试：处理包含无效标识符的 CSV"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],  # 有效
            ["invalid"],  # 无效
            ["38238491"],  # 有效
            ["12345"],  # 无效（太短）
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(csv_file, id_column="ID")

            # 只保留有效的标识符
            assert len(result["pmcids"]) == 1
            assert len(result["pmids"]) == 1
            assert len(result["dois"]) == 0
        finally:
            Path(csv_file).unlink()

    def test_read_csv_file_not_found(self):
        """测试：CSV 文件不存在"""
        with pytest.raises(FileNotFoundError):
            self.fetcher._read_identifiers_from_csv("nonexistent.csv")

    def test_read_csv_custom_column_name(self):
        """测试：自定义列名"""
        csv_data = [
            ["CustomID"],
            ["PMC10851947"],
            ["38238491"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        try:
            result = self.fetcher._read_identifiers_from_csv(
                csv_file, id_column="CustomID"
            )

            assert len(result["pmcids"]) == 1
            assert len(result["pmids"]) == 1
        finally:
            Path(csv_file).unlink()


class TestPMIDConversion:
    """测试 PMID 到 PMCID 的转换集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_convert_pmids_to_pmcids(self, mock_process):
        """测试：PMID 批量转换为 PMCID"""
        # 模拟转换结果
        mock_process.return_value = [
            {"pmid": "38238491", "pmcid": "PMC10851947"},
            {"pmid": "38238492", "pmcid": "PMC10851948"},
            {"pmid": "38238493", "pmcid": ""},  # 无 PMCID
        ]

        pmids = ["38238491", "38238492", "38238493"]
        result = self.fetcher._convert_pmids_to_pmcids(pmids)

        # 验证调用
        assert mock_process.called
        # 验证返回的 PMCID 列表
        assert len(result) == 2  # 只返回有 PMCID 的
        assert "PMC10851947" in result
        assert "PMC10851948" in result

    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_convert_empty_pmids(self, mock_process):
        """测试：空 PMID 列表"""
        result = self.fetcher._convert_pmids_to_pmcids([])

        # 应该不调用 API
        assert not mock_process.called
        assert len(result) == 0

    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_convert_pmids_all_fail(self, mock_process):
        """测试：所有 PMID 都无法转换"""
        mock_process.return_value = [
            {"pmid": "38238491", "pmcid": ""},
            {"pmid": "38238492", "pmcid": ""},
        ]

        pmids = ["38238491", "38238492"]
        result = self.fetcher._convert_pmids_to_pmcids(pmids)

        assert len(result) == 0  # 无有效 PMCID


class TestIdentifierDownloadIntegration:
    """测试完整的标识符下载集成流程"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    def _create_temp_csv(self, data: list[list[str]]) -> str:
        """创建临时 CSV 文件"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".csv", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerows(data)
            return f.name

    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_download_from_mixed_csv(self, mock_convert, mock_download):
        """测试：从混合标识符 CSV 下载"""
        # 准备测试数据
        csv_data = [
            ["ID"],
            ["PMC10851947"],  # PMCID - 直接使用
            ["38238491"],  # PMID - 需要转换
            ["10.1038/test"],  # DOI - 需要搜索
        ]
        csv_file = self._create_temp_csv(csv_data)

        # 模拟 PMID 转换
        mock_convert.return_value = [
            {"pmid": "38238491", "pmcid": "PMC10851948", "title": "Test 2"}
        ]

        # 模拟下载结果
        mock_download.return_value = [
            {"pmcid": "PMC10851947", "success": True, "path": "/path/to/pdf1.pdf"},
            {"pmcid": "PMC10851948", "success": True, "path": "/path/to/pdf2.pdf"},
        ]

        try:
            # 执行下载
            results = self.fetcher.download_from_identifiers(
                csv_file, id_column="ID", limit=None, max_workers=1
            )

            # 验证结果
            assert len(results) == 2
            assert all(r["success"] for r in results)

            # 验证调用了转换
            assert mock_convert.called

            # 验证调用了下载
            assert mock_download.called
        finally:
            Path(csv_file).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    def test_download_pmcid_only_no_conversion(self, mock_download):
        """测试：仅 PMCID 时不需要转换"""
        csv_data = [
            ["PMCID"],
            ["PMC10851947"],
            ["PMC10851948"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        mock_download.return_value = [
            {"pmcid": "PMC10851947", "success": True},
            {"pmcid": "PMC10851948", "success": True},
        ]

        try:
            results = self.fetcher.download_from_identifiers(
                csv_file, id_column="PMCID", limit=None, max_workers=1
            )

            # 应该直接下载，不转换
            assert len(results) == 2
        finally:
            Path(csv_file).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_download_with_limit(self, mock_convert, mock_download):
        """测试：限制下载数量"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],
            ["PMC10851948"],
            ["PMC10851949"],
            ["PMC10851950"],
        ]
        csv_file = self._create_temp_csv(csv_data)

        mock_download.return_value = [
            {"pmcid": "PMC10851947", "success": True},
            {"pmcid": "PMC10851948", "success": True},
        ]

        try:
            # 只下载前 2 篇
            results = self.fetcher.download_from_identifiers(
                csv_file, id_column="ID", limit=2, max_workers=1
            )

            assert len(results) == 2
        finally:
            Path(csv_file).unlink()

    @patch("src.pdfget.manager.UnifiedDownloadManager.download_batch")
    @patch("src.pdfget.pmcid.PMCIDRetriever.process_papers")
    def test_download_with_conversion_failure(self, mock_convert, mock_download):
        """测试：部分 PMID 转换失败"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],  # PMCID - 有效
            ["38238491"],  # PMID - 转换成功
            ["38238492"],  # PMID - 转换失败
        ]
        csv_file = self._create_temp_csv(csv_data)

        # 模拟转换：只有一个成功
        mock_convert.return_value = [
            {"pmid": "38238491", "pmcid": "PMC10851948", "title": "Test"},
            {"pmid": "38238492", "pmcid": "", "title": "Test"},  # 转换失败
        ]

        mock_download.return_value = [
            {"pmcid": "PMC10851947", "success": True},
            {"pmcid": "PMC10851948", "success": True},
        ]

        try:
            results = self.fetcher.download_from_identifiers(
                csv_file, id_column="ID", limit=None, max_workers=1
            )

            # 应该只下载 2 个（1个直接 PMCID + 1个转换成功的）
            assert len(results) == 2
        finally:
            Path(csv_file).unlink()
