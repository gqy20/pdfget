"""
文献获取器测试
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.core.fetcher import PaperFetcher


class TestPaperFetcher:
    """文献获取器测试类"""

    @pytest.fixture
    def fetcher(self):
        """创建获取器实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PaperFetcher(cache_dir=tmpdir)

    @pytest.fixture
    def mock_crossref_response(self):
        """模拟CrossRef API响应"""
        return {
            'message': {
                'title': ['Test Paper Title'],
                'author': [
                    {'given': 'John', 'family': 'Doe'},
                    {'given': 'Jane', 'family': 'Smith'}
                ],
                'container-title': ['Test Journal'],
                'published': {'date-parts': [[2023, 5, 15]]},
                'abstract': 'This is a test abstract about genomic research.'
            }
        }

    @pytest.fixture
    def mock_pmc_response(self):
        """模拟PMC转换API响应"""
        return {
            'records': [
                {
                    'pmcid': 'PMC123456',
                    'title': 'Test Paper Title',
                    'authors': {
                        'authors': [
                            {'name': 'John Doe'},
                            {'name': 'Jane Smith'}
                        ]
                    },
                    'source': 'Test Journal',
                    'publicationyear': '2023'
                }
            ]
        }

    def test_fetcher_initialization(self, fetcher):
        """测试获取器初始化"""
        assert fetcher.cache_dir.exists()
        assert hasattr(fetcher, 'session')
        assert fetcher.session is not None

    def test_fetch_by_doi_success(self, fetcher, mock_crossref_response):
        """测试成功通过DOI获取文献"""
        with patch.object(fetcher.session, 'get') as mock_get:
            # 模拟成功的CrossRef响应
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_crossref_response
            mock_get.return_value = mock_response

            result = fetcher.fetch_by_doi('10.1234/test.doi')

            assert result['success'] is True
            assert result['title'] == 'Test Paper Title'
            assert len(result['authors']) == 2
            assert result['journal'] == 'Test Journal'
            assert 'crossref_doi' in result['strategies_tried']

    def test_fetch_by_doi_crossref_error(self, fetcher):
        """测试CrossRef API错误"""
        with patch.object(fetcher.session, 'get') as mock_get:
            # 模拟CrossRef错误响应
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = fetcher.fetch_by_doi('10.1234/nonexistent.doi')

            assert result['success'] is False
            assert 'crossref_doi' in result['strategies_tried']
            assert any('CrossRef API error' in error for error in result['errors'])

    def test_fetch_by_doi_cache(self, fetcher):
        """测试缓存功能"""
        doi = '10.1234/cache.test.doi'
        cache_key = f"paper_{hashlib.md5(doi.encode()).hexdigest()}.json"
        cache_file = fetcher.cache_dir / cache_key

        # 创建缓存文件
        cached_data = {
            'doi': doi,
            'success': True,
            'title': 'Cached Paper Title',
            'fetch_timestamp': 1234567890
        }
        cache_file.write_text(json.dumps(cached_data))

        result = fetcher.fetch_by_doi(doi)

        assert result['success'] is True
        assert result['title'] == 'Cached Paper Title'
        assert result['doi'] == doi

    def test_try_crossref_doi(self, fetcher, mock_crossref_response):
        """测试CrossRef DOI策略"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_crossref_response
            mock_get.return_value = mock_response

            result = fetcher._try_crossref_doi('10.1234/test.doi')

            assert result['success'] is True
            assert result['title'] == 'Test Paper Title'
            assert len(result['authors']) == 2

    def test_try_crossref_doi_invalid_response(self, fetcher):
        """测试无效的CrossRef响应"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'invalid': 'response'}
            mock_get.return_value = mock_response

            result = fetcher._try_crossref_doi('10.1234/test.doi')

            assert result['success'] is False
            assert 'Invalid CrossRef response' in result['error']

    def test_try_pmc_fulltext_success(self, fetcher, mock_pmc_response):
        """测试PMC全文获取成功"""
        with patch.object(fetcher.session, 'get') as mock_get:
            # 模拟PMC转换API响应
            pmc_response = Mock()
            pmc_response.status_code = 200
            pmc_response.json.return_value = mock_pmc_response

            # 模拟PDF下载响应
            pdf_response = Mock()
            pdf_response.status_code = 200
            pdf_response.content = b'fake pdf content'

            mock_get.side_effect = [pmc_response, pdf_response]

            result = fetcher._try_pmc_fulltext('10.1234/test.doi')

            assert result['success'] is True
            assert result['pmc_id'] == 'PMC123456'
            assert result['pdf_path'] is not None
            assert Path(result['pdf_path']).exists()

    def test_try_pmc_fulltext_no_pmcid(self, fetcher):
        """测试没有PMC ID的情况"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'records': []}
            mock_get.return_value = mock_response

            result = fetcher._try_pmc_fulltext('10.1234/test.doi')

            assert result['success'] is False
            assert 'No PMC record found' in result['error']

    def test_download_pdf_from_url(self, fetcher):
        """测试PDF下载"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = b'fake pdf content'
            mock_get.return_value = mock_response

            result = fetcher._download_pdf_from_url(
                'https://example.com/paper.pdf',
                '10.1234/test.doi',
                filename_prefix='test'
            )

            assert result['success'] is True
            assert 'pdf_path' in result
            assert result['file_size'] > 0
            assert Path(result['pdf_path']).exists()

    def test_download_pdf_from_url_error(self, fetcher):
        """测试PDF下载错误"""
        with patch.object(fetcher.session, 'get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = fetcher._download_pdf_from_url(
                'https://example.com/nonexistent.pdf',
                '10.1234/test.doi'
            )

            assert result['success'] is False
            assert 'HTTP error' in result['error']

    def test_is_cache_valid(self, fetcher):
        """测试缓存有效性检查"""
        import time

        # 创建过期的缓存文件
        old_cache = fetcher.cache_dir / 'old_cache.json'
        old_data = {
            'timestamp': time.time() - (25 * 3600),  # 25小时前
            'success': True
        }
        old_cache.write_text(json.dumps(old_data))

        assert not fetcher._is_cache_valid(old_cache)

        # 创建有效的缓存文件
        new_cache = fetcher.cache_dir / 'new_cache.json'
        new_data = {
            'timestamp': time.time() - (1 * 3600),  # 1小时前
            'success': True
        }
        new_cache.write_text(json.dumps(new_data))

        assert fetcher._is_cache_valid(new_cache)

    def test_get_cached_paper(self, fetcher):
        """测试获取缓存的论文"""
        doi = '10.1234/cached.doi'
        cache_key = f"paper_{hashlib.md5(doi.encode()).hexdigest()}.json"
        cache_file = fetcher.cache_dir / cache_key

        # 创建缓存文件
        import time
        cached_data = {
            'doi': doi,
            'success': True,
            'title': 'Cached Paper',
            'timestamp': time.time() - (1 * 3600)  # 1小时前
        }
        cache_file.write_text(json.dumps(cached_data))

        result = fetcher._get_cached_paper(doi)

        assert result is not None
        assert result['title'] == 'Cached Paper'
        assert result['doi'] == doi

    def test_get_cached_paper_invalid(self, fetcher):
        """测试获取无效的缓存"""
        doi = '10.1234/invalid.doi'
        cache_key = f"paper_{hashlib.md5(doi.encode()).hexdigest()}.json"
        cache_file = fetcher.cache_dir / cache_key

        # 创建过期的缓存文件
        import time
        old_data = {
            'doi': doi,
            'success': True,
            'timestamp': time.time() - (25 * 3600)  # 25小时前
        }
        cache_file.write_text(json.dumps(old_data))

        result = fetcher._get_cached_paper(doi)

        assert result is None
        assert not cache_file.exists()  # 应该被删除

    def test_save_to_cache(self, fetcher):
        """测试保存到缓存"""
        doi = '10.1234/save.test.doi'
        data = {
            'doi': doi,
            'success': True,
            'title': 'Test Paper to Save'
        }

        fetcher._save_to_cache(doi, data)

        # 检查缓存文件是否创建
        cache_key = f"paper_{hashlib.md5(doi.encode()).hexdigest()}.json"
        cache_file = fetcher.cache_dir / cache_key

        assert cache_file.exists()

        # 检查缓存内容
        cached_data = json.loads(cache_file.read_text())
        assert cached_data['doi'] == doi
        assert cached_data['title'] == 'Test Paper to Save'
        assert 'timestamp' in cached_data