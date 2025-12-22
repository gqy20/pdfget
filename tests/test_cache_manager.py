#!/usr/bin/env python3
"""缓存管理器测试用例"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from pdfget.utils.cache_manager import CacheManager


class TestCacheManager:
    """缓存管理器测试"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """创建缓存管理器实例"""
        return CacheManager(cache_dir=temp_cache_dir)

    def test_init_with_directory(self, temp_cache_dir):
        """测试使用目录初始化"""
        manager = CacheManager(cache_dir=temp_cache_dir)
        assert manager.cache_dir == temp_cache_dir
        assert manager.cache_dir.exists()

    def test_init_create_directory(self):
        """测试自动创建目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "new_cache"
            assert not cache_dir.exists()

            manager = CacheManager(cache_dir=cache_dir)
            assert cache_dir.exists()
            assert manager.cache_dir == cache_dir

    def test_set_and_get_string_data(self, cache_manager):
        """测试设置和获取字符串数据"""
        key = "test_key"
        data = "test_data"

        # 设置数据
        cache_manager.set(key, data)

        # 获取数据
        result = cache_manager.get(key)
        assert result == data

    def test_set_and_get_dict_data(self, cache_manager):
        """测试设置和获取字典数据"""
        key = "test_dict"
        data = {"name": "test", "value": 123, "items": [1, 2, 3]}

        cache_manager.set(key, data)
        result = cache_manager.get(key)
        assert result == data

    def test_set_and_get_list_data(self, cache_manager):
        """测试设置和获取列表数据"""
        key = "test_list"
        data = [1, 2, "three", {"four": 4}]

        cache_manager.set(key, data)
        result = cache_manager.get(key)
        assert result == data

    def test_get_nonexistent_key(self, cache_manager):
        """测试获取不存在的键"""
        result = cache_manager.get("nonexistent_key")
        assert result is None

    def test_get_nonexistent_key_with_default(self, cache_manager):
        """测试获取不存在的键（带默认值）"""
        result = cache_manager.get("nonexistent_key", default="default_value")
        assert result == "default_value"

    def test_delete_existing_key(self, cache_manager):
        """测试删除存在的键"""
        key = "test_key"
        data = "test_data"

        cache_manager.set(key, data)
        assert cache_manager.get(key) == data

        cache_manager.delete(key)
        assert cache_manager.get(key) is None

    def test_delete_nonexistent_key(self, cache_manager):
        """测试删除不存在的键"""
        # 应该不抛出异常
        cache_manager.delete("nonexistent_key")

    def test_clear_all_cache(self, cache_manager):
        """测试清空所有缓存"""
        # 设置多个键
        cache_manager.set("key1", "data1")
        cache_manager.set("key2", "data2")
        cache_manager.set("key3", "data3")

        # 验证数据存在
        assert cache_manager.get("key1") == "data1"
        assert cache_manager.get("key2") == "data2"
        assert cache_manager.get("key3") == "data3"

        # 清空缓存
        cache_manager.clear()

        # 验证数据已删除
        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") is None
        assert cache_manager.get("key3") is None

    def test_ttl_expiration(self, cache_manager):
        """测试TTL过期"""
        key = "ttl_key"
        data = "ttl_data"

        # 设置很短的TTL
        cache_manager.set(key, data, ttl=0.1)  # 0.1秒
        assert cache_manager.get(key) == data

        # 等待过期
        time.sleep(0.2)
        result = cache_manager.get(key)
        assert result is None

    def test_ttl_no_expiration(self, cache_manager):
        """测试TTL不过期"""
        key = "no_ttl_key"
        data = "no_ttl_data"

        # 设置较长的TTL
        cache_manager.set(key, data, ttl=10)  # 10秒
        assert cache_manager.get(key) == data

        # 短暂等待后应该仍然存在
        time.sleep(0.1)
        result = cache_manager.get(key)
        assert result == data

    def test_exists_existing_key(self, cache_manager):
        """测试检查存在的键"""
        key = "exist_key"
        data = "exist_data"

        assert not cache_manager.exists(key)

        cache_manager.set(key, data)
        assert cache_manager.exists(key)

    def test_exists_nonexistent_key(self, cache_manager):
        """测试检查不存在的键"""
        assert not cache_manager.exists("nonexistent_key")

    def test_file_naming_sanitization(self, cache_manager):
        """测试文件名清理"""
        # 使用包含特殊字符的键
        key = "test/key with spaces & special@chars"
        data = "sanitized_data"

        cache_manager.set(key, data)
        result = cache_manager.get(key)
        assert result == data

    def test_cache_file_format(self, cache_manager):
        """测试缓存文件格式"""
        key = "format_test"
        data = {"test": "data", "number": 42}

        cache_manager.set(key, data)

        # 检查缓存文件是否存在
        cache_file = cache_manager._get_cache_file(key)
        assert cache_file.exists()

        # 检查文件内容是否为有效的JSON
        with open(cache_file, encoding="utf-8") as f:
            content = json.load(f)

        assert content["data"] == data
        assert "timestamp" in content
        assert "ttl" in content

    def test_load_corrupted_cache_file(self, cache_manager):
        """测试加载损坏的缓存文件"""
        key = "corrupted_test"
        cache_file = cache_manager._get_cache_file(key)

        # 创建损坏的JSON文件
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write("invalid json content")

        # 应该返回None而不是抛出异常
        result = cache_manager.get(key)
        assert result is None

    def test_cache_size_info(self, cache_manager):
        """测试缓存大小信息"""
        # 添加一些数据
        cache_manager.set("key1", "x" * 100)  # 100字符
        cache_manager.set("key2", "x" * 200)  # 200字符

        info = cache_manager.get_cache_info()
        assert info["count"] == 2
        assert info["size_bytes"] > 0

    def test_cache_cleanup_expired(self, cache_manager):
        """测试清理过期缓存"""
        # 设置一些数据
        cache_manager.set("valid_key", "valid_data", ttl=10)
        cache_manager.set("expired_key", "expired_data", ttl=0.1)

        # 等待过期
        time.sleep(0.2)

        # 清理过期缓存
        cleaned = cache_manager.cleanup_expired()
        assert cleaned >= 1
        assert cache_manager.exists("valid_key")
        assert not cache_manager.exists("expired_key")

    def test_set_data_with_none_ttl(self, cache_manager):
        """测试设置数据时TTL为None"""
        key = "none_ttl"
        data = "data"

        cache_manager.set(key, data, ttl=None)
        assert cache_manager.get(key) == data

        # 短暂等待后应该仍然存在
        time.sleep(0.1)
        assert cache_manager.get(key) == data
