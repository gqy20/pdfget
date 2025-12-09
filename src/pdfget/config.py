"""PDF下载器配置"""

from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "pdfs"
CACHE_DIR = DATA_DIR / ".cache"

# 创建目录
for d in [DATA_DIR, OUTPUT_DIR, CACHE_DIR]:
    d.mkdir(exist_ok=True, parents=True)

# 下载设置
TIMEOUT = 30
MAX_RETRIES = 3
DELAY = 1.0

# API请求设置
RATE_LIMIT = 3  # PubMed API 每秒最多3次请求

# 默认搜索限制
DEFAULT_SEARCH_LIMIT = 200  # 默认搜索/统计的文献数量

# 统计计算设置
AVG_PDF_SIZE_MB = 1.5  # 平均PDF大小(MB)
PUBMED_MAX_RESULTS = 10000  # PubMed单次最多返回10000条

# 并发下载设置
DOWNLOAD_BASE_DELAY = 1.0  # 基础延迟时间(秒)
DOWNLOAD_RANDOM_DELAY = 0.5  # 随机延迟范围(秒)

# API设置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PDFGet/1.0)",
    "Accept": "application/pdf,*/*",
}

# 日志设置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# PMCID统计设置
COUNT_BATCH_SIZE = 80  # 每批处理的PMID数量
COUNT_MAX_WORKERS = 5  # 并行处理的线程数
COUNT_OUTPUT_FORMAT = "console"  # 输出格式: console, json, markdown

# 数据源设置
DEFAULT_SOURCE = "pubmed"  # 默认数据源: europe_pmc, pubmed
SOURCES = ["pubmed", "europe_pmc"]  # 支持的数据源列表，优先使用PubMed
