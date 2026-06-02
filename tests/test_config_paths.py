"""
配置路径测试 - 验证缓存目录遵循 XDG 惯例
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

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
            PaperFetcher(output_dir=str(out))
            assert out.exists()

    def test_fetcher_cache_info_uses_cache_manager_files(self):
        """PaperFetcher 缓存统计应匹配 CacheManager 实际文件命名"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            fetcher.cache_manager.set("search:pubmed:test query", [{"pmid": "1"}])

            info = fetcher.get_cache_info()

            assert info["search_cache_count"] == 1
            assert info["search_cache_size_bytes"] > 0
            assert info["search_cache_dir"] == str(fetcher.cache_dir)

    def test_fetcher_clear_cache_uses_cache_manager(self):
        """PaperFetcher 清理搜索缓存应删除 CacheManager 实际缓存文件"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            fetcher.cache_manager.set("search:pubmed:test query", [{"pmid": "1"}])

            fetcher.clear_cache(search_cache=True, pdf_cache=False)

            assert fetcher.cache_manager.get_cache_info()["count"] == 0

    def test_fetcher_export_results_json(self):
        """PaperFetcher export_results 支持 JSON 兼容输出"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            output_path = fetcher.export_results(
                [{"pmid": "1", "title": "Test"}],
                format_type="json",
                filename="papers.json",
            )

            assert json.loads(Path(output_path).read_text(encoding="utf-8")) == [
                {"pmid": "1", "title": "Test"}
            ]

    def test_fetcher_export_results_rejects_legacy_format_keyword(self):
        """PaperFetcher export_results 不再接受旧 format= 关键字"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            legacy_kwargs = {"format": "csv"}
            try:
                fetcher.export_results(
                    [{"pmid": "1", "title": "Test"}],
                    **legacy_kwargs,
                    filename="papers.csv",
                )
            except TypeError as exc:
                assert "unexpected keyword argument" in str(exc)
            else:
                raise AssertionError("Expected TypeError")

    def test_fetcher_export_results_rejects_unknown_format(self):
        """PaperFetcher export_results 对未知格式报错"""
        from pdfget.fetcher import PaperFetcher

        with tempfile.TemporaryDirectory() as tmp:
            fetcher = PaperFetcher(cache_dir=tmp)
            try:
                fetcher.export_results([], format_type="xml")
            except ValueError as exc:
                assert "不支持的格式" in str(exc)
            else:
                raise AssertionError("Expected ValueError")


class TestConfigNoSideEffectsOnImport:
    """验证 config 导入时不产生文件系统副作用"""

    def test_get_cache_dir_is_callable(self):
        """get_cache_dir 应是函数，不会在 import 时执行 mkdir"""
        assert callable(get_cache_dir)

    def test_import_config_no_data_dir_created(self):
        """导入 config 不应在项目根目录创建 data/ 文件夹"""
        # 验证 DATA_DIR 常量已不存在（已移除死代码）
        import pdfget.config

        assert not hasattr(pdfget.config, "DATA_DIR")
        assert not hasattr(pdfget.config, "OUTPUT_DIR")


class TestSafeFilename:
    """统一文件名生成函数测试 — 验证所有路径行为一致"""

    def setup_method(self):
        from pdfget.filename import make_pdf_filename

        self.fn = make_pdf_filename

    def test_with_standard_doi(self):
        """标准 DOI → PMCID_doi.pdf"""
        result = self.fn("PMC123456", "10.1186/s12916-020-01690-4")
        assert result == "PMC123456_101186s12916020016904.pdf"

    def test_with_empty_doi_returns_pmcid_only(self):
        """空 DOI → PMC123.pdf（不是 unknown）"""
        result = self.fn("PMC123", "")
        assert result == "PMC123.pdf"
        assert "unknown" not in result

    def test_with_none_doi_returns_pmcid_only(self):
        """None DOI → PMC123.pdf"""
        result = self.fn("PMC123", None)
        assert result == "PMC123.pdf"
        assert "unknown" not in result

    def test_strips_pdf_suffix(self):
        """DOI 带 .pdf 后缀时自动去除"""
        result = self.fn("PMC123", "10.1000/test.pdf")
        assert result == "PMC123_101000test.pdf"
        assert ".pdf.pdf" not in result

    def test_strips_special_chars(self):
        """DOI 中的特殊字符全部移除"""
        result = self.fn("PMC123", "10.1038/s41586-024-07146-0?param=value&x=1")
        assert "/" not in result
        assert "-" not in result
        assert "?" not in result
        assert "&" not in result
        assert "=" not in result

    def test_truncates_long_doi(self):
        """超长 DOI 截断到 50 字符"""
        long_doi = "10." + "x" * 60
        result = self.fn("PMC123", long_doi)
        # PMCID_(50 chars).pdf
        base = result.replace(".pdf", "")
        _, doi_part = base.split("_", 1)
        assert len(doi_part) <= 50

    def test_unicode_stripped_cleanly(self):
        """含 Unicode 的 DOI 不崩溃"""
        result = self.fn("PMC123", "10.1000/测试测试")
        assert "PMC123" in result
        assert result.endswith(".pdf")

    def test_spaces_removed(self):
        """DOI 中空格被移除"""
        result = self.fn("PMC123", "10.1000/test name here")
        assert " " not in result
        assert "testnamehere" in result

    def test_doi_only_dots_and_special_chars_keeps_digits(self):
        """DOI 只有数字和点时保留数字部分"""
        result = self.fn("PMC123", "10.!!!/???")
        assert result == "PMC123_10.pdf"  # '10' 是有效字符

    def test_nature_doi_format(self):
        """Nature 格式 DOI"""
        result = self.fn("PMC123", "10.1038/s41586-020-2661-9")
        assert result == "PMC123_101038s4158602026619.pdf"

    def test_cell_doi_format(self):
        """Cell 格式 DOI"""
        result = self.fn("PMC123", "10.1016/j.cell.2020.01.021")
        assert result == "PMC123_101016jcell202001021.pdf"

    def test_consistency_with_downloader_behavior(self):
        """与 downloader.py 原有逻辑行为一致"""
        import re

        def old_downloader_logic(pmcid, doi):
            if doi:
                clean = doi
                if clean.lower().endswith(".pdf"):
                    clean = doi[:-4]
                safe = re.sub(r"[^a-zA-Z0-9]", "", clean)[:50]
                return f"{pmcid}_{safe}.pdf"
            return f"{pmcid}.pdf"

        cases = [
            ("PMC123", "10.1186/s12916-020-01690-4"),
            ("PMC123", ""),
            ("PMC123", None),
            ("PMC123", "10.1000/test.pdf"),
            ("PMC123", "10.!!!/???"),  # → PMC123_10.pdf (digits kept)
            ("PMC123", "10." + "x" * 60),
        ]
        for pmcid, doi in cases:
            expected = old_downloader_logic(pmcid, doi)
            actual = self.fn(pmcid, doi)
            assert actual == expected, f"不一致: doi={doi!r}, expected={expected}, actual={actual}"
