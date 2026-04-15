"""测试错误处理"""

from pdfget.error import PDFGetError, ErrorCode, InvalidInputError, NetworkError


def test_error_creation():
    """测试错误创建"""
    error = PDFGetError(ErrorCode.UNKNOWN_ERROR, "Test error", {"detail": "test"})
    assert error.error_code == ErrorCode.UNKNOWN_ERROR
    assert error.message == "Test error"
    assert error.details == {"detail": "test"}
    assert "1000" in str(error)


def test_error_to_dict():
    """测试错误转换为字典"""
    error = PDFGetError(ErrorCode.NETWORK_ERROR, "Network error", {"url": "http://example.com"})
    error_dict = error.to_dict()
    assert error_dict["error"]["code"] == 1001
    assert error_dict["error"]["message"] == "Network error"
    assert error_dict["error"]["details"] == {"url": "http://example.com"}


def test_specific_errors():
    """测试特定错误类"""
    # 测试 InvalidInputError
    input_error = InvalidInputError("Invalid input", {"field": "query"})
    assert input_error.error_code == ErrorCode.INVALID_INPUT
    assert input_error.message == "Invalid input"
    
    # 测试 NetworkError
    network_error = NetworkError("Network error", {"url": "http://example.com"})
    assert network_error.error_code == ErrorCode.NETWORK_ERROR
    assert network_error.message == "Network error"