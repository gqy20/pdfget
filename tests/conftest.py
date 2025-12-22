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
    config.addinivalue_line("markers", "doi: marks tests related to DOI functionality")


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


# CSV 和标识符相关 fixtures
@pytest.fixture
def csv_file_with_pmcids(temp_output_dir):
    """创建包含PMCID的CSV文件"""
    csv_content = """PMCID
PMC123456
PMC789012
PMC345678
"""
    csv_path = temp_output_dir / "pmcids.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def csv_file_with_mixed_ids(temp_output_dir):
    """创建包含混合标识符的CSV文件"""
    csv_content = """ID
PMC123456
38238491
10.1038/s41586-024-07146-0
PMC789012
"""
    csv_path = temp_output_dir / "mixed_ids.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def csv_file_with_header(temp_output_dir):
    """创建带标题的CSV文件"""
    csv_path = temp_output_dir / "papers.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write(
            """PMCID,Title,Author
PMC123456,Test Paper 1,Author A
PMC789012,Test Paper 2,Author B
"""
        )
    return csv_path


# DOI 相关 fixtures
@pytest.fixture
def sample_dois():
    """示例DOI列表"""
    return [
        "10.1186/s12916-020-01690-4",
        "10.1016/j.cell.2020.01.021",
        "10.1038/s41586-020-2661-9",
        "10.1000/test.doi",  # 测试用DOI
        "10.1234/invalid",  # 可能不存在的DOI
    ]


@pytest.fixture
def doi_pmcid_mapping():
    """DOI到PMCID的映射（用于测试）"""
    return {
        "10.1186/s12916-020-01690-4": "PMC7439635",
        "10.1016/j.cell.2020.01.021": "PMC7180979",
        "10.1038/s41586-020-2661-9": "PMC7439636",
        "10.1000/test.doi": "PMC123456789",
        "10.1234/invalid": None,  # 不存在
    }


@pytest.fixture
def mock_doi_converter_response():
    """模拟DOI转换器响应"""
    return {
        "resultList": {
            "result": [
                {
                    "pmcid": "PMC123456789",
                    "doi": "10.1000/test.doi",
                    "title": "Test Paper Title",
                    "authorString": "Test Author",
                    "journalTitle": "Test Journal",
                    "pubYear": "2023",
                    "abstractText": "Test abstract",
                }
            ]
        }
    }


@pytest.fixture
def csv_file_with_dois(temp_output_dir):
    """创建包含DOI的CSV文件"""
    csv_content = """DOI,Title,Journal
10.1186/s12916-020-01690-4,Paper 1,Journal 1
10.1016/j.cell.2020.01.021,Paper 2,Journal 2
10.1038/s41586-020-2661-9,Paper 3,Journal 3
"""
    csv_path = temp_output_dir / "dois.csv"
    csv_path.write_text(csv_content)
    return csv_path


@pytest.fixture
def csv_file_with_mixed_identifiers(temp_output_dir):
    """创建包含混合标识符的CSV文件"""
    csv_content = """ID,Title,Type
PMC123456,Paper 1,PMCID
38238491,Paper 2,PMID
10.1186/s12916-020-01690-4,Paper 3,DOI
PMC789012,Paper 4,PMCID
10.1016/j.cell.2020.01.021,Paper 5,DOI
"""
    csv_path = temp_output_dir / "mixed_identifiers.csv"
    csv_path.write_text(csv_content)
    return csv_path


# 辅助函数和类
class CSVTestMixin:
    """CSV测试混入类，提供通用的CSV测试方法"""

    def assert_csv_content(self, csv_path, expected_content):
        """验证CSV文件内容"""
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
        assert content.strip() == expected_content.strip()

    def create_temp_csv(self, temp_dir, filename, content):
        """创建临时CSV文件"""
        csv_path = temp_dir / filename
        csv_path.write_text(content)
        return csv_path


# XML 测试数据 fixtures
@pytest.fixture
def simple_abstract_xml():
    """简单的摘要XML"""
    return """<article>
        <abstract>
            <p>This is a test abstract.</p>
        </abstract>
    </article>"""


@pytest.fixture
def complex_abstract_xml():
    """复杂的摘要XML（嵌套结构）"""
    return """<article>
        <front>
            <article-meta>
                <abstract>
                    <sec>
                        <title>Background</title>
                        <p>Background paragraph.</p>
                    </sec>
                    <sec>
                        <title>Methods</title>
                        <p>Methods paragraph with <bold>bold text</bold>.</p>
                    </sec>
                </abstract>
            </article-meta>
        </front>
    </article>"""


@pytest.fixture
def xml_without_abstract():
    """无摘要的XML"""
    return """<article>
        <front>
            <article-meta>
                <title>Test Title</title>
            </article-meta>
        </front>
    </article>"""


# 通用工具函数
def create_temp_csv_file(data, temp_dir, filename="test.csv"):
    """创建临时CSV文件的工具函数"""
    import csv

    csv_path = temp_dir / filename
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(data)
    return csv_path
