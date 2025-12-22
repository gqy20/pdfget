"""
异常处理装饰器

提供统一的NCBI API请求异常处理。
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

import requests


def handle_ncbi_errors(
    default_return: Any = None,
    error_message: str = "",
    logger: logging.Logger | None = None,
) -> Callable:
    """
    NCBI API异常处理装饰器

    Args:
        default_return: 异常时的默认返回值
        error_message: 自定义错误消息前缀
        logger: 日志器实例，如果为None则尝试从被装饰对象的self.logger获取

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # 获取日志器
            func_logger = logger
            if func_logger is None and args and hasattr(args[0], "logger"):
                func_logger = args[0].logger
            elif func_logger is None:
                # 如果没有提供日志器，使用模块级日志器
                func_logger = logging.getLogger(func.__module__)

            try:
                return func(*args, **kwargs)
            except requests.exceptions.Timeout:
                msg = f"{error_message}请求超时" if error_message else "请求超时"
                func_logger.error(msg)
                return default_return
            except requests.exceptions.ConnectionError as e:
                msg = (
                    f"{error_message}连接失败: {str(e)}"
                    if error_message
                    else f"连接失败: {str(e)}"
                )
                func_logger.error(msg)
                return default_return
            except requests.exceptions.HTTPError as e:
                msg = (
                    f"{error_message}HTTP错误: {str(e)}"
                    if error_message
                    else f"HTTP错误: {str(e)}"
                )
                func_logger.error(msg)
                return default_return
            except requests.exceptions.RequestException as e:
                msg = (
                    f"{error_message}请求失败: {str(e)}"
                    if error_message
                    else f"请求失败: {str(e)}"
                )
                func_logger.error(msg)
                return default_return
            except Exception as e:
                msg = (
                    f"{error_message}未知错误: {str(e)}"
                    if error_message
                    else f"未知错误: {str(e)}"
                )
                func_logger.error(msg)
                return default_return

        return wrapper

    return decorator
