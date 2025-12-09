"""
PDFGet - 智能文献搜索与批量下载工具
"""

__version__ = "0.1.2"
__author__ = "gqy"
__email__ = "qingyu_ge@foxmail.com"
__description__ = "智能文献搜索与批量下载工具，支持高级检索和并发下载"

from .downloader import PDFDownloader
from .fetcher import PaperFetcher
from .logger import get_logger, setup_logger
from .pmcid import PMCIDRetriever
from .searcher import PaperSearcher

__all__ = [
    "PaperFetcher",
    "PMCIDRetriever",
    "PDFDownloader",
    "PaperSearcher",
    "get_logger",
    "setup_logger",
]
