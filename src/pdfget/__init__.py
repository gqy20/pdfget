"""
PDFGet - 智能文献搜索与批量下载工具
"""

__version__ = "0.1.5"
__author__ = "gqy"
__email__ = "qingyu_ge@foxmail.com"
__description__ = "智能文献搜索与批量下载工具，支持高级检索和并发下载"

from .counter import PMCIDCounter
from .download_service import download_from_unified_input
from .downloader import PDFDownloader
from .fetcher import PaperFetcher
from .input_planner import build_download_plan_from_unified_input
from .logger import configure_logging, get_logger, setup_logger
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher

__all__ = [
    "PaperFetcher",
    "PMCIDRetriever",
    "PDFDownloader",
    "PaperSearcher",
    "PMCIDCounter",
    "build_download_plan_from_unified_input",
    "configure_logging",
    "download_from_unified_input",
    "get_logger",
    "setup_logger",
]
