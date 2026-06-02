import json

import pytest

from pdfget.download_plan import build_download_plan
from pdfget.run_report import build_run_summary, load_failed_papers, save_run_summary


def test_build_run_summary_pairs_papers_and_results():
    papers = [
        {
            "title": "Paper One",
            "pmcid": "PMC1",
            "doi": "10.1000/one",
            "source": "pubmed",
        },
        {
            "title": "Paper Two",
            "arxiv_id": "2401.00001",
            "source": "arxiv",
        },
    ]
    results = [
        {"success": True, "path": "one.pdf", "pmcid": "PMC1"},
        {
            "success": False,
            "error": "timeout",
            "arxiv_id": "2401.00001",
            "stage": "download_pdf",
        },
    ]

    summary = build_run_summary(
        results,
        papers=papers,
        source="search",
        output_dir="pdfs",
        input_value="test query",
        download_plan_path="pdfs/download_plan.json",
    )

    assert summary["schema"] == "run_summary.v1"
    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["skipped"] == 0
    assert summary["download_plan_path"] == "pdfs/download_plan.json"
    assert summary["results"][0]["status"] == "success"
    assert summary["results"][1]["identifier"] == "2401.00001"
    assert summary["results"][1]["identifier_type"] == "arxiv"
    assert summary["results"][1]["stage"] == "download_pdf"
    assert summary["results"][1]["paper"]["title"] == "Paper Two"
    assert summary["results"][1]["error"] == "timeout"
    assert summary["results"][1]["retryable"] is True
    assert summary["results"][1]["retry_reason"] == "download_pdf"
    assert summary["results"][0]["retryable"] is False


def test_build_run_summary_includes_skipped_plan_entries():
    plan = build_download_plan(
        [
            {"pmcid": "PMC1", "source": "pubmed"},
            {"pmcid": "PMC1", "source": "europe_pmc"},
            {"title": "No route", "source": "pubmed"},
            {"arxiv_id": "2401.00001", "source": "arxiv"},
        ],
        source="search",
    )

    summary = build_run_summary(
        [
            {"success": True, "path": "one.pdf", "pmcid": "PMC1"},
            {
                "success": False,
                "error": "timeout",
                "arxiv_id": "2401.00001",
                "stage": "download_pdf",
            },
        ],
        plan_entries=plan["entries"],
        source="search",
        output_dir="pdfs",
    )

    assert summary["total"] == 4
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["skipped"] == 2
    assert [entry["status"] for entry in summary["results"]] == [
        "success",
        "skipped",
        "skipped",
        "failed",
    ]
    assert summary["results"][1]["error"] == "duplicate"
    assert summary["results"][2]["error"] == "no_download_route"
    assert summary["results"][1]["retryable"] is False
    assert summary["results"][3]["retryable"] is True
    assert summary["stats"]["by_status"] == {
        "success": 1,
        "skipped": 2,
        "failed": 1,
    }
    assert summary["stats"]["by_skip_reason"] == {
        "duplicate": 1,
        "no_download_route": 1,
    }


def test_build_run_summary_aggregates_attempt_stats():
    summary = build_run_summary(
        [
            {
                "success": False,
                "error": "timeout",
                "pmcid": "PMC1",
                "stage": "download_pdf",
                "source": "pmc",
                "attempts": [
                    {"source": "pmc", "success": False, "stage": "download_pdf"},
                    {"source": "europe_pmc", "success": False, "stage": "download_pdf"},
                ],
            }
        ],
        source="input",
        output_dir="pdfs",
    )

    assert summary["stats"]["by_source"] == {"pmc": 1}
    assert summary["stats"]["by_stage"] == {"download_pdf": 1}
    assert summary["stats"]["attempts_by_source"]["pmc"] == {
        "total": 1,
        "success": 0,
        "failed": 1,
    }
    assert summary["stats"]["attempts_by_source"]["europe_pmc"]["failed"] == 1


def test_save_run_summary_writes_latest_and_archived_copy(tmp_path):
    summary = build_run_summary(
        [{"success": False, "error": "not found", "pmcid": "PMC1"}],
        source="input",
        output_dir=str(tmp_path),
    )

    latest = save_run_summary(str(tmp_path), summary)

    assert latest == tmp_path / "run_summary.json"
    assert json.loads(latest.read_text(encoding="utf-8"))["schema"] == "run_summary.v1"
    archived = list(tmp_path.glob("run_summary_*.json"))
    assert len(archived) == 1


def test_load_failed_papers_returns_only_retryable_failures(tmp_path):
    report = build_run_summary(
        [
            {"success": True, "path": "one.pdf", "pmcid": "PMC1"},
            {
                "success": False,
                "error": "timeout",
                "arxiv_id": "2401.00001",
                "stage": "download_pdf",
            },
            {
                "success": False,
                "error": "No downloadable identifier found",
                "stage": "resolve_identifier",
            },
            {
                "success": False,
                "error": "不是 PDF 文件",
                "pdf_url": "https://example.com/html",
                "stage": "validate_response",
            },
        ],
        source="input",
        output_dir=str(tmp_path),
    )
    path = tmp_path / "run_summary.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    papers = load_failed_papers(path)

    assert len(papers) == 1
    assert papers[0]["arxiv_id"] == "2401.00001"


def test_load_failed_papers_infers_retryability_for_legacy_reports(tmp_path):
    path = tmp_path / "legacy_summary.json"
    path.write_text(
        json.dumps(
            {
                "schema": "run_summary.v1",
                "results": [
                    {
                        "status": "failed",
                        "paper": {"pmcid": "PMC1", "source": "pubmed"},
                        "result": {
                            "success": False,
                            "error": "下载失败: 503",
                            "stage": "download_pdf",
                        },
                    },
                    {
                        "status": "failed",
                        "paper": {"pmcid": "PMC2", "source": "pubmed"},
                        "result": {
                            "success": False,
                            "error": "不是 PDF 文件",
                            "stage": "validate_response",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    papers = load_failed_papers(path)

    assert len(papers) == 1
    assert papers[0]["pmcid"] == "PMC1"


def test_load_failed_papers_rejects_unknown_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema": "other.v1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="不支持的运行报告 schema"):
        load_failed_papers(path)
