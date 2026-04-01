import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdfget.fetcher import PaperFetcher
from pdfget.searcher import PaperSearcher

ARXIV_ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.12345v2</id>
    <published>2023-01-30T12:00:00Z</published>
    <updated>2023-02-01T12:00:00Z</updated>
    <title> Test arXiv Paper </title>
    <summary> Test abstract for arXiv paper. </summary>
    <author><name>Author One</name></author>
    <author><name>Author Two</name></author>
    <arxiv:doi>10.48550/arXiv.2301.12345</arxiv:doi>
    <link rel="alternate" type="text/html" href="http://arxiv.org/abs/2301.12345v2"/>
    <link title="pdf" rel="related" type="application/pdf" href="http://arxiv.org/pdf/2301.12345v2"/>
  </entry>
</feed>
"""


class TestArxivSearcher:
    def setup_method(self):
        self.session = Mock()
        self.searcher = PaperSearcher(self.session)

    def test_search_arxiv_api_parses_atom_response(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.text = ARXIV_ATOM_RESPONSE
        self.session.get.return_value = response

        papers = self.searcher.search_arxiv("transformer", limit=5)

        assert len(papers) == 1
        paper = papers[0]
        assert paper["source"] == "arxiv"
        assert paper["arxiv_id"] == "2301.12345v2"
        assert paper["title"] == "Test arXiv Paper"
        assert paper["authors"] == ["Author One", "Author Two"]
        assert paper["abstract"] == "Test abstract for arXiv paper."
        assert paper["pdf_url"] == "http://arxiv.org/pdf/2301.12345v2"
        assert paper["doi"] == "10.48550/arXiv.2301.12345"
        assert paper["year"] == "2023"

    def test_search_papers_arxiv_source(self):
        with patch.object(self.searcher, "search_arxiv", return_value=[]) as mock_search:
            self.searcher.search_papers("transformer", source="arxiv")
            mock_search.assert_called_once_with("transformer", 50)


class TestArxivFetcher:
    def setup_method(self):
        self.fetcher = PaperFetcher(cache_dir="test_cache", output_dir="test_output")

    @patch("pdfget.searcher.PaperSearcher.search_papers")
    def test_fetcher_search_papers_arxiv_source(self, mock_search):
        mock_search.return_value = [
            {
                "title": "Test arXiv Paper",
                "authors": ["Author One"],
                "year": "2023",
                "source": "arxiv",
                "arxiv_id": "2301.12345",
                "pdf_url": "http://arxiv.org/pdf/2301.12345",
            }
        ]

        papers = self.fetcher.search_papers("transformer", source="arxiv", use_cache=False)

        assert len(papers) == 1
        assert papers[0]["arxiv_id"] == "2301.12345"
        mock_search.assert_called_once_with("transformer", 50, "arxiv")
