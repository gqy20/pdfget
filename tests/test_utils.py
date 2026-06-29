"""测试共享工具模块"""

import time
from unittest.mock import patch

from pdfget.utils.identifier_utils import IdentifierUtils
from pdfget.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """测试速率限制器"""

    def test_init_default(self):
        """测试默认初始化"""
        limiter = RateLimiter()
        assert limiter.rate_limit == 3
        assert limiter.last_request_time == 0

    def test_init_custom(self):
        """测试自定义初始化"""
        limiter = RateLimiter(rate_limit=10)
        assert limiter.rate_limit == 10

    def test_wait_for_rate_limit_first_call(self):
        """测试第一次调用不应该等待"""
        limiter = RateLimiter(rate_limit=10)
        start_time = time.time()
        limiter.wait_for_rate_limit()
        elapsed = time.time() - start_time
        # 第一次调用应该立即返回
        assert elapsed < 0.1

    def test_wait_for_rate_limit_subsequent_calls(self):
        """测试后续调用应该等待"""
        limiter = RateLimiter(rate_limit=10)  # 0.1秒间隔
        limiter.wait_for_rate_limit()
        start_time = time.time()
        limiter.wait_for_rate_limit()
        elapsed = time.time() - start_time
        # 应该等待约0.1秒
        assert 0.08 <= elapsed <= 0.2

    def test_wait_for_rate_limit_different_rates(self):
        """测试不同速率限制"""
        limiter = RateLimiter(rate_limit=2)  # 0.5秒间隔
        limiter.wait_for_rate_limit()
        start_time = time.time()
        limiter.wait_for_rate_limit()
        elapsed = time.time() - start_time
        # 应该等待约0.5秒
        assert 0.4 <= elapsed <= 0.8

    @patch("time.time")
    @patch("time.sleep")
    def test_wait_for_rate_limit_no_wait_needed(self, mock_sleep, mock_time):
        """测试不需要等待的情况"""
        limiter = RateLimiter(rate_limit=1, last_request_time=0.0)

        # 第一次调用time.time()返回1.0（1秒后）
        mock_time.return_value = 1.0

        limiter.wait_for_rate_limit()

        # 不应该调用sleep
        mock_sleep.assert_not_called()

    @patch("time.time")
    @patch("time.sleep")
    def test_wait_for_rate_limit_wait_needed(self, mock_sleep, mock_time):
        """测试需要等待的情况"""
        limiter = RateLimiter(rate_limit=2, last_request_time=0.0)

        # 第一次调用time.time()返回0.3（0.3秒后），需要等待0.2秒
        mock_time.return_value = 0.3

        limiter.wait_for_rate_limit()

        # 应该等待0.2秒（0.5 - 0.3）
        mock_sleep.assert_called_once_with(0.2)


class TestIdentifierUtils:
    """测试标识符工具"""

    def test_detect_identifier_type_pmcid(self):
        """测试PMCID检测"""
        assert IdentifierUtils.detect_identifier_type("PMC123456") == "pmcid"
        assert IdentifierUtils.detect_identifier_type("pmc123456") == "pmcid"

    def test_detect_identifier_type_pmid(self):
        """测试PMID检测"""
        assert IdentifierUtils.detect_identifier_type("12345678") == "pmid"
        assert IdentifierUtils.detect_identifier_type("1234567890") == "pmid"

    def test_detect_identifier_type_doi(self):
        """测试DOI检测"""
        assert IdentifierUtils.detect_identifier_type("10.1038/nature12373") == "doi"
        assert IdentifierUtils.detect_identifier_type("10.1000/xyz") == "doi"

    def test_detect_identifier_type_invalid(self):
        """测试无效标识符"""
        assert IdentifierUtils.detect_identifier_type("") == "unknown"
        assert IdentifierUtils.detect_identifier_type("invalid") == "unknown"
        assert IdentifierUtils.detect_identifier_type("123") == "unknown"  # 太短
        assert (
            IdentifierUtils.detect_identifier_type("123456789012") == "unknown"
        )  # 太长

    def test_normalize_pmcid_with_prefix(self):
        """测试带PMC前缀的PMCID标准化"""
        result = IdentifierUtils.normalize_pmcid("PMC123456")
        assert result == "123456"

    def test_normalize_pmcid_without_prefix(self):
        """测试不带PMC前缀的PMCID标准化"""
        result = IdentifierUtils.normalize_pmcid("123456")
        assert result == "123456"

    def test_normalize_pmcid_invalid(self):
        """测试无效PMCID标准化"""
        result = IdentifierUtils.normalize_pmcid("invalid")
        assert result is None

    def test_validate_doi_valid(self):
        """测试有效DOI验证"""
        assert IdentifierUtils.validate_doi("10.1038/nature12373")
        assert IdentifierUtils.validate_doi("10.1000/xyz-abc")

    def test_validate_doi_invalid(self):
        """测试无效DOI验证"""
        assert not IdentifierUtils.validate_doi("invalid")
        assert not IdentifierUtils.validate_doi("10.1038")  # 缺少内容
        assert not IdentifierUtils.validate_doi("xyz.1038/nature12373")  # 错误前缀
