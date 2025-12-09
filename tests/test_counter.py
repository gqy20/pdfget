"""测试 PMCIDCounter 缓存功能"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.pdfget.config import CACHE_DIR, COUNT_BATCH_SIZE, COUNT_MAX_WORKERS
from src.pdfget.counter import PMCIDCounter


class TestPMCIDCounter:
    """测试 PMCIDCounter 类"""

    def test_init_default_cache_dir(self):
        """测试使用默认缓存目录初始化"""
        counter = PMCIDCounter()
        assert counter.cache_dir == CACHE_DIR
        assert counter.cache_dir.exists()

    def test_init_custom_cache_dir(self):
        """测试使用自定义缓存目录初始化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)
            assert counter.cache_dir == Path(tmpdir)
            assert counter.cache_dir.exists()

    def test_get_cache_file_path(self):
        """测试缓存文件路径生成"""
        counter = PMCIDCounter()

        # 测试不同查询生成不同的文件路径
        file1 = counter._get_cache_file("machine learning", "pubmed")
        file2 = counter._get_cache_file("cancer", "pubmed")
        file3 = counter._get_cache_file("machine learning", "europe_pmc")

        assert file1 != file2  # 不同查询
        assert file1 != file3  # 不同数据源
        assert file1.name.startswith("search_")
        assert file1.suffix == ".json"

    def test_load_cache_no_cache(self):
        """测试没有缓存文件时返回 None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)
            result = counter._load_cache("nonexistent query")
            assert result is None

    def test_load_cache_with_valid_cache(self):
        """测试加载有效的缓存文件"""
        # 创建测试数据
        test_papers = [
            {"pmid": "12345678", "title": "Test Paper 1", "pmcid": "PMC1234567"},
            {"pmid": "87654321", "title": "Test Paper 2", "pmcid": None},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            # 创建缓存文件
            cache_file = counter._get_cache_file("test query", "pubmed")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(test_papers, f)

            # 加载缓存
            result = counter._load_cache("test query")
            assert result == test_papers

    def test_load_cache_with_invalid_cache(self):
        """测试加载无效的缓存文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            # 创建无效的缓存文件
            cache_file = counter._get_cache_file("test query", "pubmed")
            with open(cache_file, "w") as f:
                f.write("invalid json")

            # 应该返回 None 而不是抛出异常
            result = counter._load_cache("test query")
            assert result is None

    def test_statistics_from_cache(self):
        """测试从缓存数据生成统计信息"""
        test_papers = [
            {"pmcid": "PMC1234567"},
            {"pmcid": None},
            {"pmcid": "PMC7654321"},
            {"pmcid": "PMC9999999"},
            {"pmcid": None},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)
            counter._current_query = "test query"

            stats = counter._statistics_from_cache(test_papers)

            assert stats["query"] == "test query"
            assert stats["total"] == 5
            assert stats["checked"] == 5
            assert stats["with_pmcid"] == 3
            assert stats["without_pmcid"] == 2
            assert stats["rate"] == 60.0
            assert stats["elapsed_seconds"] == 0
            assert stats["processing_speed"] == 0.0
            assert stats["from_cache"] is True

    @patch("src.pdfget.fetcher.PaperFetcher")
    def test_count_pmcid_with_cache(self, mock_fetcher_class):
        """测试使用缓存的 PMCID 统计"""
        # 模拟缓存数据
        test_papers = [
            {"pmcid": "PMC1234567"},
            {"pmcid": None},
            {"pmcid": "PMC7654321"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            # 创建缓存文件
            cache_file = counter._get_cache_file("test query", "pubmed")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(test_papers, f)

            # 执行统计
            stats = counter.count_pmcid("test query", use_cache=True)

            # 验证结果
            assert stats["query"] == "test query"
            assert stats["with_pmcid"] == 2
            assert stats["without_pmcid"] == 1
            assert abs(stats["rate"] - 66.66666666666667) < 0.0001
            assert stats["from_cache"] is True

            # 验证没有调用 PaperFetcher
            mock_fetcher_class.assert_not_called()

    @patch("src.pdfget.fetcher.PaperFetcher")
    def test_count_pmcid_without_cache_trigger_search(self, mock_fetcher_class):
        """测试没有缓存时触发搜索"""
        # 模拟 PaperFetcher
        mock_fetcher = MagicMock()
        mock_fetcher.search_papers.return_value = [
            {"pmcid": "PMC1234567"},
            {"pmcid": None},
        ]
        mock_fetcher_class.return_value = mock_fetcher

        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            # 执行统计（无缓存，触发搜索）
            stats = counter.count_pmcid(
                "test query", use_cache=True, trigger_search=True
            )

            # 验证调用了搜索
            mock_fetcher.search_papers.assert_called_once_with(
                "test query", limit=5000, fetch_pmcid=True
            )

            # 验证结果
            assert stats["with_pmcid"] == 1
            assert stats["without_pmcid"] == 1

    def test_count_pmcid_without_cache_no_trigger(self):
        """测试没有缓存且不触发搜索"""
        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            with patch.object(counter, "_count_without_cache") as mock_count_without:
                mock_count_without.return_value = {"test": "result"}

                # 执行统计（无缓存，不触发搜索）
                stats = counter.count_pmcid(
                    "test query", use_cache=False, trigger_search=False
                )

                # 验证调用了无缓存统计方法
                mock_count_without.assert_called_once_with("test query", 5000)
                assert stats == {"test": "result"}

    def test_batch_config_from_config_file(self):
        """测试使用配置文件中的批处理设置"""
        # 这些值应该从 config.py 导入
        expected_batch_size = COUNT_BATCH_SIZE
        expected_max_workers = COUNT_MAX_WORKERS

        # 通过访问 _count_without_cache 方法来验证配置被正确使用
        # 这里我们只需要确认导入的值是正确的
        assert expected_batch_size == 80
        assert expected_max_workers == 5

    def test_load_cache_tries_multiple_sources(self):
        """测试尝试从多个数据源加载缓存"""
        test_papers = [{"pmid": "123", "pmcid": "PMC123"}]

        with tempfile.TemporaryDirectory() as tmpdir:
            counter = PMCIDCounter(cache_dir=tmpdir)

            # 只创建 europe_pmc 的缓存
            cache_file = counter._get_cache_file("test query", "europe_pmc")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(test_papers, f)

            # 应该能从 europe_pmc 加载
            result = counter._load_cache("test query")
            assert result == test_papers
