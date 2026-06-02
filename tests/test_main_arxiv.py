import json
from pathlib import Path
from unittest.mock import ANY, Mock

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


def test_main_passes_ncbi_credentials_to_fetcher(monkeypatch, tmp_path):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Test Paper",
            "authors": [],
            "year": "2024",
            "pmid": "12345678",
        }
    ]

    fetcher_factory = Mock(return_value=fetcher)
    monkeypatch.setattr(main_module, "PaperFetcher", fetcher_factory)
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        main_module,
        "PMCIDCounter",
        Mock(
            return_value=Mock(
                count_pmcid=Mock(
                    return_value={
                        "query": "transformer",
                        "total": 1,
                        "checked": 1,
                        "with_pmcid": 0,
                        "without_pmcid": 1,
                        "rate": 0.0,
                        "elapsed_seconds": 1.0,
                        "estimated_size_mb": 0,
                    }
                )
            )
        ),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "transformer",
            "-e",
            "user@example.com",
            "-k",
            "api-key",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    fetcher_factory.assert_called_once_with(
        output_dir=str(tmp_path),
        default_source=main_module.DEFAULT_SOURCE,
        email="user@example.com",
        api_key="api-key",
    )


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
            "--source-priority",
            "arxiv,direct",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    fetcher.search_papers.assert_called_once_with(
        "transformer", limit=5, source="arxiv", fetch_pmcid=False
    )
    download_manager.download_batch.assert_called_once()
    assert main_module.UnifiedDownloadManager.call_args.kwargs["source_priority"] == [
        "arxiv",
        "direct",
    ]
    papers = download_manager.download_batch.call_args.args[0]
    assert len(papers) == 1
    assert papers[0]["arxiv_id"] == "2401.00001"


def test_main_download_dry_run_writes_plan_without_downloading(monkeypatch, tmp_path):
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

    download_manager_class = Mock()
    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "UnifiedDownloadManager", download_manager_class)
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
            "--dry-run",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    download_manager_class.assert_not_called()
    plan = json.loads((tmp_path / "download_plan.json").read_text(encoding="utf-8"))
    assert plan["schema"] == "download_plan.v1"
    assert plan["ready"] == 1
    assert not (tmp_path / "download_results.json").exists()
    assert not (tmp_path / "run_summary.json").exists()


def test_main_download_writes_summary_when_plan_has_only_skipped_entries(
    monkeypatch, tmp_path
):
    fetcher = Mock()
    fetcher.search_papers.return_value = [
        {
            "title": "Metadata Only Paper",
            "authors": ["Author One"],
            "journal": "Journal",
            "year": "2024",
        }
    ]

    download_manager_class = Mock()
    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(main_module, "UnifiedDownloadManager", download_manager_class)
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-s",
            "metadata",
            "-S",
            "arxiv",
            "-d",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    download_manager_class.assert_not_called()
    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["total"] == 1
    assert summary["success"] == 0
    assert summary["failed"] == 0
    assert summary["skipped"] == 1
    assert summary["results"][0]["status"] == "skipped"
    assert summary["results"][0]["error"] == "no_download_route"

    download_payload = json.loads(
        (tmp_path / "download_results.json").read_text(encoding="utf-8")
    )
    assert download_payload["total"] == 0


def test_main_unified_input_arxiv_id(monkeypatch, tmp_path):
    fetcher = Mock()
    plan_builder = Mock(
        return_value=(
            main_module.build_download_plan(
                [{"arxiv_id": "2301.12345", "source": "direct_arxiv"}],
                source="unified_input",
            )
        )
    )

    download_manager = Mock()
    download_manager.download_batch.return_value = [
        {
            "arxiv_id": "2301.12345",
            "success": True,
            "path": str(tmp_path / "2301.12345.pdf"),
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(
        "pdfget.cli_workflows.build_download_plan_from_unified_input",
        plan_builder,
    )
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
            "-m",
            "2301.12345",
            "-o",
            str(tmp_path),
            "-t",
            "2",
        ],
    )

    main_module.main()

    plan_builder.assert_called_once_with(
        "2301.12345",
        column=None,
        limit=main_module.DEFAULT_SEARCH_LIMIT,
        resolver=fetcher,
        logger=ANY,
    )
    main_module.UnifiedDownloadManager.assert_called_once()
    assert main_module.UnifiedDownloadManager.call_args.kwargs["max_workers"] == 2
    download_manager.download_batch.assert_called_once()


def test_main_unified_input_json_format_outputs_download_schema(
    monkeypatch, tmp_path, capsys
):
    fetcher = Mock()
    plan_builder = Mock(
        return_value=(
            main_module.build_download_plan(
                [{"arxiv_id": "2301.12345", "source": "direct_arxiv"}],
                source="unified_input",
            )
        )
    )
    download_manager = Mock()
    download_manager.download_batch.return_value = [
        {
            "arxiv_id": "2301.12345",
            "success": True,
            "path": str(tmp_path / "2301.12345.pdf"),
        }
    ]

    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(
        "pdfget.cli_workflows.build_download_plan_from_unified_input",
        plan_builder,
    )
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


def test_main_unified_input_dry_run_writes_plan_without_downloading(
    monkeypatch, tmp_path
):
    fetcher = Mock()
    plan_builder = Mock(
        return_value=(
            main_module.build_download_plan(
                [{"arxiv_id": "2301.12345", "source": "direct_arxiv"}],
                source="unified_input",
            )
        )
    )

    download_manager_class = Mock()
    monkeypatch.setattr(main_module, "PaperFetcher", Mock(return_value=fetcher))
    monkeypatch.setattr(
        "pdfget.cli_workflows.build_download_plan_from_unified_input",
        plan_builder,
    )
    monkeypatch.setattr(main_module, "UnifiedDownloadManager", download_manager_class)
    monkeypatch.setattr(main_module, "get_main_logger", lambda: _Logger())
    monkeypatch.setattr(
        "sys.argv",
        [
            "pdfget",
            "-m",
            "2301.12345",
            "--dry-run",
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    plan_builder.assert_called_once()
    download_manager_class.assert_not_called()
    plan = json.loads((tmp_path / "download_plan.json").read_text(encoding="utf-8"))
    assert plan["source"] == "unified_input"
    assert plan["ready"] == 1
    assert not (tmp_path / "download_results.json").exists()


def test_main_search_json_format_keeps_stdout_machine_readable(
    monkeypatch, tmp_path, capsys
):
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

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema"] == "paper_record.v1"
    assert payload["results"][0]["arxiv_id"] == "2401.00001"


def test_main_download_json_format_keeps_stdout_machine_readable(
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

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema"] == "download_result.v1"
    assert payload["results"][0]["arxiv_id"] == "2401.00001"
    assert "PDF 下载器启动" in captured.err


def test_main_download_writes_run_summary_for_failed_results(monkeypatch, tmp_path):
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
            "success": False,
            "error": "timeout",
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
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["schema"] == "run_summary.v2"
    assert summary["failed"] == 1
    assert summary["download_plan_path"] == str(tmp_path / "download_plan.json")
    assert summary["results"][0]["status"] == "failed"
    assert summary["results"][0]["paper"]["arxiv_id"] == "2401.00001"

    download_payload = json.loads(
        (tmp_path / "download_results.json").read_text(encoding="utf-8")
    )
    assert download_payload["total"] == 1
    assert download_payload["success"] == 0


def test_main_resume_retries_failed_report_entries(monkeypatch, tmp_path):
    report_path = tmp_path / "previous_run.json"
    report_path.write_text(
        json.dumps(
            {
                "schema": "run_summary.v2",
                "results": [
                    {
                        "status": "success",
                        "paper": {"pmcid": "PMC1", "source": "pubmed"},
                        "result": {"success": True, "pmcid": "PMC1"},
                    },
                    {
                        "status": "failed",
                        "paper": {
                            "title": "Failed arXiv",
                            "arxiv_id": "2401.00001",
                            "source": "arxiv",
                        },
                        "result": {"success": False, "error": "timeout"},
                        "retryable": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    fetcher = Mock()
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
            "--resume",
            str(report_path),
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    download_manager.download_batch.assert_called_once()
    retried_papers = download_manager.download_batch.call_args.args[0]
    assert len(retried_papers) == 1
    assert retried_papers[0]["arxiv_id"] == "2401.00001"

    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["source"] == "resume"
    assert summary["previous_report"] == str(report_path)


def test_main_resume_accepts_download_plan(monkeypatch, tmp_path):
    plan = main_module.build_download_plan(
        [
            {"pmcid": "PMC1", "source": "pubmed"},
            {"title": "No route", "source": "pubmed"},
        ],
        source="search",
    )
    plan_path = tmp_path / "download_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    fetcher = Mock()
    download_manager = Mock()
    download_manager.download_batch.return_value = [
        {
            "success": True,
            "path": str(tmp_path / "PMC1.pdf"),
            "pmcid": "PMC1",
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
            "--resume",
            str(plan_path),
            "-o",
            str(tmp_path),
        ],
    )

    main_module.main()

    download_manager.download_batch.assert_called_once()
    retried_papers = download_manager.download_batch.call_args.args[0]
    assert len(retried_papers) == 1
    assert retried_papers[0]["pmcid"] == "PMC1"

    summary = json.loads((tmp_path / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["input_value"] == "download_plan"
    assert summary["skipped"] == 1
