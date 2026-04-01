#!/usr/bin/env python3
"""统一的日志配置模块

提供整个项目的日志配置和管理功能，确保所有模块使用一致的日志格式。
"""

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import LOG_FORMAT, LOG_LEVEL


# 日志颜色配置
class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""

    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",  # 青色
        "INFO": "\033[32m",  # 绿色
        "WARNING": "\033[33m",  # 黄色
        "ERROR": "\033[31m",  # 红色
        "CRITICAL": "\033[35m",  # 紫色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # 添加颜色
        if hasattr(record, "levelname") and record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )

        # 格式化消息
        formatted = super().format(record)

        # 如果消息包含 emoji，不添加额外的颜色
        if any(c in formatted for c in ["🚀", "✅", "❌", "📊", "📄", "🔍", "💾"]):
            return formatted

        return formatted


def setup_logger(
    name: str,
    level: str | None = None,
    log_format: str | None = None,
    use_colors: bool = True,
    log_file: Path | None = None,
) -> logging.Logger:
    """
    设置并返回一个配置好的logger

    Args:
        name: logger名称，通常使用 __name__
        level: 日志级别，默认使用配置文件中的值
        log_format: 日志格式，默认使用配置文件中的值
        use_colors: 是否使用彩色输出（仅对终端有效）
        log_file: 可选的日志文件路径

    Returns:
        配置好的logger对象
    """
    # 创建logger
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 设置日志级别
    log_level = getattr(logging, (level or LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(log_level)

    # 创建格式化器
    fmt = log_format or LOG_FORMAT
    formatter: logging.Formatter
    if use_colors and sys.stdout.isatty():
        formatter = ColoredFormatter(fmt)
    else:
        formatter = logging.Formatter(fmt)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定）
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        # 文件中不使用颜色
        file_handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(file_handler)

    # 防止日志传播到根logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取logger的便捷函数

    Args:
        name: logger名称，通常使用 __name__

    Returns:
        logger对象
    """
    return setup_logger(name)


# 预定义的几个logger
def get_main_logger() -> logging.Logger:
    """获取主程序logger"""
    return get_logger("PDFDownloader")


def get_fetcher_logger() -> logging.Logger:
    """获取文献获取器logger"""
    return get_logger("PaperFetcher")


def get_manager_logger() -> logging.Logger:
    """获取下载管理器logger"""
    return get_logger("DownloadManager")


def get_counter_logger() -> logging.Logger:
    """获取计数器logger"""
    return get_logger("PMCIDCounter")


# 日志装饰器
def log_function_call(logger: logging.Logger | None = None) -> Callable:
    """
    装饰器：记录函数调用

    Args:
        logger: 可选的logger对象，如果为None则使用函数所在模块的logger
    """

    def decorator(func: Callable) -> Callable:
        import functools

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            logger.debug(f"调用函数 {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"函数 {func.__name__} 执行成功")
                return result
            except Exception as e:
                logger.error(f"函数 {func.__name__} 执行失败: {e}", exc_info=True)
                raise

        return wrapper

    return decorator


# 日志上下文管理器
class LogContext:
    """
    上下文管理器：用于临时更改日志级别
    """

    def __init__(self, logger: logging.Logger, level: str):
        self.logger = logger
        self.new_level = getattr(logging, level.upper())
        self.old_level: int | None = None

    def __enter__(self) -> "LogContext":
        self.old_level = self.logger.level
        self.logger.setLevel(self.new_level)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.old_level is not None:
            self.logger.setLevel(self.old_level)
