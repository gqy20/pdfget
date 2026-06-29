"""Tests for the single-entry ``PDFDownloader.download_paper`` contract.

Storage-level behaviour (path, listing, cleanup, cache info) is covered by
``tests/test_storage.py``; here we only assert the protocol/dispatch layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from pdfget.downloader import PDFDownloader


class TestPDFDownloader:
    """Strategy + dispatch behaviour of PDFDownloader."""

    @pytest.fixture
    def session(self):
        return Mock()

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path / "pdfs"

    @pytest.fixture
    def downloader(self, session, tmp_dir):
        return PDFDownloader(str(tmp_dir), session)

    # ---- URL → file streaming -------------------------------------------------

    def test_try_download_from_url_success(self, downloader):
        url = "http://example.com/paper.pdf"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.iter_content.return_value = [b"pdf ", b"data"]
        downloader.session.get = Mock(return_value=mock_response)

        result = downloader._try_download_from_url(url, pmcid, doi)

        assert result["success"] is True
        assert Path(result["path"]).read_bytes() == b"pdf data"
        assert result["source_url"] == url
        assert result["source"] == "url"
        assert result["stage"] == "save_file"
        assert result["content_type"] == "application/pdf"
        assert result["content_length"] == 8
        mock_response.iter_content.assert_called_once_with(chunk_size=8192)

    def test_try_download_from_url_empty_pdf(self, downloader):
        url = "http://example.com/paper.pdf"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.iter_content.return_value = []
        downloader.session.get = Mock(return_value=mock_response)

        result = downloader._try_download_from_url(url, pmcid, doi)

        assert result["success"] is False
        assert result["error"] == "PDF 内容为空"
        assert result["stage"] == "save_file"
        assert not Path(result["path"]).exists()

    def test_try_download_from_url_not_pdf(self, downloader):
        url = "http://example.com/paper.html"
        pmcid = "PMC123456"
        doi = "10.1000/test"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "text/html"}
        downloader.session.get = Mock(return_value=url)

        # patch properly — mock_response returned by session.get
        downloader.session.get.return_value = mock_response

        result = downloader._try_download_from_url(url, pmcid, doi)

        assert result["success"] is False
        assert "不是 PDF 文件" in result["error"]
        assert result["stage"] == "validate_response"

    # ---- _via_pmcid dispatch --------------------------------------------------

    def test_via_pmcid_first_source_success(self, downloader):
        pmcid = "PMC123456"
        doi = "10.1000/test"

        # Europa PMC URL fetcher succeeds on first call
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/path/to/file.pdf"}
        )

        result = downloader.download_paper({"pmcid": pmcid, "doi": doi})

        assert result["success"] is True
        assert result["source"] == "europe_pmc"
        assert [attempt["source"] for attempt in result["attempts"]] == [
            "PMC OA Service",
            "europe_pmc",
        ]
        _, url_template = downloader.pdf_sources[0]
        downloader._try_download_from_url.assert_called_once_with(
            url_template.format(pmcid=pmcid), pmcid, doi
        )

    def test_via_pmcid_all_sources_failed(self, downloader):
        pmcid = "PMC123456"
        doi = "10.1000/test"

        downloader._try_download_from_url = Mock(
            return_value={"success": False, "error": "Not found"}
        )

        result = downloader.download_paper({"pmcid": pmcid, "doi": doi})

        assert result["success"] is False
        assert "所有 2 个 PDF 源都失败" in result["error"]
        assert result["stage"] == "download_pdf"
        assert [attempt["source"] for attempt in result["attempts"]] == [
            "PMC OA Service",
            "europe_pmc",
        ]
        assert downloader._try_download_from_url.call_count == len(
            downloader.pdf_sources
        )

    def test_via_pmcid_respects_source_priority(self, session, tmp_dir):
        downloader = PDFDownloader(
            str(tmp_dir),
            session,
            source_priority=["europe_pmc"],
        )
        downloader.pmc_oa_service.process_pmcid = Mock()
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/path/to/file.pdf"}
        )

        result = downloader.download_paper(
            {"pmcid": "PMC123456", "doi": "10.1000/test"}
        )

        assert result["success"] is True
        assert [attempt["source"] for attempt in result["attempts"]] == [
            "europe_pmc"
        ]
        downloader.pmc_oa_service.process_pmcid.assert_not_called()

    def test_via_pmcid_normalizes_bare_pmcid(self, downloader):
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/x.pdf"}
        )
        downloader.download_paper({"pmcid": "123456"})  # no PMC prefix
        args = downloader._try_download_from_url.call_args.args
        assert args[1] == "PMC123456"

    def test_via_pmcid_cache_hit_returns_skipped_existing(self, downloader, tmp_dir):
        pmcid = "PMC123456"
        doi = "10.1000/test"
        existing_path = downloader.store.path_for(
            {"pmcid": pmcid, "doi": doi, "arxiv_id": ""}
        )
        existing_path.write_bytes(b"old pdf")

        downloader._try_download_from_url = Mock()
        result = downloader.download_paper({"pmcid": pmcid, "doi": doi})

        assert result["success"] is True
        assert result["source"] == "cache"
        assert result["stage"] == "cache_hit"
        assert result["path"] == str(existing_path)
        assert result["skipped_existing"] is True
        downloader._try_download_from_url.assert_not_called()

    # ---- _via_arxiv dispatch --------------------------------------------------

    def test_via_arxiv_normalizes_arxiv_prefix(self, downloader):
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/a.pdf"}
        )
        result = downloader.download_paper({"arxiv_id": "arxiv:2301.12345"})
        assert result["arxiv_id"] == "2301.12345"
        assert result["source"] == "arxiv"

    # ---- _via_direct dispatch -------------------------------------------------

    def test_via_direct_does_not_label_as_pmcid(self, downloader):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.iter_content.return_value = [b"pdf"]
        downloader.session.get = Mock(return_value=mock_response)

        result = downloader.download_paper(
            {"title": "Direct PDF", "pdf_url": "https://example.com/direct.pdf"}
        )

        assert result["success"] is True
        assert "pmcid" not in result
        assert result["pdf_url"] == "https://example.com/direct.pdf"

    def test_priority_respects_arxiv_over_direct(self, session, tmp_dir):
        downloader = PDFDownloader(
            str(tmp_dir),
            session,
            source_priority=["direct", "arxiv"],
        )
        downloader._via_arxiv = Mock()
        downloader._try_download_from_url = Mock(
            return_value={"success": True, "path": "/direct.pdf"}
        )

        result = downloader.download_paper(
            {
                "arxiv_id": "2401.00001",
                "pdf_url": "https://example.com/direct.pdf",
            }
        )
        assert result["success"] is True
        assert result["source"] == "direct"
        downloader._via_arxiv.assert_not_called()

    # ---- Public surface guard ------------------------------------------------

    def test_only_one_public_download_entry(self, downloader):
        public_download_methods = {
            name
            for name in dir(downloader)
            if not name.startswith("_")
            and callable(getattr(downloader, name))
            and "download" in name
        }
        assert public_download_methods == {"download_paper"}, (
            "PDFDownloader should expose only download_paper publicly; "
            f"found: {sorted(public_download_methods)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
