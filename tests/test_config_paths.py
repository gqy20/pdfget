"""
配置路径测试 - 验证缓存目录遵循 XDG 惯例
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pdfget.config import DEFAULT_OUTPUT_DIR, get_cache_dir


class TestCacheDir:
    """缓存目录路径测试"""

    def test_get_cache_dir_returns_path(self):
        """get_cache_dir 应返回 Path 对象"""
        result = get_cache_dir()
        assert isinstance(result, Path)

    def test_get_cache_dir_default_location(self):
        """默认缓存目录应在 ~/.cache/pdfget"""
        with patch.object(Path, "home", return_value=Path("/fake/home")):
            result = get_cache_dir()
        # 不实际依赖用户主目录，只验证拼接逻辑
        assert result == Path("/fake/home") / ".cache" / "pdfget"

    def test_get_cache_dir_respects_env_override(self):
        """支持通过环境变量 PDFGET_CACHE_DIR 覆盖缓存目录"""
        with tempfile.TemporaryDirectory() as tmp:
            import os

            old = os.environ.get("PDFGET_CACHE_DIR")
            try:
                os.environ["PDFGET_CACHE_DIR"] = tmp
                # 重新导入以获取新值
                import importlib

                import pdfget.config

                importlib.reload(pdfget.config)
                result = pdfget.config.get_cache_dir()
                assert result == Path(tmp)
            finally:
                if old is None:
                    os.environ.pop("PDFGET_CACHE_DIR", None)
                else:
                    os.environ["PDFGET_CACHE_DIR"] = old
                importlib.reload(pdfget.config)

    def test_default_output_dir_is_relative(self):
        """默认输出目录应是相对路径（CWD 下的 pdfs/）"""
        assert DEFAULT_OUTPUT_DIR == "pdfs"
        assert not Path(DEFAULT_OUTPUT_DIR).is_absolute()


class TestPaperFetcherDefaultPaths:
    """PaperFetcher 默认路径测试"""

    def test_fetcher_uses_config_cache_dir_by_default(self):
        """PaperFetcher 默认使用 config.get_cache_dir() 作为缓存目录"""
        from pdfget.fetcher import PaperFetcher

        fetcher = PaperFetcher()
        assert fetcher.cache_dir == get_cache_dir()

    def test_fetcher_accepts_custom_cache_dir(self):
        """PaperFetcher 支持自定义缓存目录覆盖"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            assert fetcher.cache_dir == Path(tmp)

    def test_fetcher_default_output_dir_is_pdfs(self):
        """PaperFetcher 默认输出目录为 'pdfs'（相对路径）"""
        from pdfget.fetcher import PaperFetcher

        fetcher = PaperFetcher()
        assert fetcher.output_dir == Path("pdfs")

    def test_fetcher_output_dir_created_on_init(self):
        """PaperFetcher 初始化时自动创建输出目录"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "custom_out"
            fetcher = PaperFetcher(output_dir=str(out))
            assert out.exists()


class TestConfigNoSideEffectsOnImport:
    """验证 config 导入时不产生文件系统副作用"""

    def test_get_cache_dir_is_callable(self):
        """get_cache_dir 应是函数，不会在 import 时执行 mkdir"""
        assert callable(get_cache_dir)

    def test_import_config_no_data_dir_created(self):
        """导入 config 不应在项目根目录创建 data/ 文件夹"""
        root = Path(__file__).resolve().parents[1]
        # 验证 DATA_DIR 常量已不存在（已移除死代码）
        import pdfget.config

        assert not hasattr(pdfget.config, "DATA_DIR")
        assert not hasattr(pdfget.config, "OUTPUT_DIR")
