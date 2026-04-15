"""错误处理模块"""

from enum import Enum
from typing import Dict, Any


class ErrorCode(Enum):
    """错误码枚举"""
    # 通用错误
    UNKNOWN_ERROR = 1000
    NETWORK_ERROR = 1001
    TIMEOUT_ERROR = 1002
    
    # API 错误
    API_RATE_LIMIT = 2001
    API_AUTH_ERROR = 2002
    API_INVALID_RESPONSE = 2003
    
    # 输入错误
    INVALID_INPUT = 3001
    INVALID_IDENTIFIER = 3002
    FILE_NOT_FOUND = 3003
    
    # 下载错误
    DOWNLOAD_FAILED = 4001
    PDF_NOT_AVAILABLE = 4002
    STORAGE_ERROR = 4003


class PDFGetError(Exception):
    """PDFGet 基础错误类"""
    
    def __init__(self, error_code: ErrorCode, message: str, details: Dict[str, Any] = None):
        """
        初始化错误
        
        Args:
            error_code: 错误码
            message: 错误消息
            details: 错误详情
        """
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{error_code.value}] {message}")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": self.details
            }
        }


class NetworkError(PDFGetError):
    """网络错误"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(ErrorCode.NETWORK_ERROR, message, details)


class TimeoutError(PDFGetError):
    """超时错误"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(ErrorCode.TIMEOUT_ERROR, message, details)


class InvalidInputError(PDFGetError):
    """无效输入错误"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(ErrorCode.INVALID_INPUT, message, details)


class DownloadError(PDFGetError):
    """下载错误"""
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(ErrorCode.DOWNLOAD_FAILED, message, details)