"""PMC OA Service integration: ensure ``download_paper`` routes correctly
through the PMC OA branch and produces the expected download_result shape.
"""

from unittest.mock import patch

import pytest

from pdfget.downloader import PDFDownloader


@pytest.mark.integration
class TestPMCOAIntegration:
    """Verify PMC OA Service is consulted before fall-back URLs."""

    @pytest.fixture
    def session(self):
        from unittest.mock import Mock

        return Mock()

    @pytest.fixture
    def downloader(self, session, tmp_path):
        return PDFDownloader(str(tmp_path / "pdfs"), session)

    def test_download_paper_uses_pmc_oa_first(self, downloader):
        pmcid = "PMC7927990"
        doi = "10.1000/test.doi"

        with (
            patch.object(downloader.store, "has", return_value=False),
            patch.object(downloader.pmc_oa_service, "process_pmcid") as mock_process,
            patch.object(downloader.pmc_oa_service, "_query_oa_service") as mock_query,
            patch.object(
                downloader.pmc_oa_service, "_extract_download_links"
            ) as mock_extract,
            patch.object(downloader.pmc_oa_service, "_download_file") as mock_download,
        ):
            mock_process.return_value = True
            mock_query.return_value.__enter__ = lambda x: x
            mock_query.return_value.__exit__ = lambda x, *args: None
            mock_extract.return_value = [
                {
                    "format": "pdf",
                    "href": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/1d/5a/106863.PMC7927990.pdf",
                }
            ]
            mock_download.return_value = True

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.stat") as mock_stat,
            ):
                mock_stat.return_value.st_size = 12345

                result = downloader.download_paper(
                    {"pmcid": pmcid, "doi": doi}
                )

            assert result["success"] is True
            assert result["source"] == "PMC OA Service"
            assert result["content_length"] == 12345
            assert result["stage"] == "download_pdf"
            mock_process.assert_called_once_with(pmcid, doi)

    def test_download_paper_falls_back_to_other_sources(self, downloader):
        pmcid = "PMC123456"
        doi = "10.1000/test.doi"

        with (
            patch.object(
                downloader.pmc_oa_service, "process_pmcid", return_value=False
            ),
            patch.object(downloader, "_try_download_from_url") as mock_try,
        ):
            mock_try.return_value = {
                "success": True,
                "path": "/tmp/test.pdf",
                "content_length": 67890,
            }

            result = downloader.download_paper({"pmcid": pmcid, "doi": doi})

            assert result["success"] is True
            assert result["path"] == "/tmp/test.pdf"
            assert mock_try.call_count >= 1

    @pytest.mark.network
    def test_real_pmc_oa_download(self, tmp_path):
        """Live network test against PMC OA Service."""
        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": "test-integration/1.0"})

        downloader = PDFDownloader(str(tmp_path), session)

        pmcid = "PMC7927990"
        doi = "10.1000/test.doi"

        result = downloader.download_paper({"pmcid": pmcid, "doi": doi})

        if result["success"]:
            assert "path" in result
            assert result["source"] in ("PMC OA Service", "europe_pmc")
            assert "attempts" in result
            pdf_path = tmp_path / result["path"]
            assert pdf_path.exists()
            assert pdf_path.stat().st_size > 0
        else:
            pytest.skip(f"PMC OA Service 不可用: {result.get('error', '未知错误')}")
