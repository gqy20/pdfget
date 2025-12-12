"""
集成测试 - 测试摘要补充功能与搜索器的集成
"""

from unittest.mock import patch

from src.pdfget.fetcher import PaperFetcher


class TestAbstractSupplementIntegration:
    """测试摘要补充集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.fetcher = PaperFetcher(cache_dir="test_cache")

    @patch("src.pdfget.abstract_supplementor.requests.get")
    @patch("src.pdfget.searcher.requests.Session.get")
    def test_europe_pmc_search_with_abstract_supplement(self, mock_search, mock_xml):
        """测试：Europe PMC 搜索时补充摘要"""
        # 模拟搜索返回（无摘要）
        mock_search_response = {
            "resultList": {
                "result": [
                    {
                        "pmid": "12345678",
                        "pmcid": "PMC12345678",
                        "title": "Test Article 1",
                        "inPMC": "Y",
                    },
                    {
                        "pmid": "87654321",
                        "pmcid": "PMC87654321",
                        "title": "Test Article 2",
                        "inPMC": "Y",
                    },
                ]
            },
            "hitCount": 2,
            "nextCursorMark": "next_cursor",
        }

        mock_search.return_value.json.return_value = mock_search_response
        mock_search.return_value.raise_for_status.return_value = None

        # 模拟 XML 响应
        def xml_side_effect(url, **kwargs):
            from unittest.mock import Mock

            import requests

            response = Mock(spec=requests.Response)
            response.raise_for_status.return_value = None

            if "PMC12345678" in url:
                response.text = """
                <article>
                    <abstract>
                        <p>Abstract for article 1. This is a test abstract.</p>
                    </abstract>
                </article>
                """
            elif "PMC87654321" in url:
                response.text = """
                <article>
                    <abstract>
                        <p>Abstract for article 2. Another test abstract.</p>
                    </abstract>
                </article>
                """

            return response

        mock_xml.side_effect = xml_side_effect

        # 执行搜索
        papers = self.fetcher.search_papers(
            "test query", limit=10, source="europe_pmc", use_cache=False
        )

        # 验证结果
        assert len(papers) == 2
        assert papers[0]["title"] == "Test Article 1"
        assert papers[1]["title"] == "Test Article 2"

        # 验证摘要已被补充
        assert (
            papers[0]["abstract"] == "Abstract for article 1. This is a test abstract."
        )
        assert papers[1]["abstract"] == "Abstract for article 2. Another test abstract."
        assert papers[0]["abstract_source"] == "xml"
        assert papers[1]["abstract_source"] == "xml"

    @patch("src.pdfget.abstract_supplementor.requests.get")
    @patch("src.pdfget.searcher.requests.Session.get")
    def test_europe_pmc_search_with_existing_abstract(self, mock_search, mock_xml):
        """测试：已有摘要时不再补充"""
        # 模拟搜索返回（有摘要）
        mock_search_response = {
            "resultList": {
                "result": [
                    {
                        "pmid": "12345678",
                        "pmcid": "PMC12345678",
                        "title": "Test Article",
                        "abstractText": "Existing abstract from API",
                    }
                ]
            },
            "hitCount": 1,
        }

        mock_search.return_value.json.return_value = mock_search_response
        mock_search.return_value.raise_for_status.return_value = None

        # 执行搜索
        papers = self.fetcher.search_papers(
            "test query", limit=10, source="europe_pmc", use_cache=False
        )

        # 验证结果
        assert len(papers) == 1
        assert papers[0]["abstract"] == "Existing abstract from API"
        assert papers[0]["abstract_source"] == "api"

        # 确保没有调用 XML 获取
        mock_xml.assert_not_called()

    @patch("src.pdfget.abstract_supplementor.requests.get")
    @patch("src.pdfget.searcher.requests.Session.get")
    def test_pubmed_search_no_supplement(self, mock_search, mock_xml):
        """测试：PubMed 搜索不进行摘要补充（MVP版本限制）"""
        # 模拟搜索返回
        mock_search.return_value.json.return_value = {
            "esearchresult": {"idlist": ["12345678"]},
            "esummaryresult": {},
        }
        mock_search.return_value.raise_for_status.return_value = None

        # 执行搜索
        self.fetcher.search_papers(
            "test query", limit=10, source="pubmed", use_cache=False
        )

        # 确保没有调用摘要补充
        mock_xml.assert_not_called()

    @patch("src.pdfget.abstract_supplementor.requests.get")
    @patch("src.pdfget.searcher.requests.Session.get")
    def test_partial_abstract_supplement(self, mock_search, mock_xml):
        """测试：部分摘要补充成功"""
        # 模拟搜索返回（部分有摘要）
        mock_search_response = {
            "resultList": {
                "result": [
                    {
                        "pmid": "11111111",
                        "pmcid": "PMC11111111",
                        "title": "Article with abstract",
                        "abstractText": "Existing abstract",
                    },
                    {
                        "pmid": "22222222",
                        "pmcid": "PMC22222222",
                        "title": "Article without abstract",
                        "inPMC": "Y",
                    },
                    {
                        "pmid": "33333333",
                        "pmcid": "PMC33333333",
                        "title": "Another without abstract",
                        "inPMC": "Y",
                    },
                ]
            },
            "hitCount": 3,
        }

        mock_search.return_value.json.return_value = mock_search_response
        mock_search.return_value.raise_for_status.return_value = None

        # 模拟 XML 响应（只对缺少摘要的请求）
        def xml_side_effect(url, **kwargs):
            from unittest.mock import Mock

            import requests

            response = Mock(spec=requests.Response)
            response.raise_for_status.return_value = None

            if "PMC22222222" in url:
                response.text = "<article><abstract><p>Supplemented abstract 2</p></abstract></article>"
            elif "PMC33333333" in url:
                response.text = "<article><abstract><p>Supplemented abstract 3</p></abstract></article>"

            return response

        mock_xml.side_effect = xml_side_effect

        # 执行搜索
        papers = self.fetcher.search_papers(
            "test query", limit=10, source="europe_pmc", use_cache=False
        )

        # 验证结果
        assert len(papers) == 3

        # 第一篇保持原有摘要
        assert papers[0]["abstract"] == "Existing abstract"
        assert papers[0]["abstract_source"] == "api"

        # 第二篇和第三篇被补充
        assert papers[1]["abstract"] == "Supplemented abstract 2"
        assert papers[1]["abstract_source"] == "xml"
        assert papers[2]["abstract"] == "Supplemented abstract 3"
        assert papers[2]["abstract_source"] == "xml"

        # 确保只调用了两次 XML 请求（针对缺少摘要的）
        assert mock_xml.call_count == 2
