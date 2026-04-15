"""API 集成测试"""

from pdfget import PDFGetAPI


def test_full_workflow():
    """测试完整工作流程"""
    with PDFGetAPI() as api:
        # 1. 搜索文献
        search_result = api.search_papers("machine learning", limit=3, source="pubmed")
        assert search_result["total"] >= 0
        
        # 2. 如果有结果，尝试下载
        if search_result["results"]:
            papers = search_result["results"][:1]
            download_result = api.download_papers(papers, max_workers=1)
            assert download_result["total"] == 1
            assert "success" in download_result


def test_mixed_identifiers():
    """测试混合标识符下载"""
    with PDFGetAPI() as api:
        # 测试不同类型的标识符
        identifiers = ["2301.12345"]  # arXiv ID
        result = api.download_from_identifiers(identifiers)
        assert result["total"] == 1
        assert "success" in result