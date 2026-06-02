import json

import pytest

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
        {"success": False, "error": "timeout", "arxiv_id": "2401.00001"},
    ]

    summary = build_run_summary(
        results,
        papers=papers,
        source="search",
        output_dir="pdfs",
        input_value="test query",
    )

    assert summary["schema"] == "run_summary.v1"
    assert summary["total"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["results"][0]["status"] == "success"
    assert summary["results"][1]["identifier"] == "2401.00001"
    assert summary["results"][1]["identifier_type"] == "arxiv"
    assert summary["results"][1]["paper"]["title"] == "Paper Two"
    assert summary["results"][1]["error"] == "timeout"


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
            {"success": False, "error": "timeout", "arxiv_id": "2401.00001"},
            {"success": False, "error": "no identifier"},
        ],
        source="input",
        output_dir=str(tmp_path),
    )
    path = tmp_path / "run_summary.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    papers = load_failed_papers(path)

    assert len(papers) == 1
    assert papers[0]["arxiv_id"] == "2401.00001"


def test_load_failed_papers_rejects_unknown_schema(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema": "other.v1"}), encoding="utf-8")

    with pytest.raises(ValueError, match="不支持的运行报告 schema"):
        load_failed_papers(path)
