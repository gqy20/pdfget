#!/usr/bin/env python3
"""异常处理装饰器测试用例"""

from unittest.mock import Mock

import pytest
import requests

from pdfget.utils.error_handling import handle_ncbi_errors


class TestErrorHandlingDecorator:
    """异常处理装饰器测试"""

    @pytest.fixture
    def mock_logger(self):
        """Mock日志器"""
        logger = Mock()
        return logger

    def test_timeout_exception_handling(self, mock_logger):
        """测试超时异常处理"""

        @handle_ncbi_errors(default_return=[], logger=mock_logger)
        def test_function():
            raise requests.exceptions.Timeout("Request timeout")

        result = test_function()
        assert result == []
        mock_logger.error.assert_called_once_with("请求超时")

    def test_request_exception_handling(self, mock_logger):
        """测试请求异常处理"""

        @handle_ncbi_errors(default_return=None, logger=mock_logger)
        def test_function():
            raise requests.exceptions.RequestException("Network error")

        result = test_function()
        assert result is None
        mock_logger.error.assert_called_once_with("请求失败: Network error")

    def test_connection_exception_handling(self, mock_logger):
        """测试连接异常处理"""

        @handle_ncbi_errors(default_return=False, logger=mock_logger)
        def test_function():
            raise requests.exceptions.ConnectionError("Connection failed")

        result = test_function()
        assert result is False
        mock_logger.error.assert_called_once_with("连接失败: Connection failed")

    def test_http_exception_handling(self, mock_logger):
        """测试HTTP异常处理"""

        @handle_ncbi_errors(default_return={}, logger=mock_logger)
        def test_function():
            raise requests.exceptions.HTTPError("404 Not Found")

        result = test_function()
        assert result == {}
        mock_logger.error.assert_called_once_with("HTTP错误: 404 Not Found")

    def test_general_exception_handling(self, mock_logger):
        """测试通用异常处理"""

        @handle_ncbi_errors(default_return="error", logger=mock_logger)
        def test_function():
            raise ValueError("Invalid value")

        result = test_function()
        assert result == "error"
        mock_logger.error.assert_called_once_with("未知错误: Invalid value")

    def test_successful_execution(self, mock_logger):
        """测试正常执行情况"""

        @handle_ncbi_errors(default_return="error", logger=mock_logger)
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"
        mock_logger.error.assert_not_called()

    def test_default_return_none(self):
        """测试默认返回None"""

        @handle_ncbi_errors()
        def test_function():
            raise requests.exceptions.Timeout("Timeout")

        result = test_function()
        assert result is None

    def test_logger_from_instance(self):
        """测试从实例获取日志器"""

        class TestClass:
            def __init__(self):
                self.logger = Mock()

            @handle_ncbi_errors(default_return=[])
            def method_with_error(self):
                raise requests.exceptions.RequestException("Error")

        obj = TestClass()
        result = obj.method_with_error()
        assert result == []
        obj.logger.error.assert_called_once_with("请求失败: Error")

    def test_custom_error_message(self, mock_logger):
        """测试自定义错误消息"""

        @handle_ncbi_errors(error_message="自定义错误", logger=mock_logger)
        def test_function():
            raise requests.exceptions.RequestException("Error")

        test_function()
        mock_logger.error.assert_called_once_with("自定义错误请求失败: Error")

    def test_no_logger_fallback(self, caplog):
        """测试无日志器时的回退"""

        @handle_ncbi_errors(default_return=[])
        def test_function():
            raise requests.exceptions.Timeout("Timeout")

        with caplog.at_level("ERROR"):
            result = test_function()
            assert result == []
            assert "请求超时" in caplog.text

    def test_function_with_arguments(self, mock_logger):
        """测试带参数的函数"""

        @handle_ncbi_errors(default_return=[], logger=mock_logger)
        def test_function(arg1, arg2, kwarg1=None):
            if arg1 == "error":
                raise requests.exceptions.RequestException("Error")
            return [arg1, arg2, kwarg1]

        # 正常情况
        result = test_function("test", "value", kwarg1="kwvalue")
        assert result == ["test", "value", "kwvalue"]

        # 异常情况
        result = test_function("error", "value")
        assert result == []
