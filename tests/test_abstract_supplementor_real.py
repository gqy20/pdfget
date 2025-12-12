"""
测试摘要补充器 - 与真实模块集成
"""

from unittest.mock import Mock, patch

import requests

from src.pdfget.abstract_supplementor import AbstractSupplementor


class TestAbstractSupplementorReal:
    """测试摘要补充器真实功能"""

    def setup_method(self):
        """每个测试前的设置"""
        self.supplementor = AbstractSupplementor(timeout=5, delay=0)

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

    def test_extract_abstract_from_xml_method(self):
        """测试：XML 解析方法"""
        # 简单摘要
        xml_content = """
        <article>
            <abstract>
                <p>This is a simple abstract.</p>
            </abstract>
        </article>
        """
        result = self.supplementor._extract_abstract_from_xml(xml_content)
        assert result == "This is a simple abstract."

        # 无摘要
        xml_content_no_abstract = """
        <article>
            <title>Article Title</title>
        </article>
        """
        result = self.supplementor._extract_abstract_from_xml(xml_content_no_abstract)
        assert result is None

        # 嵌套摘要
        xml_content_nested = """
        <article>
            <abstract>
                <sec>
                    <title>Background</title>
                    <p>Background text.</p>
                </sec>
                <sec>
                    <title>Methods</title>
                    <p>Methods with <bold>bold text</bold>.</p>
                </sec>
            </abstract>
        </article>
        """
        result = self.supplementor._extract_abstract_from_xml(xml_content_nested)
        assert "Background text" in result
        assert "Methods with" in result
        assert "bold text" in result

    @patch("src.pdfget.abstract_supplementor.requests.get")
    def test_successful_xml_request(self, mock_get):
        """测试：成功的 XML 请求"""
        paper = {"pmcid": "PMC123456", "abstract": ""}
        xml_content = "<article><abstract><p>Test abstract</p></abstract></article>"

        mock_response = Mock()
        mock_response.text = xml_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.supplementor.supplement_abstract(paper)
        assert result == "Test abstract"
        mock_get.assert_called_once_with(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML",
            timeout=5,
        )

    @patch("src.pdfget.abstract_supplementor.requests.get")
    def test_http_error(self, mock_get):
        """测试：HTTP 错误"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        result = self.supplementor.supplement_abstract(paper)
        assert result is None

    @patch("src.pdfget.abstract_supplementor.requests.get")
    def test_timeout_error(self, mock_get):
        """测试：超时错误"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

        result = self.supplementor.supplement_abstract(paper)
        assert result is None

    def test_caching_behavior(self):
        """测试：缓存行为"""
        paper = {"pmcid": "PMC123456", "abstract": ""}

        with patch("src.pdfget.abstract_supplementor.requests.get") as mock_get:
            xml_content = (
                "<article><abstract><p>Cached abstract</p></abstract></article>"
            )
            mock_response = Mock()
            mock_response.text = xml_content
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            # 第一次调用
            result1 = self.supplementor.supplement_abstract(paper)
            assert result1 == "Cached abstract"

            # 第二次调用应该使用缓存
            result2 = self.supplementor.supplement_abstract(paper)
            assert result2 == "Cached abstract"

            # 只请求了一次
            assert mock_get.call_count == 1

    def test_batch_supplement(self):
        """测试：批量补充摘要"""
        papers = [
            {"pmcid": "PMC123456", "abstract": ""},
            {"pmcid": "PMC789012", "abstract": "Has abstract"},
            {"pmcid": "", "abstract": ""},
            {"pmcid": "PMC345678", "abstract": ""},
        ]

        with patch("src.pdfget.abstract_supplementor.requests.get") as mock_get:
            # 模拟不同的响应
            def side_effect(url, timeout=None):
                response = Mock()
                response.raise_for_status.return_value = None
                if "PMC123456" in url:
                    response.text = (
                        "<article><abstract><p>Abstract 1</p></abstract></article>"
                    )
                elif "PMC345678" in url:
                    response.text = (
                        "<article><abstract><p>Abstract 3</p></abstract></article>"
                    )
                return response

            mock_get.side_effect = side_effect

            results = self.supplementor.supplement_abstracts_batch(papers)

            # 验证结果
            assert results[0]["abstract"] == "Abstract 1"
            assert results[0]["abstract_source"] == "xml"
            assert results[1]["abstract"] == "Has abstract"
            assert results[1]["abstract_source"] == "api"
            assert results[2]["abstract"] == ""
            assert results[2]["abstract_source"] == "none"
            assert results[3]["abstract"] == "Abstract 3"
            assert results[3]["abstract_source"] == "xml"

    def test_delay_between_requests(self):
        """测试：请求间隔"""
        import time

        paper1 = {"pmcid": "PMC111111", "abstract": ""}
        paper2 = {"pmcid": "PMC222222", "abstract": ""}

        with patch("src.pdfget.abstract_supplementor.requests.get") as mock_get:

            def side_effect(url, timeout=None):
                response = Mock()
                response.text = (
                    "<article><abstract><p>Abstract</p></abstract></article>"
                )
                response.raise_for_status.return_value = None
                return response

            mock_get.side_effect = side_effect

            # 创建有延迟的补充器
            supplementor = AbstractSupplementor(timeout=5, delay=0.1)

            start_time = time.time()
            supplementor.supplement_abstract(paper1)
            supplementor.supplement_abstract(paper2)
            elapsed = time.time() - start_time

            # 应该有延迟
            assert elapsed >= 0.2  # 两个请求，每个 0.1 秒延迟
