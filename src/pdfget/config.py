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
MAX_CONCURRENT = 5
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# API设置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PDFGet/1.0)",
    "Accept": "application/pdf,*/*",
}

# 日志设置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"