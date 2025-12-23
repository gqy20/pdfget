#!/usr/bin/env python3
"""NCBI基类测试用例"""

from unittest.mock import Mock, patch

import pytest

from pdfget.base.ncbi_base import NCBIBaseModule
from pdfget.utils import RateLimiter


class TestNCBIBaseModule:
    """NCBI基类测试"""

    @pytest.fixture
    def mock_session(self):
        """Mock requests.Session"""
        return Mock()

    @pytest.fixture
    def ncbi_module(self, mock_session):
        """创建NCBI基类实例"""
        return NCBIBaseModule(
            session=mock_session, email="test@example.com", api_key="test_api_key"
        )

    def test_init_with_email_and_api_key(self, mock_session):
        """测试使用邮箱和API密钥初始化"""
        module = NCBIBaseModule(
            session=mock_session, email="test@example.com", api_key="test_key"
        )

        assert module.session == mock_session
        assert module.email == "test@example.com"
        assert module.api_key == "test_key"
        assert module.base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        assert isinstance(module.rate_limiter, RateLimiter)
        # config 现在是一个简单的字典
        assert isinstance(module.config, dict)
        assert "timeouts" in module.config
        assert "rate_limit" in module.config

    def test_init_without_email_and_api_key(self, mock_session):
        """测试不使用邮箱和API密钥初始化"""
        module = NCBIBaseModule(session=mock_session)

        assert module.session == mock_session
        assert module.email == ""
        assert module.api_key == ""
        assert module.base_url == "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    def test_rate_limit_delegation(self, ncbi_module):
        """测试限流方法委托"""
        with patch.object(ncbi_module.rate_limiter, "wait_for_rate_limit") as mock_wait:
            ncbi_module._rate_limit()
            mock_wait.assert_called_once()

    def test_logger_initialization(self, ncbi_module):
        """测试日志器初始化"""
        assert hasattr(ncbi_module, "logger")
        assert ncbi_module.logger is not None

    def test_network_config_setup(self, ncbi_module):
        """测试网络配置设置"""
        # config 现在是一个简单的字典
        assert isinstance(ncbi_module.config, dict)
        assert "timeouts" in ncbi_module.config
        assert "rate_limit" in ncbi_module.config
        # 验证超时配置的值
        assert "download" in ncbi_module.config["timeouts"]
        assert "request" in ncbi_module.config["timeouts"]

    def test_session_passed_correctly(self, mock_session):
        """测试session正确传递"""
        module = NCBIBaseModule(session=mock_session)
        assert module.session is mock_session

    def test_base_url_constant(self, ncbi_module):
        """测试基础URL常量"""
        expected_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        assert ncbi_module.base_url == expected_url

    def test_rate_limiter_config(self, ncbi_module):
        """测试限流器配置"""
        # config 现在是字典，使用字典访问
        assert ncbi_module.rate_limiter.rate_limit == ncbi_module.config["rate_limit"]
