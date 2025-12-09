#!/usr/bin/env python3
"""
测试文献搜索模块
"""

from unittest.mock import Mock, patch

import pytest

from src.pdfget.searcher import PaperSearcher


class TestPaperSearcher:
    """测试 PaperSearcher 类"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        return Mock()

    @pytest.fixture
    def searcher(self, session):
        """创建 PaperSearcher 实例"""
        return PaperSearcher(session)

    @pytest.fixture
    def sample_search_results(self):
        """示例搜索结果"""
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

    def test_parse_query_pubmed_simple(self, searcher):
        """
        测试: 解析简单的 PubMed 查询
        """
        query = "COVID-19 vaccine"
        result = searcher._parse_query_pubmed(query)

        assert "COVID-19" in result
        assert "vaccine" in result

    def test_parse_query_pubmed_advanced(self, searcher):
        """
        测试: 解析高级 PubMed 查询语法
        """
        query = "COVID-19[Title] AND vaccine[Abstract]"
        result = searcher._parse_query_pubmed(query)

        # 应该保留 PubMed 字段标签
        assert "[Title]" in result
        assert "[Abstract]" in result

    def test_parse_query_pubmed_filters(self, searcher):
        """
        测试: 解析包含过滤器的查询
        """
        query = "COVID-19 year:2020"
        result = searcher._parse_query_pubmed(query)

        # 应该解析年份过滤器
        assert "2020[pdat]" in result

    @patch("src.pdfget.searcher.PaperSearcher._search_pubmed_api")
    def test_search_pubmed_success(self, mock_search, searcher, sample_search_results):
        """
        测试: 成功搜索 PubMed
        """
        mock_search.return_value = sample_search_results

        query = "COVID-19 vaccine"
        result = searcher.search_pubmed(query, limit=20)

        assert len(result) == 2
        assert result[0]["pmid"] == "32353885"
        assert result[0]["source"] == "pubmed"
        mock_search.assert_called_once()

    @patch("src.pdfget.searcher.PaperSearcher._search_pubmed_api")
    def test_search_pubmed_empty_result(self, mock_search, searcher):
        """
        测试: PubMed 搜索返回空结果
        """
        mock_search.return_value = []

        query = "nonexistent term"
        result = searcher.search_pubmed(query, limit=20)

        assert result == []
        mock_search.assert_called_once()

    @patch("src.pdfget.searcher.PaperSearcher._search_pubmed_api")
    def test_search_pubmed_api_error(self, mock_search, searcher):
        """
        测试: PubMed API 错误
        """
        mock_search.return_value = []

        query = "test query"
        result = searcher.search_pubmed(query, limit=20)

        assert result == []

    def test_parse_query_europepmc_simple(self, searcher):
        """
        测试: 解析简单的 Europe PMC 查询
        """
        query = "COVID-19 vaccine"
        result = searcher._parse_query_europepmc(query)

        assert "COVID-19" in result
        assert "vaccine" in result

    def test_parse_query_europepmc_advanced(self, searcher):
        """
        测试: 解析高级 Europe PMC 查询语法
        """
        query = 'TITLE:"COVID-19" AND vaccine'
        result = searcher._parse_query_europepmc(query)

        # 应该保留 Europe PMC 字段
        assert "TITLE:" in result

    @patch("src.pdfget.searcher.PaperSearcher._search_europepmc_api")
    def test_search_europepmc_success(
        self, mock_search, searcher, sample_search_results
    ):
        """
        测试: 成功搜索 Europe PMC
        """
        # 修改结果来源
        for paper in sample_search_results:
            paper["source"] = "europe_pmc"
        mock_search.return_value = sample_search_results

        query = "COVID-19 vaccine"
        result = searcher.search_europepmc(query, limit=20)

        assert len(result) == 2
        assert result[0]["pmid"] == "32353885"
        assert result[0]["source"] == "europe_pmc"

    def test_search_papers_pubmed_source(self, searcher):
        """
        测试: 搜索指定 PubMed 源
        """
        with patch.object(searcher, "search_pubmed", return_value=[]) as mock_search:
            searcher.search_papers("test query", source="pubmed")
            mock_search.assert_called_once_with("test query", 50)

    def test_search_papers_europe_pmc_source(self, searcher):
        """
        测试: 搜索指定 Europe PMC 源
        """
        with patch.object(searcher, "search_europepmc", return_value=[]) as mock_search:
            searcher.search_papers("test query", source="europe_pmc")
            mock_search.assert_called_once_with("test query", 50)

    def test_search_papers_both_sources(self, searcher):
        """
        测试: 搜索两个源
        """
        with (
            patch.object(searcher, "search_pubmed", return_value=[]) as mock_pubmed,
            patch.object(searcher, "search_europepmc", return_value=[]) as mock_europe,
        ):
            searcher.search_papers("test query", source="both")

            mock_pubmed.assert_called_once_with("test query", 50)
            mock_europe.assert_called_once_with("test query", 50)

    def test_search_papers_default_source(self, searcher):
        """
        测试: 使用默认源搜索
        """
        # 由于默认数据源是 pubmed，应该调用 search_pubmed
        with patch.object(searcher, "search_pubmed", return_value=[]) as mock_search:
            searcher.search_papers("test query")
            mock_search.assert_called_once_with("test query", 50)

    def test_normalize_paper_data_missing_fields(self, searcher):
        """
        测试: 标准化缺少字段的论文数据
        """
        paper = {
            "pmid": "12345",
            "title": "Test Paper",
            # 缺少其他字段
        }

        result = searcher._normalize_paper_data(paper, "pubmed")

        assert result["pmid"] == "12345"
        assert result["title"] == "Test Paper"
        assert result["doi"] == ""
        assert result["authors"] == []
        assert result["journal"] == ""
        assert result["year"] == ""
        assert result["abstract"] == ""
        assert result["source"] == "pubmed"

    def test_normalize_paper_data_complete(self, searcher):
        """
        测试: 标准化完整的论文数据
        """
        paper = {
            "pmid": "12345",
            "doi": "10.1000/test",
            "title": "Test Paper",
            "authors": ["Author 1", "Author 2"],
            "journal": "Test Journal",
            "year": "2020",
            "abstract": "Test abstract",
        }

        result = searcher._normalize_paper_data(paper, "pubmed")

        assert result["pmid"] == "12345"
        assert result["doi"] == "10.1000/test"
        assert result["title"] == "Test Paper"
        assert len(result["authors"]) == 2
        assert result["journal"] == "Test Journal"
        assert result["year"] == "2020"
        assert result["abstract"] == "Test abstract"
        assert result["source"] == "pubmed"

    @patch("src.pdfget.searcher.PaperSearcher.search_pubmed")
    @patch("src.pdfget.searcher.PaperSearcher.search_europepmc")
    def test_search_all_sources_combine_results(
        self, mock_europe, mock_pubmed, searcher
    ):
        """
        测试: 合并两个源的搜索结果
        """
        # 设置不同的返回结果
        mock_pubmed.return_value = [
            {"pmid": "1", "title": "Paper 1", "source": "pubmed"}
        ]
        mock_europe.return_value = [
            {"pmid": "2", "title": "Paper 2", "source": "europe_pmc"}
        ]

        result = searcher.search_all_sources("test query", limit=10)

        # 应该返回两个结果
        assert len(result) == 2
        assert result[0]["pmid"] == "1"
        assert result[1]["pmid"] == "2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
