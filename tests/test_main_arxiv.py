from unittest.mock import Mock
import json
from pathlib import Path

import pytest

from pdfget import main as main_module


class _Logger:
    def info(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def setLevel(self, *args, **kwargs):
        return None


def test_primary_identifier_display_for_arxiv():
    label, value = main_module.get_primary_identifier_display(
        {
            "identifier": "2401.01234",
            "identifier_type": "arxiv",
            "arxiv_id": "2401.01234",
        }
    )

    assert label == "arXiv"
    assert value == "2401.01234"


def test_primary_identifier_display_falls_back_to_doi():
    label, value = main_module.get_primary_identifier_display(
        {
            "doi": "10.1000/test",
        }
    )

    assert label == "DOI"
    assert value == "10.1000/test"


def test_main_search_arxiv_skips_pmcid_counter(monkeypatch, tmp_path):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Test arXiv Paper",
            "authors": ["Author One", "Author Two"],
            "journal": "arXiv",
            "year": "2024",
            "doi": "10.48550/arXiv.2401.00001",
            "arxiv_id": "2401.00001",
            "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
            "repository": "arXiv",
            "download_type": "pdf",
        }
    ]

    pmcid_counter = Mock()

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "PMCIDCounter", Mock(return_value=pmcid_counter))
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        main_module,
        "StatsFormatter",
        Mock(format=Mock(), save_report=Mock()),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "transformer",
            "-S",
            "arxiv",
            "-l",
            "5",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    fetcher.search_papers.assert_called_once_with(
        "transformer", limit=5, source="arxiv"
    )
    main_module.PMCIDCounter.assert_not_called()


def test_main_search_arxiv_json_format_outputs_schema(monkeypatch, tmp_path, capsys):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Test arXiv Paper",
            "authors": ["Author One"],
            "year": "2024",
            "source": "arxiv",
            "identifier": "2401.00001",
            "identifier_type": "arxiv",
            "arxiv_id": "2401.00001",
            "is_downloadable": True,
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "transformer",
            "-S",
            "arxiv",
            "--format",
            "json",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    output = capsys.readouterr().out
    assert '"schema": "paper_record.v1"' in output
    assert '"arxiv_id": "2401.00001"' in output

    saved_files = list(Path(tmp_path).glob("search_results_*.json"))
    assert len(saved_files) == 1
    payload = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert payload["schema"] == "paper_record.v1"
    assert payload["results"][0]["arxiv_id"] == "2401.00001"


def test_main_download_arxiv_json_format_outputs_download_schema(
    monkeypatch, tmp_path, capsys
):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Downloadable arXiv Paper",
            "authors": ["Author One"],
            "journal": "arXiv",
            "year": "2024",
            "arxiv_id": "2401.00001",
            "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
        }
    ]

    download_manager = Mock()
    download_manager.download_batch.return_value = [
        {
            "success": True,
            "path": str(tmp_path / "2401.00001.pdf"),
            "arxiv_id": "2401.00001",
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(
        main_module,
        "UnifiedDownloadManager",
        Mock(return_value=download_manager),
    )
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "transformer",
            "-S",
            "arxiv",
            "-d",
            "--format",
            "json",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    output = capsys.readouterr().out
    assert '"schema": "download_result.v1"' in output
    assert '"arxiv_id": "2401.00001"' in output

    payload = json.loads(
        (Path(tmp_path) / "download_results.json").read_text(encoding="utf-8")
    )
    assert payload["schema"] == "download_result.v1"
    assert payload["results"][0]["arxiv_id"] == "2401.00001"


def test_main_download_arxiv_includes_arxiv_papers(monkeypatch, tmp_path):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Downloadable arXiv Paper",
            "authors": ["Author One"],
            "journal": "arXiv",
            "year": "2024",
            "arxiv_id": "2401.00001",
            "pdf_url": "https://arxiv.org/pdf/2401.00001.pdf",
        },
        {
            "title": "No PDF",
            "authors": ["Author Two"],
            "journal": "arXiv",
            "year": "2024",
        },
    ]

    download_manager = Mock()
    download_manager.download_batch.return_value = [
        {"success": True, "path": str(tmp_path / "2401.00001.pdf")}
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(
        main_module,
        "UnifiedDownloadManager",
        Mock(return_value=download_manager),
    )
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "transformer",
            "-S",
            "arxiv",
            "-l",
            "5",
            "-d",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    fetcher.search_papers.assert_called_once_with(
        "transformer", limit=5, source="arxiv", fetch_pmcid=False
    )
    download_manager.download_batch.assert_called_once()
    papers = download_manager.download_batch.call_args.args[0]
    assert len(papers) == 1
    assert papers[0]["arxiv_id"] == "2401.00001"


def test_main_unified_input_arxiv_id(monkeypatch, tmp_path):
    fetcher = Mock()
    fetcher.download_from_unified_input.return_value = [
        {
            "arxiv_id": "2301.12345",
            "success": True,
            "path": str(tmp_path / "2301.12345.pdf"),
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-m",
            "2301.12345",
            "-o",
            str(tmp_path),
            "-t",
            "2",
        ],
    )

    main_module.main()

    fetcher.download_from_unified_input.assert_called_once_with(
        input_value="2301.12345",
        column=None,
        limit=main_module.DEFAULT_SEARCH_LIMIT,
        max_workers=2,
        base_delay=None,
    )


def test_main_unified_input_json_format_outputs_download_schema(
    monkeypatch, tmp_path, capsys
):
    fetcher = Mock()
    fetcher.download_from_unified_input.return_value = [
        {
            "arxiv_id": "2301.12345",
            "success": True,
            "path": str(tmp_path / "2301.12345.pdf"),
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-m",
            "2301.12345",
            "--format",
            "json",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    output = capsys.readouterr().out
    assert '"schema": "download_result.v1"' in output
    assert '"arxiv_id": "2301.12345"' in output

    payload = json.loads(
        (Path(tmp_path) / "download_results.json").read_text(encoding="utf-8")
    )
    assert payload["schema"] == "download_result.v1"
    assert payload["input_value"] == "2301.12345"
