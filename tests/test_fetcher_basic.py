"""
基础文献获取器测试
"""

import pytest
import tempfile
from unittest.mock import Mock, patch

from pdfget.fetcher import PaperFetcher


class TestPaperFetcherBasic:
    """基础文献获取器测试类"""

    @pytest.fixture
    def fetcher(self):
        """创建获取器实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PaperFetcher(cache_dir=tmpdir)

    def test_fetcher_initialization(self, fetcher):
        """测试获取器初始化"""
        assert fetcher.cache_dir.exists()
        assert hasattr(fetcher, "session")
        assert fetcher.session is not None
        assert hasattr(fetcher, "logger")

    def test_parse_query_simple(self, fetcher):
        """测试简单查询解析"""
        result = fetcher.parse_query("machine learning")
        assert result == "machine learning"

    def test_parse_query_phrase(self, fetcher):
        """测试短语查询解析"""
        result = fetcher.parse_query('"deep learning"')
        assert result == '"deep learning"'

    def test_parse_query_field_title(self, fetcher):
        """测试标题字段查询（转换为大写）"""
        result = fetcher.parse_query('title:"neural networks"')
        assert result == 'TITLE:"neural networks"'

    def test_parse_query_field_author(self, fetcher):
        """测试作者字段查询（转换为大写）"""
        result = fetcher.parse_query("author:hinton")
        assert result == "AUTHOR:hinton"

    def test_search_papers_success(self, fetcher):
        """测试成功搜索论文"""
        mock_response = {
            "resultList": {
                "result": [
                    {
                        "title": "Test Paper",
                        "authorString": "Doe J",
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

            result = fetcher.search_papers("test query", limit=10)

            assert len(result) == 1
            assert result[0]["title"] == "Test Paper"
            assert result[0]["doi"] == "10.1234/test.doi"

    def test_search_papers_empty_result(self, fetcher):
        """测试搜索结果为空"""
        mock_response = {"resultList": {"result": []}, "hitCount": 0}

        with patch.object(fetcher.session, "get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_get.return_value = mock_response_obj

            result = fetcher.search_papers("nonexistent query", limit=10)

            assert len(result) == 0

    def test_search_papers_api_error(self, fetcher):
        """测试API错误"""
        with patch.object(fetcher.session, "get") as mock_get:
            mock_response_obj = Mock()
            mock_response_obj.status_code = 500
            mock_get.return_value = mock_response_obj

            result = fetcher.search_papers("test query", limit=10)

            assert len(result) == 0

    def test_fetch_by_doi_success(self, fetcher):
        """测试成功通过DOI获取论文"""
        mock_data = {
            "success": True,
            "title": "Test Paper",
            "doi": "10.1234/test.doi",
            "authors": ["John Doe"],
            "journal": "Nature",
            "year": "2023",
        }

        with patch.object(fetcher, "_get_cache", return_value=None):
            with patch.object(fetcher, "_save_cache"):
                with patch.object(fetcher, "_fetch_from_pmc", return_value=mock_data):
                    result = fetcher.fetch_by_doi("10.1234/test.doi")

                    assert result["success"] is True
                    assert result["title"] == "Test Paper"

    def test_fetch_by_doi_from_cache(self, fetcher):
        """测试从缓存获取论文"""
        mock_data = {
            "success": True,
            "title": "Cached Paper",
            "doi": "10.1234/test.doi",
        }

        with patch.object(fetcher, "_get_cache", return_value=mock_data):
            result = fetcher.fetch_by_doi("10.1234/test.doi")

            assert result["success"] is True
            assert result["title"] == "Cached Paper"

    def test_get_nonexistent_cache(self, fetcher):
        """测试获取不存在的缓存"""
        result = fetcher._get_cache("10.1234/nonexistent.doi")
        assert result is None

    def test_save_cache(self, fetcher):
        """测试保存缓存"""
        doi = "10.1234/test.doi"
        data = {"success": True, "title": "Test Paper"}

        fetcher._save_cache(doi, data)

        # 验证缓存文件被创建
        cache_files = list(fetcher.cache_dir.glob("cache_*.json"))
        assert len(cache_files) >= 1

        # 验证缓存内容
        cached_data = fetcher._get_cache(doi)
        assert cached_data is not None
        assert cached_data["success"] is True
        assert cached_data["title"] == "Test Paper"

    def test_fetch_batch_success(self, fetcher):
        """测试批量获取论文"""
        dois = ["10.1234/test1.doi", "10.1234/test2.doi"]
        mock_data = {"success": True, "title": "Test Paper", "doi": "10.1234/test.doi"}

        with patch.object(fetcher, "_get_cache", return_value=None):
            with patch.object(fetcher, "_save_cache"):
                with patch.object(fetcher, "_fetch_from_pmc", return_value=mock_data):
                    results = fetcher.fetch_batch(dois, delay=0.1)

                    assert len(results) == 2
                    assert all(result["success"] for result in results)

    def test_fetch_batch_empty(self, fetcher):
        """测试空批量获取"""
        results = fetcher.fetch_batch([])
        assert results == []
