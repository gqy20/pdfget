"""Tests for the arXiv branch of PDFDownloader.download_paper."""

import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfget.downloader import PDFDownloader


class TestArxivDownloader:
    def test_download_paper_routes_arxiv(self, tmp_path):
        """``download_paper`` should dispatch arXiv records through ``_via_arxiv``."""
        session = Mock()
        downloader = PDFDownloader(str(tmp_path / "pdfs"), session)
        downloader._via_arxiv = Mock(
            return_value={"success": True, "path": "/path/to/arxiv.pdf"}
        )

        paper = {"arxiv_id": "2301.12345", "title": "Test arXiv paper"}
        result = downloader.download_paper(paper)

        assert result["success"] is True
        downloader._via_arxiv.assert_called_once()
        assert downloader._via_arxiv.call_args.args[0]["arxiv_id"] == "2301.12345"

    def test_via_arxiv_strips_prefix(self, tmp_path):
        session = Mock()
        downloader = PDFDownloader(str(tmp_path / "pdfs"), session)
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/p.pdf"}
        )

        result = downloader._via_arxiv({"arxiv_id": "arxiv:2301.12345"})

        assert result["arxiv_id"] == "2301.12345"
        assert result["source"] == "arxiv"
        downloader._try_download_from_url.assert_called_once_with(
            "https://arxiv.org/pdf/2301.12345.pdf", "2301.12345", ""
        )
