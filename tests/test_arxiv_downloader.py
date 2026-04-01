import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfget.downloader import PDFDownloader


class TestArxivDownloader:
    def test_download_arxiv_pdf_success(self, tmp_path):
        session = Mock()
        downloader = PDFDownloader(str(tmp_path / "pdfs"), session)
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/path/to/arxiv.pdf"}
        )

        result = downloader.download_arxiv_pdf("2301.12345v2")

        assert result["success"] is True
        downloader._try_download_from_url.assert_called_once_with(
            "https://arxiv.org/pdf/2301.12345v2.pdf",
            "2301.12345v2",
            "",
        )

    def test_download_paper_routes_arxiv(self, tmp_path):
        session = Mock()
        downloader = PDFDownloader(str(tmp_path / "pdfs"), session)
        downloader.download_arxiv_pdf = Mock(
            return_value={"success": True, "path": "/path/to/arxiv.pdf"}
        )

        paper = {"arxiv_id": "2301.12345", "title": "Test arXiv paper"}
        result = downloader.download_paper(paper)

        assert result["success"] is True
        downloader.download_arxiv_pdf.assert_called_once_with("2301.12345")
