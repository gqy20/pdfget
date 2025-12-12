"""
测试摘要补充功能
"""

from unittest.mock import patch

import requests
import requests_mock

from src.pdfget.abstract_supplementor import AbstractSupplementor


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

    def test_successful_xml_parsing(self):
        """测试：成功从 XML 解析摘要"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = """
        <article>
            <front>
                <article-meta>
                    <abstract>
                        <p>This is a test abstract.</p>
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
            assert result == "This is a test abstract."

    def test_xml_without_abstract(self):
        """测试：XML 中无摘要标签"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = """
        <article>
            <front>
                <article-meta>
                    <title>Test Title</title>
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

    def test_complex_abstract_with_nested_tags(self):
        """测试：包含嵌套标签的复杂摘要"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = """
        <article>
            <front>
                <article-meta>
                    <abstract>
                        <sec>
                            <title>Background</title>
                            <p>Background paragraph.</p>
                        </sec>
                        <sec>
                            <title>Methods</title>
                            <p>Methods paragraph with <bold>bold text</bold>.</p>
                        </sec>
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
