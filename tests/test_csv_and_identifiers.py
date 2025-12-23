#!/usr/bin/env python3
"""
统一的CSV和标识符处理测试
整合了原本分散在多个文件中的CSV读取、标识符检测和转换功能
"""

from unittest.mock import Mock, patch

import pytest

from src.pdfget.fetcher import PaperFetcher
from tests.conftest import CSVTestMixin, create_temp_csv_file


class TestCSVIdentifierReading(CSVTestMixin):
    """测试从 CSV 读取混合标识符（从 test_identifier_download.py 整合）"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    def test_read_pmcid_only_csv(self, temp_output_dir):
        """测试：读取仅包含 PMCID 的 CSV"""
        # 创建CSV数据
        csv_data = [["ID"], ["PMC10851947"], ["PMC10851948"], ["PMC10851949"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "pmcid_only.csv")

        result = self.fetcher._read_identifiers_from_csv(str(csv_file), id_column="ID")

        assert len(result["pmcids"]) == 3
        assert len(result["pmids"]) == 0
        assert len(result["dois"]) == 0
        assert "PMC10851947" in result["pmcids"]

    def test_read_pmid_only_csv(self, temp_output_dir):
        """测试：读取仅包含 PMID 的 CSV"""
        # 创建CSV数据
        csv_data = [["ID"], ["38238491"], ["38238492"], ["38238493"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "pmid_only.csv")

        result = self.fetcher._read_identifiers_from_csv(str(csv_file), id_column="ID")

        assert len(result["pmids"]) == 3
        assert len(result["pmcids"]) == 0
        assert len(result["dois"]) == 0
        assert "38238491" in result["pmids"]

    def test_read_doi_only_csv(self, temp_output_dir):
        """测试：读取仅包含 DOI 的 CSV"""
        identifiers = ["10.1038/s41586-024-07146-0", "10.1000/test1", "10.1000/test2"]
        # 创建CSV数据
        csv_data = [["ID"], [identifiers[0]], [identifiers[1]], [identifiers[2]]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "doi_only.csv")

        result = self.fetcher._read_identifiers_from_csv(str(csv_file), id_column="ID")

        assert len(result["dois"]) == 3
        assert len(result["pmcids"]) == 0
        assert len(result["pmids"]) == 0

    def test_read_mixed_identifiers_csv(self, csv_file_with_mixed_ids):
        """测试：读取混合标识符的 CSV（使用fixture）"""
        result = self.fetcher._read_identifiers_from_csv(
            str(csv_file_with_mixed_ids), id_column="ID"
        )

        assert len(result["pmcids"]) == 2
        assert len(result["pmids"]) == 1
        assert len(result["dois"]) == 1
        assert "PMC123456" in result["pmcids"]
        assert "38238491" in result["pmids"]
        assert "10.1038/s41586-024-07146-0" in result["dois"]

    def test_read_csv_with_empty_lines(self, temp_output_dir):
        """测试：处理包含空行的 CSV"""
        csv_data = [
            ["ID"],
            ["PMC10851947"],
            [""],  # 空行
            ["38238491"],
            [""],  # 空行
        ]
        csv_file = create_temp_csv_file(
            csv_data, temp_output_dir, "with_empty_lines.csv"
        )

        result = self.fetcher._read_identifiers_from_csv(str(csv_file), id_column="ID")

        # 应该跳过空行
        assert len(result["pmcids"]) == 1
        assert len(result["pmids"]) == 1


class TestInputTypeDetection(CSVTestMixin):
    """测试输入类型检测功能（从 test_unified_input.py 整合）"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_detect_csv_file(self, csv_file_with_pmcids):
        """测试：识别CSV文件路径"""
        result = self.fetcher._detect_input_type(str(csv_file_with_pmcids))
        assert result == "csv_file"

    def test_detect_single_pmcid(self):
        """测试：识别单个PMCID"""
        result = self.fetcher._detect_input_type("PMC123456")
        assert result == "single"

    def test_detect_single_pmid(self):
        """测试：识别单个PMID"""
        result = self.fetcher._detect_input_type("38238491")
        assert result == "single"

    def test_detect_single_doi(self):
        """测试：识别单个DOI"""
        result = self.fetcher._detect_input_type("10.1038/s41586-024-07146-0")
        assert result == "single"

    def test_detect_multiple_identifiers(self):
        """测试：识别逗号分隔的多个标识符"""
        result = self.fetcher._detect_input_type("PMC123456,38238491,10.1038/xxx")
        assert result == "multiple"

    def test_detect_multiple_with_spaces(self):
        """测试：识别带空格的多个标识符"""
        result = self.fetcher._detect_input_type("PMC123456, 38238491, 10.1038/xxx")
        assert result == "multiple"

    def test_detect_empty_string(self):
        """测试：空字符串返回invalid"""
        result = self.fetcher._detect_input_type("")
        assert result == "invalid"

    def test_detect_whitespace_only(self):
        """测试：只有空白字符返回invalid"""
        result = self.fetcher._detect_input_type("   ")
        assert result == "invalid"


class TestColumnAutoDetection(CSVTestMixin):
    """测试CSV列名自动检测功能（从 test_unified_input.py 整合）"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_auto_detect_id_column(self, temp_output_dir):
        """测试：优先检测ID列"""
        csv_data = [["ID", "Title", "PMCID"], ["PMC123456", "Test", "PMC123456"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "id_priority.csv")

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "ID"

    def test_auto_detect_pmcid_column(self, temp_output_dir):
        """测试：其次检测PMCID列"""
        csv_data = [["PMCID", "Title"], ["PMC123456", "Test"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "pmcid_column.csv")

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "PMCID"

    def test_auto_detect_doi_column(self, temp_output_dir):
        """测试：再次检测doi列"""
        csv_data = [["doi", "Title"], ["10.1038/xxx", "Test"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "doi_column.csv")

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "doi"

    def test_auto_detect_pmid_column(self, temp_output_dir):
        """测试：检测pmid列"""
        csv_data = [["pmid", "Title"], ["38238491", "Test"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "pmid_column.csv")

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "pmid"

    def test_case_insensitive_detection(self, temp_output_dir):
        """测试：大小写不敏感"""
        csv_data = [["id", "Title"], ["PMC123456", "Test"]]
        csv_file = create_temp_csv_file(
            csv_data, temp_output_dir, "case_insensitive.csv"
        )

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result.upper() == "ID"


class TestPMIDConversion(CSVTestMixin):
    """测试 PMID 到 PMCID 的转换集成（从 test_identifier_download.py 整合）"""

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


class TestCSVDowloadIntegration(CSVTestMixin):
    """测试CSV下载集成功能（从 test_pmcid_csv.py 和其他文件整合）"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv(self, mock_manager_class, csv_file_with_pmcids):
        """测试：从 PMCID CSV 文件下载论文"""
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

        # 调用下载方法
        results = self.fetcher.download_from_pmcid_csv(
            str(csv_file_with_pmcids), limit=None, max_workers=10
        )

        # 验证结果
        assert len(results) == 2

        # 验证创建了 UnifiedDownloadManager
        mock_manager_class.assert_called_once()

        # 验证调用了 download_batch
        mock_manager.download_batch.assert_called_once()

    @patch("src.pdfget.manager.UnifiedDownloadManager")
    def test_download_from_pmcid_csv_with_limit(
        self, mock_manager_class, temp_output_dir
    ):
        """测试：带限制的下载"""
        # Mock UnifiedDownloadManager 实例
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.download_batch.return_value = []

        # 创建包含多个 PMCID 的 CSV 文件
        csv_data = [["ID"], ["123456"], ["789012"], ["345678"], ["901234"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "many_pmcids.csv")

        try:
            # 限制只下载前 2 个
            self.fetcher.download_from_pmcid_csv(str(csv_file), limit=2)

            # 验证只传递了前 2 个论文
            call_args = mock_manager.download_batch.call_args
            papers = call_args[0][0]
            assert len(papers) == 2
            assert papers[0]["pmcid"] == "PMC123456"
            assert papers[1]["pmcid"] == "PMC789012"
        finally:
            csv_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
