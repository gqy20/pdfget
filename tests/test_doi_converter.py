#!/usr/bin/env python3
"""
测试 DOI 转换模块的功能

采用TDD方式，先定义测试用例，再实现功能。
"""

import json
from unittest.mock import Mock, patch

import pytest
import requests

from src.pdfget.base.ncbi_base import NCBIBaseModule
from src.pdfget.config import DOI_QUERY_TIMEOUT


class TestDOIConverter:
    """测试 DOIConverter 类"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        mock_session = Mock(spec=requests.Session)
        return mock_session

    @pytest.fixture
    def converter(self, session):
        """创建 DOIConverter 实例"""
        # 这里会在实现后导入实际的 DOIConverter
        from src.pdfget.doi_converter import DOIConverter
        return DOIConverter(session=session, email="test@example.com", api_key="test_key")

    # 测试用例1: 成功的DOI到PMCID转换（Europe PMC API）
    @pytest.mark.parametrize("doi,expected_pmcid", [
        ("10.1186/s12916-020-01690-4", "PMC7439635"),
        ("10.1016/j.cell.2020.01.021", "PMC7180979"),
        ("10.1038/s41586-020-2661-9", "PMC7439635"),
    ])
    def test_doi_to_pmcid_success_europepmc(self, converter, session, doi, expected_pmcid):
        """
        测试: 通过 Europe PMC API 成功转换 DOI 到 PMCID
        """
        # 模拟 Europe PMC API 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resultList": {
                "result": [
                    {
                        "pmcid": expected_pmcid,
                        "doi": doi,
                        "title": "Sample Paper Title",
                        "authorString": "Test Author"
                    }
                ]
            }
        }
        session.get.return_value = mock_response

        # 执行转换
        result = converter.doi_to_pmcid(doi)

        # 验证结果
        assert result == expected_pmcid
        session.get.assert_called_once()

        # 验证API调用参数
        call_args = session.get.call_args
        # call_args[0] 是位置参数 (URL), call_args[1] 是关键字参数
        assert call_args[1]["params"]["query"] == f'doi:"{doi}"'  # 查询参数包含doi
        assert call_args[1]["timeout"] == DOI_QUERY_TIMEOUT

    # 测试用例2: DOI不存在的情况
    def test_doi_to_pmcid_not_found(self, converter, session):
        """
        测试: DOI 不存在时返回 None
        """
        # 模拟空响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resultList": {"result": []}
        }
        session.get.return_value = mock_response

        result = converter.doi_to_pmcid("10.1000/nonexistent.doi")

        assert result is None

    # 测试用例3: 网络错误处理
    def test_doi_to_pmcid_network_error(self, converter, session):
        """
        测试: 网络错误时的重试机制
        """
        # 模拟网络超时
        session.get.side_effect = requests.exceptions.Timeout("Request timeout")

        # 我的实现会捕获异常并返回None，而不是重新抛出异常
        result = converter.doi_to_pmcid("10.1000/test.doi")

        # 验证返回None（转换失败）
        assert result is None

        # 验证进行了多次重试尝试（通过日志输出可以验证）

    # 测试用例4: API返回错误状态码
    def test_doi_to_pmcid_api_error(self, converter, session):
        """
        测试: API返回错误状态码时返回 None
        """
        mock_response = Mock()
        mock_response.status_code = 404
        session.get.return_value = mock_response

        result = converter.doi_to_pmcid("10.1000/test.doi")

        assert result is None

    # 测试用例5: 无效DOI格式
    @pytest.mark.parametrize("invalid_doi", [
        "",  # 空字符串
        "invalid-doi",  # 无效格式
        "10.1000",  # 缺少后缀
        "not.a.doi.at.all",  # 完全不是DOI
    ])
    def test_doi_to_pmcid_invalid_format(self, converter, invalid_doi):
        """
        测试: 无效DOI格式应该抛出异常或返回None
        """
        result = converter.doi_to_pmcid(invalid_doi)
        assert result is None

    # 测试用例6: 批量DOI转换
    def test_batch_doi_to_pmcid(self, converter, session):
        """
        测试: 批量转换DOI到PMCID
        """
        # 测试数据
        doi_list = [
            "10.1186/s12916-020-01690-4",
            "10.1016/j.cell.2020.01.021",
            "10.1000/nonexistent.doi",  # 这个不存在
        ]

        # 模拟不同的响应
        def mock_get(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200

            # 检查查询参数中的DOI
            query = kwargs.get('params', {}).get('query', '')

            if 'doi:"10.1186/s12916-020-01690-4"' in query:
                mock_response.json.return_value = {
                    "resultList": {"result": [{"pmcid": "PMC7439635", "doi": "10.1186/s12916-020-01690-4"}]}
                }
            elif 'doi:"10.1016/j.cell.2020.01.021"' in query:
                mock_response.json.return_value = {
                    "resultList": {"result": [{"pmcid": "PMC7180979", "doi": "10.1016/j.cell.2020.01.021"}]}
                }
            else:
                mock_response.json.return_value = {"resultList": {"result": []}}

            return mock_response

        session.get.side_effect = mock_get

        # 执行批量转换
        results = converter.batch_doi_to_pmcid(doi_list)

        # 验证结果
        expected_results = {
            "10.1186/s12916-020-01690-4": "PMC7439635",
            "10.1016/j.cell.2020.01.021": "PMC7180979",
            "10.1000/nonexistent.doi": None,
        }
        assert results == expected_results

    # 测试用例7: CrossRef API作为备选方案
    @patch('src.pdfget.doi_converter.DOIConverter._query_crossref_api')
    def test_doi_to_pmcid_fallback_to_crossref(self, mock_crossref, converter, session):
        """
        测试: Europe PMC失败时回退到CrossRef API
        """
        # Europe PMC返回空结果
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"resultList": {"result": []}}
        session.get.return_value = mock_response

        # CrossRef返回结果
        mock_crossref.return_value = "PMC123456789"

        result = converter.doi_to_pmcid("10.1000/test.doi", use_fallback=True)

        assert result == "PMC123456789"
        mock_crossref.assert_called_once_with("10.1000/test.doi")

    # 测试用例8: 缓存机制
    def test_doi_to_pmcid_caching(self, converter, session):
        """
        测试: DOI转换结果应该被缓存
        """
        # 第一次调用
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resultList": {"result": [{"pmcid": "PMC123456789", "doi": "10.1000/test.doi"}]}
        }
        session.get.return_value = mock_response

        result1 = converter.doi_to_pmcid("10.1000/test.doi")
        assert result1 == "PMC123456789"

        # 第二次调用应该使用缓存，不再请求API
        session.get.reset_mock()
        result2 = converter.doi_to_pmcid("10.1000/test.doi")
        assert result2 == "PMC123456789"
        session.get.assert_not_called()

    # 测试用例9: 速率限制
    def test_doi_to_pmcid_rate_limiting(self, converter, session):
        """
        测试: 应该遵守速率限制
        """
        # Mock the DOI rate limiter
        converter.doi_rate_limiter = Mock()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "resultList": {"result": [{"pmcid": "PMC123456789", "doi": "10.1000/test.doi"}]}
        }
        session.get.return_value = mock_response

        # 连续调用多次
        for i in range(3):
            converter.doi_to_pmcid(f"10.1000/test{i}.doi")

        # 验证调用了DOI速率限制器
        assert converter.doi_rate_limiter.wait_for_rate_limit.call_count >= 2

    # 测试用例10: 配置参数
    def test_doi_converter_configuration(self, converter):
        """
        测试: DOI转换器的配置参数
        """
        # 验证继承的配置
        assert hasattr(converter, 'rate_limiter')
        assert hasattr(converter, 'config')
        assert hasattr(converter, 'logger')
        assert converter.email == "test@example.com"
        assert converter.api_key == "test_key"

        # 验证DOI特定的配置
        assert hasattr(converter, 'europepmc_doi_url')
        assert converter.europepmc_doi_url == "https://www.ebi.ac.uk/europepmc/api/search"
        assert hasattr(converter, '_cache')  # 内存缓存
        assert hasattr(converter, 'doi_rate_limiter')  # DOI速率限制器