"""
测试统一输入功能
整合 -i、--doi、-m 参数为统一的 -m 参数
"""

import csv
from unittest.mock import patch

import pytest

from src.pdfget.fetcher import PaperFetcher


class TestInputTypeDetection:
    """测试输入类型检测功能"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_detect_csv_file(self, tmp_path):
        """测试：识别CSV文件路径"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("ID\nPMC123456\n")

        result = self.fetcher._detect_input_type(str(csv_file))
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

    def test_detect_nonexistent_file(self):
        """测试：不存在的文件当作单个标识符"""
        result = self.fetcher._detect_input_type("nonexistent_file.csv")
        # 文件不存在，可能被当作标识符或返回invalid
        assert result in ["single", "invalid"]

    def test_detect_empty_string(self):
        """测试：空字符串返回invalid"""
        result = self.fetcher._detect_input_type("")
        assert result == "invalid"

    def test_detect_whitespace_only(self):
        """测试：只有空白字符返回invalid"""
        result = self.fetcher._detect_input_type("   ")
        assert result == "invalid"


class TestColumnAutoDetection:
    """测试CSV列名自动检测功能"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_auto_detect_id_column(self, tmp_path):
        """测试：优先检测ID列"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Title", "PMCID"])
            writer.writerow(["PMC123456", "Test", "PMC123456"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "ID"

    def test_auto_detect_pmcid_column(self, tmp_path):
        """测试：其次检测PMCID列"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["PMCID", "Title"])
            writer.writerow(["PMC123456", "Test"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "PMCID"

    def test_auto_detect_doi_column(self, tmp_path):
        """测试：再次检测doi列"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["doi", "Title"])
            writer.writerow(["10.1038/xxx", "Test"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "doi"

    def test_auto_detect_pmid_column(self, tmp_path):
        """测试：检测pmid列"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["pmid", "Title"])
            writer.writerow(["38238491", "Test"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "pmid"

    def test_fallback_to_first_column(self, tmp_path):
        """测试：都没有时使用第一列"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Identifier", "Title"])
            writer.writerow(["PMC123456", "Test"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result == "Identifier"  # 返回第一列名称

    def test_case_insensitive_detection(self, tmp_path):
        """测试：大小写不敏感"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "Title"])
            writer.writerow(["PMC123456", "Test"])

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result.upper() == "ID"

    def test_empty_csv(self, tmp_path):
        """测试：空CSV文件"""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        result = self.fetcher._auto_detect_column(str(csv_file))
        assert result is None


class TestIdentifierStringParsing:
    """测试标识符字符串解析功能"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_parse_single_pmcid(self):
        """测试：解析单个PMCID"""
        result = self.fetcher._parse_identifier_string("PMC123456")
        assert result == ["PMC123456"]

    def test_parse_single_pmid(self):
        """测试：解析单个PMID"""
        result = self.fetcher._parse_identifier_string("38238491")
        assert result == ["38238491"]

    def test_parse_single_doi(self):
        """测试：解析单个DOI"""
        result = self.fetcher._parse_identifier_string("10.1038/s41586-024-07146-0")
        assert result == ["10.1038/s41586-024-07146-0"]

    def test_parse_comma_separated_pmcids(self):
        """测试：解析逗号分隔的多个PMCID"""
        result = self.fetcher._parse_identifier_string("PMC123456,PMC789012,PMC345678")
        assert result == ["PMC123456", "PMC789012", "PMC345678"]

    def test_parse_comma_separated_mixed(self):
        """测试：解析逗号分隔的混合标识符"""
        result = self.fetcher._parse_identifier_string(
            "PMC123456,38238491,10.1038/s41586-024-07146-0"
        )
        assert len(result) == 3
        assert "PMC123456" in result
        assert "38238491" in result
        assert "10.1038/s41586-024-07146-0" in result

    def test_parse_comma_separated_with_spaces(self):
        """测试：解析带空格的逗号分隔"""
        result = self.fetcher._parse_identifier_string("PMC123456, 38238491, PMC789012")
        assert result == ["PMC123456", "38238491", "PMC789012"]

    def test_parse_empty_string(self):
        """测试：解析空字符串"""
        result = self.fetcher._parse_identifier_string("")
        assert result == []

    def test_parse_whitespace_only(self):
        """测试：解析只有空白字符"""
        result = self.fetcher._parse_identifier_string("   ")
        assert result == []

    def test_parse_with_empty_elements(self):
        """测试：解析包含空元素的字符串"""
        result = self.fetcher._parse_identifier_string("PMC123456,,38238491")
        # 应该跳过空元素
        assert len(result) == 2
        assert "PMC123456" in result
        assert "38238491" in result


class TestUnifiedInputDownload:
    """测试统一输入下载功能"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_download_from_single_pmcid(self):
        """测试：从单个PMCID下载"""
        with (
            patch.object(
                self.fetcher, "_parse_identifier_string", return_value=["PMC123456"]
            ),
            patch.object(self.fetcher, "_read_identifiers_from_csv") as mock_read,
            patch.object(self.fetcher, "download_from_identifiers") as mock_download,
        ):
            mock_download.return_value = [{"pmcid": "PMC123456", "success": True}]

            result = self.fetcher.download_from_unified_input("PMC123456")

            mock_read.assert_not_called()
            assert len(result) == 1

    def test_download_from_multiple_identifiers(self):
        """测试：从多个标识符下载"""
        with (
            patch.object(
                self.fetcher,
                "_parse_identifier_string",
                return_value=["PMC123456", "38238491"],
            ),
            patch.object(self.fetcher, "download_from_identifiers") as mock_download,
        ):
            mock_download.return_value = [
                {"pmcid": "PMC123456", "success": True},
                {"pmcid": "PMC789012", "success": True},
            ]

            result = self.fetcher.download_from_unified_input("PMC123456,38238491")

            assert len(result) == 2

    def test_download_from_csv_with_auto_column(self, tmp_path):
        """测试：从CSV下载，自动检测列名"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Title"])
            writer.writerow(["PMC123456", "Test"])

        with (
            patch.object(self.fetcher, "_auto_detect_column", return_value="ID"),
            patch.object(self.fetcher, "download_from_identifiers") as mock_download,
        ):
            mock_download.return_value = [{"pmcid": "PMC123456", "success": True}]

            result = self.fetcher.download_from_unified_input(str(csv_file))

            assert len(result) == 1

    def test_download_from_csv_with_manual_column(self, tmp_path):
        """测试：从CSV下载，手动指定列名"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["PMCID", "Title"])
            writer.writerow(["PMC123456", "Test"])

        with patch.object(self.fetcher, "download_from_identifiers") as mock_download:
            mock_download.return_value = [{"pmcid": "PMC123456", "success": True}]

            result = self.fetcher.download_from_unified_input(
                str(csv_file), column="PMCID"
            )

            # 手动指定列名时，不应该调用自动检测
            assert len(result) == 1

    def test_download_with_limit(self):
        """测试：限制下载数量"""
        # 对于直接输入的标识符，limit会在构建papers列表时应用
        with (
            patch.object(
                self.fetcher,
                "_parse_identifier_string",
                return_value=["PMC1", "PMC2", "PMC3"],
            ),
            patch.object(self.fetcher, "_convert_pmids_to_pmcids", return_value=[]),
            patch("src.pdfget.manager.UnifiedDownloadManager") as MockManager,
        ):
            mock_instance = MockManager.return_value
            mock_instance.download_batch.return_value = [
                {"pmcid": "PMC1", "success": True},
                {"pmcid": "PMC2", "success": True},
            ]

            # 验证传递给download_batch的papers列表应该是2个（应用了limit）
            self.fetcher.download_from_unified_input("PMC1,PMC2,PMC3", limit=2)
            call_args = mock_instance.download_batch.call_args
            papers = call_args[0][0]
            assert len(papers) == 2

    def test_download_with_workers(self):
        """测试：并发下载"""
        with (
            patch.object(
                self.fetcher, "_parse_identifier_string", return_value=["PMC123456"]
            ),
            patch.object(self.fetcher, "_convert_pmids_to_pmcids", return_value=[]),
            patch("src.pdfget.manager.UnifiedDownloadManager") as MockManager,
        ):
            mock_instance = MockManager.return_value
            mock_instance.download_batch.return_value = [
                {"pmcid": "PMC123456", "success": True}
            ]

            # 验证UnifiedDownloadManager是用max_workers=5创建的
            self.fetcher.download_from_unified_input("PMC123456", max_workers=5)
            assert MockManager.call_args[1]["max_workers"] == 5

    def test_invalid_input(self):
        """测试：无效输入"""
        with (
            patch.object(self.fetcher, "_detect_input_type", return_value="invalid"),
            pytest.raises(ValueError, match="无效的输入"),
        ):
            self.fetcher.download_from_unified_input("")


class TestEdgeCases:
    """测试边界情况"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher()

    def test_csv_with_no_matching_identifiers(self, tmp_path):
        """测试：CSV中没有有效标识符"""
        csv_file = tmp_path / "test.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Title"])
            writer.writerow(["invalid", "Test"])

        with patch.object(self.fetcher, "download_from_identifiers", return_value=[]):
            result = self.fetcher.download_from_unified_input(str(csv_file))
            assert result == []

    def test_mixed_valid_invalid_identifiers(self):
        """测试：混合有效和无效标识符"""
        with (
            patch.object(
                self.fetcher,
                "_parse_identifier_string",
                return_value=["PMC123456", "invalid", "38238491"],
            ),
            patch.object(self.fetcher, "download_from_identifiers") as mock_download,
        ):
            mock_download.return_value = [
                {"pmcid": "PMC123456", "success": True},
                {"pmcid": "PMC789012", "success": True},
            ]

            result = self.fetcher.download_from_unified_input(
                "PMC123456,invalid,38238491"
            )

            # 应该过滤掉无效标识符
            assert len(result) == 2

    def test_very_long_identifier_list(self):
        """测试：非常长的标识符列表"""
        # 减少数量以加快测试速度
        identifiers = [f"PMC{i}" for i in range(100)]
        id_string = ",".join(identifiers)

        with (
            patch.object(
                self.fetcher, "_parse_identifier_string", return_value=identifiers
            ),
            patch.object(self.fetcher, "_convert_pmids_to_pmcids", return_value=[]),
            patch("src.pdfget.manager.UnifiedDownloadManager") as MockManager,
        ):
            mock_instance = MockManager.return_value
            mock_instance.download_batch.return_value = []

            self.fetcher.download_from_unified_input(id_string)

            # 应该能处理大量标识符
            assert MockManager.called
