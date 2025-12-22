"""
统一的超时配置管理

提供集中化的超时配置，避免在代码中硬编码超时值。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimeoutConfig:
    """
    超时配置类

    集中管理各种网络请求的超时设置，避免硬编码。
    """

    download: int = 30  # 下载超时
    request: int = 30  # 通用请求超时
    xml: int = 5  # XML请求超时
    fetch: int = 30  # 数据获取超时

    def get_timeout(self, timeout_type: str, default: int = 30) -> int:
        """
        获取指定类型的超时值

        Args:
            timeout_type: 超时类型（download/request/xml/fetch）
            default: 默认值

        Returns:
            超时秒数
        """
        return getattr(self, timeout_type, default)

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "TimeoutConfig":
        """
        从字典创建配置对象

        Args:
            config_dict: 配置字典

        Returns:
            TimeoutConfig实例
        """
        # 过滤出有效的配置项
        valid_config = {
            k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__
        }

        return cls(**valid_config)

    def to_dict(self) -> dict[str, int]:
        """
        转换为字典

        Returns:
            配置字典
        """
        return {
            "download": self.download,
            "request": self.request,
            "xml": self.xml,
            "fetch": self.fetch,
        }

    def update(self, **kwargs) -> None:
        """
        更新配置

        Args:
            **kwargs: 要更新的配置项
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass
class NetworkConfig:
    """
    网络配置类

    包含所有网络相关的配置：超时、重试、速率限制等。
    """

    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    max_retries: int = 4
    rate_limit: int = 3

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "NetworkConfig":
        """从字典创建配置对象"""
        # 处理超时配置
        timeouts_config = config_dict.pop("timeouts", {})
        timeouts = TimeoutConfig.from_dict(timeouts_config)

        return cls(timeouts=timeouts, **config_dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "timeouts": self.timeouts.to_dict(),
            "max_retries": self.max_retries,
            "rate_limit": self.rate_limit,
        }


# 默认全局配置
DEFAULT_CONFIG = NetworkConfig()
