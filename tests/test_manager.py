import threading
import time
from unittest.mock import Mock, patch

import pytest

from pdfget.manager import UnifiedDownloadManager


class _ThreadDownloader:
    def __init__(self):
        self.download_paper = Mock(side_effect=self._download_paper)

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
    manager._create_thread_downloader = Mock(side_effect=_ThreadDownloader)

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

    created_downloaders = []

    class RecordingDownloader:
        def __init__(self):
            self.thread_ids = []

            def _record_thread(paper):
                self.thread_ids.append(threading.get_ident())
                time.sleep(0.01)
                return {
                    "success": True,
                    "path": f"{paper['title']}.pdf",
                }

            self.download_paper = Mock(side_effect=_record_thread)

    def _create_downloader():
        downloader = RecordingDownloader()
        created_downloaders.append(downloader)
        return downloader

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=1, base_delay=0)
    manager._create_thread_downloader = Mock(side_effect=_create_downloader)

    papers = [
        {"pmcid": "PMC1", "title": "first"},
        {"pmcid": "PMC2", "title": "second"},
    ]

    results = manager.download_batch(papers)

    assert [result["path"] for result in results] == ["first.pdf", "second.pdf"]
    manager._create_thread_downloader.assert_called_once()
    assert len(created_downloaders[0].thread_ids) == 2
    assert len(set(created_downloaders[0].thread_ids)) == 1


def test_create_thread_downloader_uses_parent_output_dir():
    fetcher = Mock()
    fetcher.output_dir = "pdfs"
    fetcher.session = Mock()

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=1, base_delay=0)

    with patch("pdfget.manager.PDFDownloader") as created:
        manager._create_thread_downloader()

    created.assert_called_once_with("pdfs", fetcher.session, source_priority=None)


def test_create_thread_downloader_passes_source_priority():
    fetcher = Mock()
    fetcher.output_dir = "pdfs"
    fetcher.session = Mock()

    manager = UnifiedDownloadManager(
        fetcher=fetcher,
        max_workers=1,
        base_delay=0,
        source_priority=["europe_pmc"],
    )

    with patch("pdfget.manager.PDFDownloader") as created:
        manager._create_thread_downloader()

    created.assert_called_once_with(
        "pdfs",
        fetcher.session,
        source_priority=["europe_pmc"],
    )


@pytest.mark.usefixtures("fast_sleep")
def test_download_batch_marks_worker_errors_with_stage():
    fetcher = Mock()
    fetcher.cache_dir = "cache"
    fetcher.output_dir = "pdfs"
    fetcher.email = ""
    fetcher.api_key = ""
    fetcher.default_source = "pubmed"

    thread_downloader = Mock()
    thread_downloader.download_paper.side_effect = RuntimeError("boom")

    manager = UnifiedDownloadManager(fetcher=fetcher, max_workers=1, base_delay=0)
    manager._create_thread_downloader = Mock(return_value=thread_downloader)

    results = manager.download_batch([{"pmcid": "PMC1"}])

    assert results[0]["success"] is False
    assert results[0]["error"] == "boom"
    assert results[0]["stage"] == "worker_error"
