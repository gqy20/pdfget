"""
缓存管理器

提供统一的缓存操作接口，支持TTL和自动清理。
"""

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from ..logger import get_logger


class CacheManager:
    """缓存管理器

    提供统一的缓存存储、获取、删除和清理功能。
    """

    def __init__(self, cache_dir: str | Path):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.logger = get_logger(__name__)

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file(self, key: str) -> Path:
        """
        获取缓存文件路径

        Args:
            key: 缓存键

        Returns:
            缓存文件路径
        """
        # 清理键名中的特殊字符，生成安全的文件名
        safe_key = re.sub(r"[^\w\-_\.]", "_", str(key))
        # 使用MD5哈希确保文件名唯一且长度合理
        key_hash = hashlib.md5(str(key).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{safe_key}_{key_hash}.json"

    def set(self, key: str, data: Any, ttl: float | None = None) -> None:
        """
        设置缓存数据

        Args:
            key: 缓存键
            data: 要缓存的数据
            ttl: 生存时间（秒），None表示永不过期
        """
        try:
            cache_file = self._get_cache_file(key)

            # 准备缓存数据
            cache_data = {"data": data, "timestamp": time.time(), "ttl": ttl}

            # 写入缓存文件
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"设置缓存失败 [{key}]: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取缓存数据

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存的数据或默认值
        """
        try:
            cache_file = self._get_cache_file(key)

            if not cache_file.exists():
                return default

            # 读取缓存文件
            with open(cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            # 检查是否过期
            if self._is_expired(cache_data):
                # 删除过期缓存
                self.delete(key)
                return default

            return cache_data.get("data", default)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # 缓存文件损坏，删除并返回默认值
            self.logger.warning(f"缓存文件损坏 [{key}]: {str(e)}")
            self.delete(key)
            return default
        except Exception as e:
            self.logger.error(f"获取缓存失败 [{key}]: {str(e)}")
            return default

    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在且未过期

        Args:
            key: 缓存键

        Returns:
            True如果存在且未过期
        """
        try:
            cache_file = self._get_cache_file(key)

            if not cache_file.exists():
                return False

            # 检查是否过期
            with open(cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)

            return not self._is_expired(cache_data)

        except Exception:
            return False

    def delete(self, key: str) -> None:
        """
        删除缓存数据

        Args:
            key: 缓存键
        """
        try:
            cache_file = self._get_cache_file(key)
            if cache_file.exists():
                cache_file.unlink()
        except Exception as e:
            self.logger.error(f"删除缓存失败 [{key}]: {str(e)}")

    def clear(self) -> None:
        """清空所有缓存"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            self.logger.info("已清空所有缓存")
        except Exception as e:
            self.logger.error(f"清空缓存失败: {str(e)}")

    def cleanup_expired(self) -> int:
        """
        清理过期的缓存文件

        Returns:
            清理的文件数量
        """
        cleaned_count = 0
        try:
            current_time = time.time()
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, encoding="utf-8") as f:
                        cache_data = json.load(f)

                    if self._is_expired(cache_data, current_time):
                        cache_file.unlink()
                        cleaned_count += 1

                except Exception:
                    # 损坏的文件也删除
                    try:
                        cache_file.unlink()
                        cleaned_count += 1
                    except Exception:
                        pass

            if cleaned_count > 0:
                self.logger.info(f"清理了 {cleaned_count} 个过期缓存文件")

        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {str(e)}")

        return cleaned_count

    def get_cache_info(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含缓存统计的字典
        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)

            return {
                "count": len(cache_files),
                "size_bytes": total_size,
                "size_mb": round(total_size / (1024 * 1024), 2),
                "directory": str(self.cache_dir),
            }

        except Exception as e:
            self.logger.error(f"获取缓存信息失败: {str(e)}")
            return {
                "count": 0,
                "size_bytes": 0,
                "size_mb": 0,
                "directory": str(self.cache_dir),
            }

    def _is_expired(
        self, cache_data: dict[str, Any], current_time: float | None = None
    ) -> bool:
        """
        检查缓存数据是否过期

        Args:
            cache_data: 缓存数据字典
            current_time: 当前时间戳

        Returns:
            True如果已过期
        """
        if current_time is None:
            current_time = time.time()

        ttl = cache_data.get("ttl")
        if ttl is None:
            return False  # 永不过期

        timestamp = cache_data.get("timestamp", 0)
        return bool((current_time - timestamp) > ttl)
