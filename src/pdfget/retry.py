"""指数退避重试机制"""

import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import requests

from .config import MAX_RETRIES
from .logger import get_logger


def retry_with_backoff(
    max_retries: int | None = None,  # 如果为None，使用配置中的值
    retryable_status_codes: tuple[int, ...] = (429, 502, 503, 504),
    use_config: bool = True,  # 是否使用全局配置
) -> Callable:
    """
    固定梯度重试装饰器

    Args:
        max_retries: 最大重试次数。如果为None且use_config=True，使用配置中的值
        retryable_status_codes: 需要重试的HTTP状态码
        use_config: 是否使用全局配置中的重试次数

    Returns:
        装饰器函数

    Note:
        使用固定的5个等待时间梯度：5s, 15s, 30s, 45s, 60s
        每次重试的等待时间：第1次重试等待5秒，第2次15秒，以此类推
        每次等待时间有±10%的随机抖动
        当use_config=True且max_retries=None时，使用DEFAULT_CONFIG.max_retries
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            # 确定实际的重试次数
            if max_retries is None and use_config:
                actual_max_retries = MAX_RETRIES
            else:
                actual_max_retries = max_retries if max_retries is not None else 4

            for retry in range(actual_max_retries + 1):  # +1 包含初始尝试
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # 检查是否应该重试
                    if retry < actual_max_retries and _should_retry(
                        e, retryable_status_codes
                    ):
                        wait_time = _get_wait_time(retry)

                        # 记录重试信息
                        logger = get_logger(func.__module__)
                        logger.warning(
                            f"请求失败 ({type(e).__name__}: {str(e)[:50]}...)，"
                            f"第 {retry + 1}/{actual_max_retries} 次重试，"
                            f"等待 {wait_time:.2f} 秒..."
                        )

                        time.sleep(wait_time)
                        continue
                    else:
                        # 不重试或达到最大重试次数，抛出异常
                        if retry == actual_max_retries:
                            logger = get_logger(func.__module__)
                            logger.error(
                                f"达到最大重试次数 ({actual_max_retries})，放弃重试"
                            )
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


def _get_wait_time(retry: int) -> float:
    """
    计算等待时间

    使用固定的5个时间梯度：5s, 15s, 30s, 45s, 60s

    Args:
        retry: 重试次数（从0开始）

    Returns:
        计算后的等待时间（包含±10%的随机抖动）
    """
    # 预定义的5个等待时间梯度
    wait_times = [5, 15, 30, 45, 60]

    # 获取对应的等待时间，如果超出范围则使用最大值
    base_wait = wait_times[retry] if retry < len(wait_times) else wait_times[-1]

    # 添加少量随机抖动（±10%）
    jitter_range = base_wait * 0.1
    jitter_value = random.uniform(-jitter_range, jitter_range)

    return float(max(0, base_wait + jitter_value))
