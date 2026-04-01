from pdfget.paper_schema import (
    build_identifier,
    compute_download_fields,
    normalize_paper_record,
)


def test_normalize_paper_record_arxiv_contract():
    record = normalize_paper_record(
        {
            "title": "Test arXiv Paper",
            "authors": ["Author One"],
            "year": "2024-01-10",
            "source": "arxiv",
            "arxiv_id": "2401.01234",
            "pdf_url": "https://arxiv.org/pdf/2401.01234.pdf",
        },
        "arxiv",
    )

    assert record["identifier"] == "2401.01234"
    assert record["identifier_type"] == "arxiv"
    assert record["is_downloadable"] is True
    assert record["download_url"] == "https://arxiv.org/pdf/2401.01234.pdf"
    assert record["repository"] == "arXiv"
    assert record["year"] == "2024"
    assert record["published_at"] == "2024"


def test_normalize_paper_record_pmc_contract():
    record = normalize_paper_record(
        {
            "title": "Test PMC Paper",
            "source": "pubmed",
            "pmid": "12345678",
            "pmcid": "PMC1234567",
            "doi": "10.1000/test",
        },
        "pubmed",
    )

    assert record["identifier"] == "PMC1234567"
    assert record["identifier_type"] == "pmcid"
    assert record["is_downloadable"] is True
    assert record["download_url"] == ""
    assert record["download_type"] == "pmc"


def test_build_identifier_priority():
    identifier, identifier_type = build_identifier(
        {
            "pmid": "12345678",
            "pmcid": "PMC1234567",
            "doi": "10.1000/test",
            "arxiv_id": "2401.01234",
        }
    )

    assert identifier == "PMC1234567"
    assert identifier_type == "pmcid"


def test_compute_download_fields_priority():
    is_downloadable, download_url = compute_download_fields(
        {
            "pmcid": "",
            "arxiv_id": "2401.01234",
            "pdf_url": "",
        }
    )

    assert is_downloadable is True
    assert download_url == "https://arxiv.org/pdf/2401.01234.pdf"
