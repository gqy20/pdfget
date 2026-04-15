"""测试 API 功能"""

from pdfget import PDFGetAPI


def test_api_initialization():
    """测试 API 初始化"""
    api = PDFGetAPI()
    assert api is not None
    api.close()


def test_api_search_papers():
    """测试搜索功能"""
    api = PDFGetAPI()
    try:
        result = api.search_papers("machine learning", limit=2, source="pubmed")
        assert result is not None
        assert result["schema"] == "search_result.v1"
        assert "query" in result
        assert "timestamp" in result
        assert "total" in result
        assert "results" in result
        assert "metadata" in result
        assert result["metadata"]["api_version"] == "1.0"
        assert result["metadata"]["source"] == "pubmed"
        assert result["metadata"]["limit"] == 2
    finally:
        api.close()


def test_api_download_from_identifiers():
    """测试从标识符下载"""
    api = PDFGetAPI()
    try:
        # 使用有效的 arXiv ID 进行测试
        identifiers = ["2301.12345"]
        result = api.download_from_identifiers(identifiers)
        assert result is not None
        assert result["schema"] == "download_result.v1"
        assert "timestamp" in result
        assert "total" in result
        assert "success" in result
        assert "results" in result
        assert "metadata" in result
        assert result["metadata"]["api_version"] == "1.0"
        assert result["metadata"]["input_count"] == 1
    finally:
        api.close()


def test_api_context_manager():
    """测试上下文管理器"""
    with PDFGetAPI() as api:
        result = api.search_papers("test", limit=1)
        assert result is not None
        assert result["schema"] == "search_result.v1"