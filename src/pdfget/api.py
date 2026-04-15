"""PDFGet API 接口"""

import time
from typing import List, Dict, Optional, Any
from .fetcher import PaperFetcher
from .manager import UnifiedDownloadManager
from .config import DOWNLOAD_BASE_DELAY


class PDFGetAPI:
    """PDFGet 编程接口"""
    
    def __init__(self, cache_dir: str = "data/cache", output_dir: str = "data/pdfs"):
        """
        初始化 API 实例
        
        Args:
            cache_dir: 缓存目录
            output_dir: 输出目录
        """
        self.fetcher = PaperFetcher(cache_dir=cache_dir, output_dir=output_dir)
    
    def search_papers(self, query: str, limit: int = 50, source: str = "pubmed") -> Dict[str, Any]:
        """
        搜索文献
        
        Args:
            query: 搜索关键词
            limit: 结果数量限制
            source: 数据源
        
        Returns:
            标准化的搜索结果
        """
        start_time = time.time()
        papers = self.fetcher.search_papers(query, limit=limit, source=source)
        return {
            "schema": "search_result.v1",
            "query": query,
            "timestamp": time.time(),
            "total": len(papers),
            "results": papers,
            "metadata": {
                "api_version": "1.0",
                "source": source,
                "limit": limit,
                "processing_time": time.time() - start_time
            }
        }
    
    def download_papers(self, papers: List[Dict], max_workers: int = 3, delay: float = DOWNLOAD_BASE_DELAY) -> Dict[str, Any]:
        """
        下载文献
        
        Args:
            papers: 论文列表
            max_workers: 并发线程数
            delay: 下载延迟
        
        Returns:
            标准化的下载结果
        """
        start_time = time.time()
        download_manager = UnifiedDownloadManager(
            fetcher=self.fetcher,
            max_workers=max_workers,
            base_delay=delay
        )
        results = download_manager.download_batch(papers)
        success_count = sum(1 for r in results if r.get("success"))
        
        return {
            "schema": "download_result.v1",
            "timestamp": time.time(),
            "total": len(results),
            "success": success_count,
            "results": results,
            "metadata": {
                "api_version": "1.0",
                "max_workers": max_workers,
                "delay": delay,
                "processing_time": time.time() - start_time
            }
        }
    
    def download_from_identifiers(self, identifiers: List[str], max_workers: int = 3) -> Dict[str, Any]:
        """
        从标识符列表下载文献
        
        Args:
            identifiers: 标识符列表（PMCID/PMID/DOI/arXiv ID）
            max_workers: 并发线程数
        
        Returns:
            标准化的下载结果
        """
        start_time = time.time()
        # 构建统一输入字符串
        input_value = ",".join(identifiers)
        results = self.fetcher.download_from_unified_input(
            input_value=input_value,
            max_workers=max_workers
        )
        success_count = sum(1 for r in results if r.get("success"))
        
        return {
            "schema": "download_result.v1",
            "timestamp": time.time(),
            "total": len(results),
            "success": success_count,
            "results": results,
            "metadata": {
                "api_version": "1.0",
                "max_workers": max_workers,
                "input_count": len(identifiers),
                "processing_time": time.time() - start_time
            }
        }
    
    def close(self):
        """关闭 API 实例，释放资源"""
        self.fetcher.session.close()
    
    def __enter__(self):
        """支持上下文管理器"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时关闭资源"""
        self.close()