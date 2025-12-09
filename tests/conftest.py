"""
pytest配置和共享fixtures
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def temp_output_dir():
    """创建临时输出目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_paper_data():
    """示例论文数据"""
    return {
        "title": "Sample Research Paper",
        "authors": ["John Doe", "Jane Smith", "Bob Johnson"],
        "journal": "Nature Publishing Group",
        "year": "2023",
        "volume": "15",
        "issue": "3",
        "pages": "123-145",
        "doi": "10.1038/sample.2023.123",
        "pmcid": "PMC123456789",
        "pmid": "98765432",
        "abstract": "This is a sample abstract describing the research paper content and findings.",
        "affiliation": "University of Example, Department of Research",
        "keywords": ["research", "science", "innovation"],
        "meshTerms": ["Research", "Science", "Technology"],
        "citedBy": 42,
        "license": "CC BY 4.0",
        "grants": ["Grant12345"],
        "hasData": True,
        "hasSuppl": False,
        "isOpenAccess": True,
    }


@pytest.fixture
def sample_search_results(sample_paper_data):
    """示例搜索结果"""
    return {"query": "machine learning", "total": 1, "results": [sample_paper_data]}


@pytest.fixture
def mock_csv_file(temp_output_dir):
    """创建模拟CSV文件"""
    csv_content = """doi
10.1234/test1.doi
10.1234/test2.doi
10.1234/test3.doi
"""
    csv_path = temp_output_dir / "test_dois.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def mock_txt_file(temp_output_dir):
    """创建模拟TXT文件"""
    txt_content = """10.1234/test1.doi
10.1234/test2.doi
10.1234/test3.doi"""
    txt_path = temp_output_dir / "test_dois.txt"
    txt_path.write_text(txt_content)
    return txt_path


@pytest.fixture
def cache_data(sample_paper_data):
    """缓存数据格式"""
    return {**sample_paper_data, "timestamp": 1234567890, "cache_version": "1.0"}


# 测试标记
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )


# 钩子函数
@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """为所有测试设置环境变量"""
    # 设置测试环境变量
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


@pytest.fixture
def mock_pdf_content():
    """模拟PDF内容"""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n..."


@pytest.fixture
def mock_europe_pmc_response():
    """模拟Europe PMC API响应"""
    return {
        "resultList": {
            "result": [
                {
                    "title": "Sample Paper Title",
                    "authorString": "Doe J, Smith J",
                    "journalTitle": "Nature",
                    "pubYear": "2023",
                    "doi": "10.1038/sample.2023.123",
                    "pmcid": "PMC123456789",
                    "pmid": "98765432",
                    "abstractText": "Sample abstract text.",
                    "affiliation": "University of Example",
                    "keywordList": ["keyword1", "keyword2"],
                    "meshHeadingList": ["mesh1", "mesh2"],
                    "citedByCount": "42",
                    "license": "CC BY 4.0",
                    "grantList": "Grant12345",
                    "isOpenAccess": "Y",
                    "hasData": "Y",
                    "hasSuppl": "N",
                    "journalVolume": "15",
                    "journalIssue": "3",
                    "pageInfo": "123-145",
                }
            ]
        },
        "hitCount": 1,
        "nextCursorMark": "*",
    }
