"""
统一的速率限制工具

提供线程安全的速率限制功能，用于控制API请求频率。
"""

import time


class RateLimiter:
    """速率限制器

    用于控制API请求频率，遵守各种服务的速率限制要求。
    """

    def __init__(self, rate_limit: int = 3, last_request_time: float | None = None):
        """
        初始化速率限制器

        Args:
            rate_limit: 每秒最大请求次数
            last_request_time: 上次请求时间（用于测试）
        """
        self.rate_limit = rate_limit
        self.last_request_time = last_request_time or 0.0

    def wait_for_rate_limit(self) -> None:
        """
        等待直到可以进行下一次请求

        根据速率限制计算需要等待的时间，并执行等待。
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # 计算最小间隔时间
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            # 需要等待
            wait_time = min_interval - time_since_last
            time.sleep(wait_time)

        # 更新最后请求时间
        self.last_request_time = current_time

    def reset(self) -> None:
        """重置速率限制器"""
        self.last_request_time = 0.0

    def get_wait_time(self) -> float:
        """
        获取当前需要等待的时间

        Returns:
            需要等待的秒数，0表示不需要等待
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.rate_limit

        if time_since_last < min_interval:
            return min_interval - time_since_last
        return 0.0
