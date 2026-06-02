"""
配置文件测试
"""

import importlib

import pdfget.config as config_module
from pdfget.config import DELAY, HEADERS, LOG_FORMAT, LOG_LEVEL, MAX_RETRIES, TIMEOUT


class TestConfig:
    """配置测试类"""

    def test_timeout_constant(self):
        """测试超时常量"""
        assert isinstance(TIMEOUT, int)
        assert TIMEOUT > 0

    def test_max_retries_constant(self):
        """测试最大重试次数常量"""
        assert isinstance(MAX_RETRIES, int)
        assert MAX_RETRIES >= 0

    def test_delay_constant(self):
        """测试延迟常量"""
        assert isinstance(DELAY, (int, float))
        assert DELAY >= 0

    def test_log_level_constant(self):
        """测试日志级别常量"""
        assert LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_log_format_constant(self):
        """测试日志格式常量"""
        assert isinstance(LOG_FORMAT, str)
        assert "%(asctime)s" in LOG_FORMAT
        assert "%(levelname)s" in LOG_FORMAT

    def test_headers_constant(self):
        """测试请求头常量"""
        assert isinstance(HEADERS, dict)
        assert "User-Agent" in HEADERS
        assert len(HEADERS["User-Agent"]) > 0

    def test_config_values_are_reasonable(self):
        """测试配置值的合理性"""
        # 超时时间应该在合理范围内（10-300秒）
        assert 10 <= TIMEOUT <= 300

        # 最大重试次数应该在合理范围内（0-10次）
        assert 0 <= MAX_RETRIES <= 10

        # 延迟时间应该在合理范围内（0-60秒）
        assert 0 <= DELAY <= 60

    def test_ncbi_credentials_from_environment(self, monkeypatch):
        """测试 NCBI 凭据从环境变量读取"""
        monkeypatch.setenv("PDFGET_NCBI_EMAIL", "user@example.com")
        monkeypatch.setenv("PDFGET_NCBI_API_KEY", "secret-key")

        reloaded = importlib.reload(config_module)

        assert reloaded.NCBI_EMAIL == "user@example.com"
        assert reloaded.NCBI_API_KEY == "secret-key"

        monkeypatch.delenv("PDFGET_NCBI_EMAIL", raising=False)
        monkeypatch.delenv("PDFGET_NCBI_API_KEY", raising=False)
        importlib.reload(config_module)
