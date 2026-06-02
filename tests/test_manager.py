import threading
import time
from unittest.mock import Mock, patch

import pytest

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


@pytest.mark.usefixtures("fast_sleep")
def test_download_batch_preserves_duplicate_identifier_order():
    fetcher = Mock()
    fetcher.cache_dir = "cache"
    fetcher.output_dir = "pdfs"
    fetcher.email = ""
    fetcher.api_key = ""
    fetcher.default_source = "pubmed"

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=2, base_delay=0)
    manager._create_thread_fetcher = Mock(side_effect=lambda: _ThreadFetcher())

    papers = [
        {"pmcid": "PMC123", "title": "first"},
        {"pmcid": "PMC123", "title": "second"},
    ]

    results = manager.download_batch(papers)

    assert [result["path"] for result in results] == ["first.pdf", "second.pdf"]
    assert all(result["pmcid"] == "PMC123" for result in results)


@pytest.mark.usefixtures("fast_sleep")
def test_download_batch_reuses_fetcher_within_worker_thread():
    fetcher = Mock()
    fetcher.cache_dir = "cache"
    fetcher.output_dir = "pdfs"
    fetcher.email = "user@example.com"
    fetcher.api_key = "api-key"
    fetcher.default_source = "pubmed"

    created_fetchers = []

    class RecordingFetcher(_ThreadFetcher):
        def __init__(self):
            super().__init__()
            self.thread_ids = []

            def _record_thread(paper):
                self.thread_ids.append(threading.get_ident())
                time.sleep(0.01)
                return self._download_paper(paper)

            self.pdf_downloader.download_paper.side_effect = _record_thread

    def _create_fetcher():
        thread_fetcher = RecordingFetcher()
        created_fetchers.append(thread_fetcher)
        return thread_fetcher

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=1, base_delay=0)
    manager._create_thread_fetcher = Mock(side_effect=_create_fetcher)

    papers = [
        {"pmcid": "PMC1", "title": "first"},
        {"pmcid": "PMC2", "title": "second"},
    ]

    results = manager.download_batch(papers)

    assert [result["path"] for result in results] == ["first.pdf", "second.pdf"]
    manager._create_thread_fetcher.assert_called_once()
    assert len(created_fetchers[0].thread_ids) == 2
    assert len(set(created_fetchers[0].thread_ids)) == 1


def test_create_thread_fetcher_preserves_parent_credentials():
    fetcher = Mock()
    fetcher.cache_dir = "cache"
    fetcher.output_dir = "pdfs"
    fetcher.email = "user@example.com"
    fetcher.api_key = "api-key"
    fetcher.default_source = "arxiv"

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=1, base_delay=0)

    with patch("pdfget.manager.PaperFetcher") as created:
        manager._create_thread_fetcher()

    created.assert_called_once_with(
        cache_dir="cache",
        output_dir="pdfs",
        email="user@example.com",
        api_key="api-key",
        default_source="arxiv",
    )
