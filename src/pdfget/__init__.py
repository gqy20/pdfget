"""
PDFGet - 智能文献搜索与批量下载工具
"""

__version__ = "0.1.0"
__author__ = "gqy"
__email__ = "qingyu_ge@foxmail.com"
__description__ = "智能文献搜索与批量下载工具，支持高级检索和并发下载"

from .fetcher import PaperFetcher
from .manager import UnifiedDownloadManager
from .counter import PMCIDCounter
from .formatter import StatsFormatter

__all__ = ["PaperFetcher", "UnifiedDownloadManager", "PMCIDCounter", "StatsFormatter"]
