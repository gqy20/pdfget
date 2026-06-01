"""
配置文件测试
"""

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
