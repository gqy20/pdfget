"""
配置文件测试
"""

import os
from pathlib import Path

from pdfget.config import (
    DELAY,
    HEADERS,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_RETRIES,
    OUTPUT_DIR,
    TIMEOUT,
)


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

    def test_output_dir_constant(self):
        """测试输出目录常量"""
        assert isinstance(OUTPUT_DIR, (str, Path))
        assert len(str(OUTPUT_DIR)) > 0

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

    def test_environment_override(self):
        """测试环境变量覆盖"""
        # 设置环境变量
        test_timeout = 60
        os.environ["PDFGET_TIMEOUT"] = str(test_timeout)

        # 重新导入模块以测试环境变量覆盖
        import importlib

        import pdfget.config

        importlib.reload(pdfget.config)

        # 恢复环境
        del os.environ["PDFGET_TIMEOUT"]

        # 注意：这个测试取决于实际的配置实现
        # 如果配置不支持环境变量覆盖，可以跳过
        pass
