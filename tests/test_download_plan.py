from pdfget.download_plan import (
    build_download_plan,
    choose_download_strategy,
    ready_papers,
    save_download_plan,
)
from pdfget.paper_schema import normalize_paper_record


class _Resolver:
    def resolve_pmids(self, pmids: list[str]) -> dict[str, str]:
        return {"12345678": "PMC123456"} if "12345678" in pmids else {}

    def resolve_dois(self, dois: list[str]) -> dict[str, str]:
        return {"10.1000/test": "PMC1000"} if "10.1000/test" in dois else {}


def test_build_download_plan_marks_ready_and_skipped_entries():
    papers = [
        {"pmcid": "PMC1", "source": "pubmed"},
        {"arxiv_id": "2401.00001", "source": "arxiv"},
        {"pdf_url": "https://example.com/paper.pdf", "source": "custom"},
        {"title": "No download route", "source": "pubmed"},
    ]

    plan = build_download_plan(papers, source="search")

    assert plan["schema"] == "download_plan.v1"
    assert plan["total"] == 4
    assert plan["ready"] == 3
    assert plan["skipped"] == 1
    assert [entry["strategy"] for entry in plan["entries"]] == [
        "pmc",
        "arxiv",
        "direct_pdf",
        "",
    ]
    assert plan["entries"][3]["status"] == "skipped"
    assert plan["entries"][3]["skip_reason"] == "no_download_route"


def test_ready_papers_returns_only_downloadable_records():
    plan = build_download_plan(
        [
            {"pmcid": "PMC1", "source": "pubmed"},
            {"title": "No download route", "source": "pubmed"},
        ],
        source="search",
    )

    papers = ready_papers(plan)

    assert len(papers) == 1
    assert papers[0]["pmcid"] == "PMC1"


def test_build_download_plan_skips_duplicate_ready_records():
    plan = build_download_plan(
        [
            {"doi": "10.1000/test", "pmcid": "PMC1", "source": "pubmed"},
            {"doi": "10.1000/test", "pmcid": "PMC1", "source": "europe_pmc"},
            {"doi": "10.1000/other", "pmcid": "PMC2", "source": "pubmed"},
        ],
        source="search",
    )

    assert plan["total"] == 3
    assert plan["ready"] == 2
    assert plan["skipped"] == 1
    assert plan["entries"][1]["status"] == "skipped"
    assert plan["entries"][1]["skip_reason"] == "duplicate"
    assert plan["entries"][1]["duplicate_of"] == 0
    assert plan["entries"][0]["merged_sources"] == ["pubmed", "europe_pmc"]


def test_build_download_plan_deduplicates_by_title_when_identifiers_are_missing():
    plan = build_download_plan(
        [
            {
                "title": "A  Normalized   Title",
                "pdf_url": "https://example.com/first.pdf",
                "source": "custom",
            },
            {
                "title": "a normalized title",
                "pdf_url": "https://example.com/second.pdf",
                "source": "mirror",
            },
        ],
        source="search",
    )

    assert plan["ready"] == 1
    assert plan["skipped"] == 1
    assert plan["entries"][0]["dedupe_key"] == "title:a normalized title"
    assert plan["entries"][1]["skip_reason"] == "duplicate"
    assert ready_papers(plan)[0]["pdf_url"] == "https://example.com/first.pdf"


def test_build_download_plan_resolves_pmid_and_doi_to_pmcid():
    plan = build_download_plan(
        [
            {"pmid": "12345678", "source": "pubmed"},
            {"doi": "10.1000/test", "source": "pubmed"},
        ],
        source="search",
        resolver=_Resolver(),
    )

    assert plan["ready"] == 2
    assert plan["entries"][0]["resolved_by"] == "pmid_to_pmcid"
    assert plan["entries"][0]["resolved_from"] == "12345678"
    assert plan["entries"][0]["paper"]["pmcid"] == "PMC123456"
    assert plan["entries"][1]["resolved_by"] == "doi_to_pmcid"
    assert plan["entries"][1]["resolved_from"] == "10.1000/test"
    assert plan["entries"][1]["paper"]["pmcid"] == "PMC1000"


def test_build_download_plan_marks_unresolved_identifiers():
    plan = build_download_plan(
        [
            {"pmid": "99999999", "source": "pubmed"},
            {"doi": "10.1000/missing", "source": "pubmed"},
        ],
        source="search",
        resolver=_Resolver(),
    )

    assert plan["ready"] == 0
    assert plan["skipped"] == 2
    assert [entry["skip_reason"] for entry in plan["entries"]] == [
        "unresolved_identifier",
        "unresolved_identifier",
    ]


def test_choose_download_strategy_prefers_pmc_then_arxiv_then_pdf():
    pmc_record = normalize_paper_record(
        {"pmcid": "PMC1", "arxiv_id": "2401.00001", "pdf_url": "https://x/pdf"},
        "test",
    )
    arxiv_record = normalize_paper_record(
        {"arxiv_id": "2401.00001", "pdf_url": "https://x/pdf"},
        "test",
    )
    pdf_record = normalize_paper_record({"pdf_url": "https://x/pdf"}, "test")

    assert choose_download_strategy(pmc_record) == "pmc"
    assert choose_download_strategy(arxiv_record) == "arxiv"
    assert choose_download_strategy(pdf_record) == "direct_pdf"


def test_save_download_plan_writes_latest_and_archived_copy(tmp_path):
    plan = build_download_plan([{"pmcid": "PMC1", "source": "pubmed"}], source="search")

    latest = save_download_plan(str(tmp_path), plan)

    assert latest == tmp_path / "download_plan.json"
    assert latest.exists()
    archived = list(tmp_path.glob("download_plan_*.json"))
    assert len(archived) == 1
