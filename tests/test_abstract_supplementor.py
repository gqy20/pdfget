"""
测试摘要补充功能
整合了简单的XML解析测试和完整的摘要补充功能测试
"""

import xml.etree.ElementTree as ET
from unittest.mock import patch

import requests
import requests_mock

from src.pdfget.abstract_supplementor import AbstractSupplementor


# XML 解析函数（从 test_abstract_simple.py 移动过来）
def extract_abstract_from_xml(xml_content):
    """
    从 XML 内容中提取摘要
    这是我们要实现的核心功能
    """
    root = ET.fromstring(xml_content)
    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        # 获取所有文本
        text_content = []
        for elem in abstract_elem.iter():
            if elem.text:
                text_content.append(elem.text)
            if elem.tail:
                text_content.append(elem.tail)
        return " ".join(text_content).strip()
    return None


class TestAbstractExtraction:
    """测试摘要提取功能（从 test_abstract_simple.py 整合）"""

    def test_simple_abstract_extraction(self):
        """测试：简单摘要提取"""
        xml_content = """
        <article>
            <abstract>
                <p>This is a simple abstract.</p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert result == "This is a simple abstract."

    def test_no_abstract_tag(self):
        """测试：无摘要标签"""
        xml_content = """
        <article>
            <title>Article Title</title>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert result is None

    def test_nested_abstract(self):
        """测试：嵌套的摘要结构"""
        xml_content = """
        <article>
            <abstract>
                <sec>
                    <title>Background</title>
                    <p>Background text.</p>
                </sec>
                <sec>
                    <title>Conclusion</title>
                    <p>Conclusion text.</p>
                </sec>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "Background text" in result
        assert "Conclusion text" in result

    def test_whitespace_cleaning(self):
        """测试：空白字符清理"""
        xml_content = """
        <article>
            <abstract>
                <p>
                    Text with    extra
                    spaces.
                </p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "  " not in result
        assert result.startswith("Text with")

    def test_mixed_content(self):
        """测试：混合内容（文本和标签）"""
        xml_content = """
        <article>
            <abstract>
                <p>Text with <bold>bold</bold> and <italic>italic</italic> text.</p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "Text with" in result
        assert "bold" in result
        assert "italic" in result


class TestAbstractSupplementor:
    """测试摘要补充器"""

    def setup_method(self):
        """每个测试前的设置"""
        self.supplementor = AbstractSupplementor()

    def test_no_pmcid_returns_none(self):
        """测试：无 PMCID 时返回 None"""
        paper = {"pmcid": "", "abstract": ""}
        result = self.supplementor.supplement_abstract(paper)
        assert result is None

    def test_has_abstract_returns_none(self):
        """测试：已有摘要时返回 None"""
        paper = {"pmcid": "PMC123456", "abstract": "Existing abstract"}
        result = self.supplementor.supplement_abstract(paper)
        assert result is None

    def test_successful_xml_parsing(self, simple_abstract_xml):
        """测试：成功从 XML 解析摘要"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=simple_abstract_xml,
            )

            result = self.supplementor.supplement_abstract(paper)
            assert result == "This is a test abstract."

    def test_xml_without_abstract(self, xml_without_abstract):
        """测试：XML 中无摘要标签"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=xml_without_abstract,
            )

            result = self.supplementor.supplement_abstract(paper)
            assert result is None

    def test_http_error_handling(self):
        """测试：HTTP 错误处理"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                status_code=404,
            )

            result = self.supplementor.supplement_abstract(paper)
            assert result is None

    def test_timeout_handling(self):
        """测试：超时处理"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            result = self.supplementor.supplement_abstract(paper)
            assert result is None

    def test_complex_abstract_with_nested_tags(self, complex_abstract_xml):
        """测试：包含嵌套标签的复杂摘要"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=complex_abstract_xml,
            )

            result = self.supplementor.supplement_abstract(paper)
            assert "Background paragraph" in result
            assert "Methods paragraph" in result
            assert "bold text" in result

    def test_whitespace_cleaning(self):
        """测试：空白字符清理"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = """
        <article>
            <front>
                <article-meta>
                    <abstract>
                        <p>
                            This abstract has    multiple
                            spaces and
                            tabs.
                        </p>
                    </abstract>
                </article-meta>
            </front>
        </article>
        """

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=xml_content,
            )

            result = self.supplementor.supplement_abstract(paper)
            # 应该清理多余的空白
            assert "  " not in result
            assert "\t" not in result
            assert result.strip() == result

    def test_batch_supplement(self):
        """测试：批量补充摘要"""
        papers = [
            {"pmcid": "PMC123456", "abstract": ""},
            {"pmcid": "PMC789012", "abstract": "Has abstract"},
            {"pmcid": "", "abstract": ""},
            {"pmcid": "PMC345678", "abstract": ""},
        ]

        xml_content1 = "<article><abstract><p>Abstract 1</p></abstract></article>"
        xml_content3 = "<article><abstract><p>Abstract 3</p></abstract></article>"

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=xml_content1,
            )
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC345678/fullTextXML",
                text=xml_content3,
            )

            results = self.supplementor.supplement_abstracts_batch(papers)

            # 检查结果
            assert results[0]["abstract"] == "Abstract 1"  # 被补充
            assert results[1]["abstract"] == "Has abstract"  # 未改变
            assert results[2]["abstract"] == ""  # 无 PMCID
            assert results[3]["abstract"] == "Abstract 3"  # 被补充

    def test_caching_behavior(self):
        """测试：缓存行为"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = "<article><abstract><p>Test abstract</p></abstract></article>"

        with requests_mock.Mocker() as m:
            m.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
                text=xml_content,
            )

            # 第一次调用
            result1 = self.supplementor.supplement_abstract(paper)
            assert result1 == "Test abstract"

            # 第二次调用应该使用缓存（只请求一次）
            result2 = self.supplementor.supplement_abstract(paper)
            assert result2 == "Test abstract"

            # 验证只请求了一次
            assert m.call_count == 1


class TestAbstractSupplementIntegration:
    """测试摘要补充集成（从 test_integration.py 整合）"""

    def setup_method(self):
        """每个测试前的设置"""
        from src.pdfget.fetcher import PaperFetcher

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
