import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfget.fetcher import PaperFetcher
from pdfget.utils.identifier_utils import IdentifierUtils
from tests.conftest import CSVTestMixin, create_temp_csv_file


class TestArxivIdentifierUtils:
    def test_detect_identifier_type_arxiv(self):
        assert IdentifierUtils.detect_identifier_type("2301.12345") == "arxiv"
        assert IdentifierUtils.detect_identifier_type("2301.12345v2") == "arxiv"
        assert IdentifierUtils.detect_identifier_type("arXiv:2301.12345") == "arxiv"
        assert IdentifierUtils.detect_identifier_type("hep-th/9901001") == "arxiv"

    def test_validate_arxiv_id_valid(self):
        assert IdentifierUtils.validate_arxiv_id("2301.12345")
        assert IdentifierUtils.validate_arxiv_id("2301.12345v2")
        assert IdentifierUtils.validate_arxiv_id("arXiv:2301.12345")
        assert IdentifierUtils.validate_arxiv_id("hep-th/9901001")

    def test_validate_arxiv_id_invalid(self):
        assert not IdentifierUtils.validate_arxiv_id("2301")
        assert not IdentifierUtils.validate_arxiv_id("arXiv:")
        assert not IdentifierUtils.validate_arxiv_id("hep-th9901001")

    def test_normalize_arxiv_id(self):
        assert IdentifierUtils.normalize_arxiv_id("arXiv:2301.12345v2") == "2301.12345v2"
        assert IdentifierUtils.normalize_arxiv_id("2301.12345") == "2301.12345"
        assert IdentifierUtils.normalize_arxiv_id("hep-th/9901001") == "hep-th/9901001"


class TestArxivCSVAndInput(CSVTestMixin):
    def setup_method(self):
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    def test_read_arxiv_only_csv(self, temp_output_dir):
        csv_data = [["ID"], ["2301.12345"], ["arXiv:2301.12346v2"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "arxiv_only.csv")

        result = self.fetcher._read_identifiers_from_csv(str(csv_file), id_column="ID")

        assert len(result["arxiv_ids"]) == 2
        assert "2301.12345" in result["arxiv_ids"]
        assert "2301.12346v2" in result["arxiv_ids"]

    def test_detect_single_arxiv(self):
        assert self.fetcher._detect_input_type("2301.12345") == "single"

    @patch("pdfget.manager.UnifiedDownloadManager")
    def test_download_from_unified_input_routes_arxiv(self, mock_manager_class):
        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.download_batch.return_value = [
            {"arxiv_id": "2301.12345", "success": True, "path": "/tmp/arxiv.pdf"}
        ]

        results = self.fetcher.download_from_unified_input("2301.12345")

        assert results[0]["success"] is True
        papers = mock_manager.download_batch.call_args[0][0]
        assert papers[0]["arxiv_id"] == "2301.12345"

    @patch("pdfget.manager.UnifiedDownloadManager")
    def test_download_from_identifiers_routes_arxiv_csv(self, mock_manager_class, temp_output_dir):
        csv_data = [["ID"], ["arXiv:2301.12345"], ["2301.12346v2"]]
        csv_file = create_temp_csv_file(csv_data, temp_output_dir, "arxiv_download.csv")

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.download_batch.return_value = [
            {"arxiv_id": "2301.12345", "success": True, "path": "/tmp/2301.12345.pdf"},
            {"arxiv_id": "2301.12346v2", "success": True, "path": "/tmp/2301.12346v2.pdf"},
        ]

        results = self.fetcher.download_from_identifiers(str(csv_file), id_column="ID")

        assert len(results) == 2
        papers = mock_manager.download_batch.call_args[0][0]
        assert papers[0]["arxiv_id"] == "2301.12345"
        assert papers[1]["arxiv_id"] == "2301.12346v2"
