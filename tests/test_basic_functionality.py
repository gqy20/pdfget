"""
基础功能测试
"""

import pytest
import tempfile
from unittest.mock import Mock, patch

from pdfget.fetcher import PaperFetcher


class TestBasicFunctionality:
    """基础功能测试类"""

    @pytest.fixture
    def fetcher(self):
        """创建获取器实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PaperFetcher(cache_dir=tmpdir)

    def test_initialization(self, fetcher):
        """测试初始化"""
        assert fetcher.cache_dir.exists()
        assert hasattr(fetcher, "session")

    def test_query_parsing(self, fetcher):
        """测试查询解析功能"""
        # 基础查询
        assert fetcher.parse_query("cancer") == "cancer"

        # 短语查询
        assert fetcher.parse_query('"deep learning"') == '"deep learning"'

        # 布尔运算符
        assert "AND" in fetcher.parse_query("cancer AND immunotherapy")

        # 字段查询（转为大写）
        assert "TITLE:" in fetcher.parse_query('title:"neural networks"')
        assert "AUTHOR:" in fetcher.parse_query("author:hinton")

    def test_search_functionality(self, fetcher):
        """测试搜索功能"""
        # 模拟API响应
        mock_response = {
            "resultList": {
                "result": [
                    {
                        "title": "Test Paper",
                        "authorString": "Doe J, Smith J",
                        "journalTitle": "Nature",
                        "pubYear": "2023",
                        "doi": "10.1234/test.doi",
                        "pmcid": "PMC123456",
                        "abstractText": "Test abstract",
                    }
                ]
            },
            "hitCount": 1,
        }

        with patch.object(fetcher.session, "get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_get.return_value = mock_response_obj

            result = fetcher.search_papers("test", limit=10)

            assert len(result) == 1
            assert result[0]["title"] == "Test Paper"
            assert result[0]["doi"] == "10.1234/test.doi"

    def test_cache_operations(self, fetcher):
        """测试缓存操作"""
        doi = "10.1234/test.doi"
        data = {"success": True, "title": "Test Paper"}

        # 测试保存和获取缓存
        fetcher._save_cache(doi, data)
        cached_data = fetcher._get_cache(doi)

        assert cached_data is not None
        assert cached_data["title"] == "Test Paper"

        # 测试不存在的缓存
        nonexistent = fetcher._get_cache("10.1234/nonexistent.doi")
        assert nonexistent is None

    def test_batch_fetch(self, fetcher):
        """测试批量获取"""
        dois = ["10.1234/test1.doi", "10.1234/test2.doi"]
        mock_data = {"success": True, "title": "Test Paper"}

        with patch.object(fetcher, "_get_cache", return_value=None):
            with patch.object(fetcher, "_save_cache"):
                with patch.object(fetcher, "_fetch_from_pmc", return_value=mock_data):
                    results = fetcher.fetch_batch(dois, delay=0)

                    assert len(results) == 2
                    assert all(result["success"] for result in results)
