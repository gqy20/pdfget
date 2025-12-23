"""
NCBI基类模块

提供所有NCBI相关模块的通用基类，统一配置初始化和错误处理。
"""

from typing import Any

import requests

from ..config import RATE_LIMIT, TIMEOUT
from ..logger import get_logger
from ..utils import RateLimiter

# 配置字典类型
ConfigDict = dict[str, Any | dict[str, int]]


class NCBIBaseModule:
    """NCBI模块基类

    提供统一的NCBI API访问配置和通用功能。
    """

    # NCBI API基础URL
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    config: ConfigDict  # 类型注解

    def __init__(
        self,
        session: requests.Session,
        email: str = "",
        api_key: str = "",
    ):
        """
        初始化NCBI基类

        Args:
            session: requests.Session实例
            email: NCBI API邮箱（可选，用于提高请求限制）
            api_key: NCBI API密钥（可选）
        """
        self.logger = get_logger(self.__class__.__module__)
        self.session = session
        self.email = email
        self.api_key = api_key
        self.base_url = self.BASE_URL

        # 使用简单的字典配置
        self.config = {
            "timeouts": {
                "download": TIMEOUT,
                "request": TIMEOUT,
                "xml": 5,
                "fetch": TIMEOUT,
            },
            "rate_limit": RATE_LIMIT,
        }
        self.rate_limiter = RateLimiter(rate_limit=self.config["rate_limit"])

    def _rate_limit(self) -> None:
        """处理NCBI API请求频率限制"""
        self.rate_limiter.wait_for_rate_limit()

    def _build_ncbi_params(self, **kwargs) -> dict[str, Any]:
        """构建NCBI API请求参数

        Args:
            **kwargs: API参数

        Returns:
            包含邮箱和API密钥的参数字典
        """
        params = kwargs.copy()

        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        return params
