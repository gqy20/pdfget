from unittest.mock import Mock

from pdfget.manager import UnifiedDownloadManager


class _ThreadFetcher:
    def __init__(self):
        self.pdf_downloader = Mock()
        self.pdf_downloader.download_paper.side_effect = self._download_paper

    @staticmethod
    def _download_paper(paper):
        return {
            "success": True,
            "path": f"{paper['title']}.pdf",
        }


def test_download_batch_preserves_duplicate_identifier_order():
    fetcher = Mock()
    fetcher.cache_dir = "cache"
    fetcher.output_dir = "pdfs"

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=2, base_delay=0)
    manager._create_thread_fetcher = Mock(side_effect=lambda: _ThreadFetcher())

    papers = [
        {"pmcid": "PMC123", "title": "first"},
        {"pmcid": "PMC123", "title": "second"},
    ]

    results = manager.download_batch(papers)

    assert [result["path"] for result in results] == ["first.pdf", "second.pdf"]
    assert all(result["pmcid"] == "PMC123" for result in results)
