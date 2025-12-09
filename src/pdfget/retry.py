"""指数退避重试机制"""

import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import requests

from .logger import get_logger


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 60.0,
    jitter: float = 0.1,
    retryable_status_codes: tuple[int, ...] = (429, 502, 503, 504),
) -> Callable:
    """
    指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        jitter: 随机抖动范围（秒）
        retryable_status_codes: 需要重试的HTTP状态码

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for retry in range(max_retries + 1):  # +1 包含初始尝试
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否应该重试
                    if retry < max_retries and _should_retry(e, retryable_status_codes):
                        wait_time = _get_wait_time(retry, base_delay, max_delay, jitter)

                        # 记录重试信息
                        logger = get_logger(func.__module__)
                        logger.warning(
                            f"请求失败 ({type(e).__name__}: {str(e)[:50]}...)，"
                            f"第 {retry + 1}/{max_retries} 次重试，"
                            f"等待 {wait_time:.2f} 秒..."
                        )

                        time.sleep(wait_time)
                        continue
                    else:
                        # 不重试或达到最大重试次数，抛出异常
                        if retry == max_retries:
                            logger = get_logger(func.__module__)
                            logger.error(f"达到最大重试次数 ({max_retries})，放弃重试")
                        raise e

            # 理论上不会执行到这里
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def _should_retry(exception: Exception, status_codes: tuple[int, ...]) -> bool:
    """判断是否应该重试"""
    # 只对网络相关异常和指定状态码重试
    if isinstance(exception, requests.HTTPError):
        # 对于HTTPError，如果有response且状态码在列表中，则重试
        if hasattr(exception, "response") and exception.response is not None:
            return exception.response.status_code in status_codes
        # 如果没有response，也尝试重试（可能是其他HTTP相关错误）
        return True

    # 其他网络异常（超时、连接错误等）
    return isinstance(exception, (requests.Timeout, requests.ConnectionError))


def _get_wait_time(
    retry: int, base_delay: float, max_delay: float, jitter: float
) -> float:
    """计算等待时间"""
    # 指数退避：delay = base_delay * (2 ^ retry)
    exponential_delay = base_delay * (2**retry)

    # 应用最大延迟限制
    capped_delay = min(exponential_delay, max_delay)

    # 添加随机抖动
    jitter_value = random.uniform(0, min(jitter, capped_delay * 0.1))

    return float(capped_delay + jitter_value)
