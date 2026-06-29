"""Tests for the single-entry ``PaperSearcher.search_papers`` contract."""

from unittest.mock import Mock, patch

import pytest

from pdfget.searcher import PaperSearcher


class TestPaperSearcher:
    """All search behaviour is reachable through ``search_papers``."""

    @pytest.fixture
    def session(self):
        return Mock()

    @pytest.fixture
    def searcher(self, session):
        return PaperSearcher(session)

    @pytest.fixture
    def sample_search_results(self):
        return [
            {
                "pmid": "32353885",
                "doi": "10.1186/s12916-020-01690-4",
                "title": "Paper 1",
                "authors": ["Author 1", "Author 2"],
                "journal": "Journal 1",
                "year": "2020",
                "abstract": "Abstract 1",
                "source": "pubmed",
            },
            {
                "pmid": "32353886",
                "doi": "10.1186/s12916-020-01690-5",
                "title": "Paper 2",
                "authors": ["Author 3"],
                "journal": "Journal 2",
                "year": "2020",
                "abstract": "Abstract 2",
                "source": "pubmed",
            },
        ]

    # ---- query normalisation --------------------------------------------------

    def test_parse_query_pubmed_simple(self, searcher):
        query = "COVID-19 vaccine"
        result = searcher._parse_query_pubmed(query)
        assert "COVID-19" in result
        assert "vaccine" in result

    def test_parse_query_pubmed_advanced(self, searcher):
        query = "COVID-19[Title] AND vaccine[Abstract]"
        result = searcher._parse_query_pubmed(query)
        assert "[Title]" in result
        assert "[Abstract]" in result

    def test_parse_query_pubmed_filters(self, searcher):
        query = "COVID-19 year:2020"
        result = searcher._parse_query_pubmed(query)
        assert "2020[pdat]" in result

    def test_parse_query_europepmc_simple(self, searcher):
        query = "COVID-19 vaccine"
        result = searcher._parse_query_europepmc(query)
        assert "COVID-19" in result

    def test_parse_query_europepmc_advanced(self, searcher):
        query = 'TITLE:"COVID-19" AND vaccine'
        result = searcher._parse_query_europepmc(query)
        assert "TITLE:" in result

    # ---- single source dispatch -----------------------------------------------

    @patch("pdfget.searcher.PaperSearcher._search_pubmed_api")
    def test_search_papers_pubmed_dispatches_to_api(
        self, mock_search, searcher, sample_search_results
    ):
        mock_search.return_value = sample_search_results
        result = searcher.search_papers("q", source="pubmed", limit=20)
        assert len(result) == 2
        assert result[0]["pmid"] == "32353885"
        mock_search.assert_called_once()

    @patch("pdfget.searcher.PaperSearcher._search_pubmed_api")
    def test_search_papers_pubmed_empty(self, mock_search, searcher):
        mock_search.return_value = []
        assert searcher.search_papers("nonexistent", source="pubmed") == []

    @patch("pdfget.searcher.PaperSearcher._search_europepmc_api")
    def test_search_papers_europepmc_dispatches(
        self, mock_search, searcher, sample_search_results
    ):
        for paper in sample_search_results:
            paper["source"] = "europe_pmc"
        mock_search.return_value = sample_search_results
        result = searcher.search_papers("q", source="europe_pmc", limit=20)
        assert len(result) == 2
        assert result[0]["source"] == "europe_pmc"

    # ---- combined-mode aggregation -------------------------------------------

    def test_search_papers_both_sources_runs_each(self, searcher):
        with (
            patch.object(searcher, "_single_source", return_value=[]) as mock_single,
        ):
            searcher.search_papers("test query", source="both", limit=50)
            sources = [call.args[2] for call in mock_single.call_args_list]
            assert sources == ["pubmed", "europe_pmc"]
            assert mock_single.call_count == 2

    def test_search_papers_all_sources_includes_arxiv(self, searcher):
        with patch.object(searcher, "_single_source", return_value=[]) as mock_single:
            searcher.search_papers("test query", source="all", limit=50)
            sources = [call.args[2] for call in mock_single.call_args_list]
            assert sources == ["pubmed", "europe_pmc", "arxiv"]

    def test_combined_applies_final_limit(self, searcher):
        with (
            patch.object(
                searcher,
                "_single_source",
                side_effect=lambda *a, **kw: [
                    {"pmid": str(i), "source": a[2]}
                    for i in (range(2) if a[2] == "pubmed" else range(2, 4))
                ],
            ),
        ):
            results = searcher.search_papers("q", source="both", limit=3)
        assert len(results) == 3
        assert [r["pmid"] for r in results] == ["0", "1", "2"]

    def test_combined_deduplicates_by_normalized_key(self, searcher):
        with (
            patch.object(
                searcher,
                "_single_source",
                side_effect=lambda *a, **kw: [
                    {
                        "pmid": "1",
                        "doi": "10.1000/example",
                        "title": "Shared",
                        "source": a[2],
                    },
                    {
                        "pmid": "1",
                        "doi": "10.1000/example",
                        "title": "A  Shared   Title",
                        "source": a[2],
                    },
                ]
                if a[2] == "pubmed"
                else [
                    {
                        "pmid": "99",
                        "doi": "10.1000/example",
                        "title": "A shared title",
                        "source": a[2],
                    }
                ],
            ),
        ):
            results = searcher.search_papers("q", source="both", limit=10)
        assert len(results) == 1
        for r in results:
            assert "pubmed" in r["merged_sources"]
            assert "europe_pmc" in r["merged_sources"]

    def test_combined_limit_with_arxiv(self, searcher):
        with patch.object(
            searcher,
            "_single_source",
            side_effect=lambda *a, **kw: [
                {"pmid": "1", "title": "P", "source": "pubmed"},
                {"arxiv_id": "2301.12345", "title": "A", "source": "arxiv"}
                if a[2] == "arxiv"
                else {},
            ]
            if a[2] != "europe_pmc"
            else [],
        ):
            results = searcher.search_papers("q", source="all", limit=10)
            sources = {r.get("source") for r in results}
            assert "arxiv" in sources

    def test_combined_passes_include_arxiv_override(self, searcher):
        with patch.object(searcher, "_single_source", return_value=[]) as mock_single:
            searcher.search_papers(
                "q", source="both", limit=10, include_arxiv=True
            )
            sources = [call.args[2] for call in mock_single.call_args_list]
            assert "arxiv" in sources

    # ---- default + unknown source --------------------------------------------

    def test_search_papers_default_source_is_pubmed(self, searcher):
        with patch.object(searcher, "_single_source", return_value=[]) as mock_single:
            searcher.search_papers("test query")
            assert mock_single.call_args.args[2] == "pubmed"

    def test_search_papers_unknown_source_falls_back(self, searcher):
        with patch.object(searcher, "_single_source", return_value=[]) as mock_single:
            searcher.search_papers("q", source="not_a_source")
            assert mock_single.call_args.args[2] == "pubmed"  # default

    # ---- normalise ----------------------------------------------------------

    def test_normalize_paper_data_missing_fields(self, searcher):
        result = searcher._normalize_paper_data({"pmid": "12345", "title": "x"}, "pubmed")
        assert result["doi"] == ""
        assert result["authors"] == []

    def test_normalize_paper_data_complete(self, searcher):
        paper = {
            "pmid": "12345",
            "doi": "10.1000/test",
            "title": "Test Paper",
            "authors": ["A 1", "A 2"],
            "journal": "T Journal",
            "year": "2020",
            "abstract": "x",
        }
        result = searcher._normalize_paper_data(paper, "pubmed")
        assert result["doi"] == "10.1000/test"
        assert len(result["authors"]) == 2

    # ---- public surface guard ----------------------------------------------

    def test_only_one_public_search_entry(self, searcher):
        public = {
            n
            for n in dir(searcher)
            if not n.startswith("_")
            and callable(getattr(searcher, n))
            and "search" in n
        }
        assert public == {"search_papers"}, (
            "PaperSearcher should expose only search_papers publicly; "
            f"found: {sorted(public)}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
