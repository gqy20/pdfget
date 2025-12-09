"""测试固定梯度重试机制"""

from unittest.mock import Mock, patch

import pytest
import requests

from src.pdfget.retry import retry_with_backoff


class TestFixedGradientBackoff:
    """测试固定梯度重试算法"""

    def test_basic_retry_success_on_second_attempt(self):
        """测试：第二次尝试成功"""
        mock_func = Mock(side_effect=[requests.HTTPError("First fail"), "success"])

        # 使用新的API（只有 max_retries 参数）
        decorated_func = retry_with_backoff(max_retries=2)(mock_func)
        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_fixed_gradient_timing(self):
        """测试：使用固定的5个时间梯度"""
        from src.pdfget.retry import _get_wait_time

        # 测试前5次重试的等待时间
        expected_times = [5, 15, 30, 45, 60]
        actual_times = []

        for retry in range(5):
            # 运行多次以获取平均等待时间
            times = []
            for _ in range(10):
                wait_time = _get_wait_time(retry)
                times.append(wait_time)
            avg_time = sum(times) / len(times)
            actual_times.append(avg_time)

        # 验证等待时间在期望值附近（±10%抖动）
        for i, (actual, expected) in enumerate(
            zip(actual_times, expected_times, strict=True)
        ):
            assert (
                expected * 0.9 <= actual <= expected * 1.1
            ), f"第{i + 1}次重试等待时间错误: {actual} vs {expected}"

    def test_max_retries_exceeded(self):
        """测试：超过最大重试次数后抛出异常"""
        mock_func = Mock(side_effect=requests.HTTPError("Always fails"))

        decorated_func = retry_with_backoff(max_retries=2)(mock_func)

        with pytest.raises(requests.HTTPError):
            decorated_func()

        assert mock_func.call_count == 3  # 初始 + 2次重试

    def test_retry_only_on_designated_status(self):
        """测试：只对指定的HTTP状态码重试"""
        # 创建带有特定状态码的HTTPError
        response_429 = Mock()
        response_429.status_code = 429
        error_429 = requests.HTTPError("Too Many Requests")
        error_429.response = response_429

        response_404 = Mock()
        response_404.status_code = 404
        error_404 = requests.HTTPError("Not Found")
        error_404.response = response_404

        mock_func = Mock(side_effect=[error_429, "success"])

        # 应该重试429错误
        decorated_func = retry_with_backoff(max_retries=2)(mock_func)
        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

        # 不应该重试404错误
        mock_func.reset_mock()
        mock_func.side_effect = error_404

        with pytest.raises(requests.HTTPError):
            decorated_func()

        assert mock_func.call_count == 1  # 没有重试

    def test_jitter_added_to_delay(self):
        """测试：等待时间包含±10%的随机抖动"""
        from src.pdfget.retry import _get_wait_time

        retry_num = 1  # 第二次尝试，基础等待时间15秒
        wait_times = []

        # 运行足够多次以观察抖动效果
        for _ in range(100):
            wait_time = _get_wait_time(retry_num)
            wait_times.append(wait_time)

        # 验证有抖动（不是所有等待时间都相同）
        assert len(set(wait_times)) > 10, "等待时间应该有抖动"

        # 验证抖动范围在±10%以内
        expected = 15
        min_allowed = expected * 0.9
        max_allowed = expected * 1.1

        assert all(
            min_allowed <= wt <= max_allowed for wt in wait_times
        ), f"等待时间抖动超出±10%范围: min={min(wait_times)}, max={max(wait_times)}"

    def test_different_exception_types(self):
        """测试：不同类型的异常处理"""
        # 超时异常应该重试
        mock_func = Mock(side_effect=[requests.Timeout("Timeout"), "success"])
        decorated_func = retry_with_backoff(max_retries=2)(mock_func)
        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

        # 连接错误应该重试
        mock_func.reset_mock()
        mock_func.side_effect = [
            requests.ConnectionError("Connection failed"),
            "success",
        ]
        decorated_func = retry_with_backoff(max_retries=2)(mock_func)
        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_wait_time_beyond_five_retries(self):
        """测试：超过5次重试后使用最大等待时间"""
        from src.pdfget.retry import _get_wait_time

        # 测试第5次及之后的重试
        wait_time_5 = _get_wait_time(4)  # 第5次重试
        wait_time_6 = _get_wait_time(5)  # 第6次重试
        wait_time_10 = _get_wait_time(9)  # 第10次重试

        # 都应该使用60秒作为基础等待时间（±10%抖动）
        assert 54 <= wait_time_5 <= 66  # 60 ± 10%
        assert 54 <= wait_time_6 <= 66
        assert 54 <= wait_time_10 <= 66

    def test_logging_during_retry(self):
        """测试：重试过程中记录日志"""
        with patch("src.pdfget.retry.get_logger") as mock_logger:
            mock_log = Mock()
            mock_logger.return_value = mock_log

            mock_func = Mock(side_effect=[requests.HTTPError("Fail"), "success"])
            decorated_func = retry_with_backoff(max_retries=2)(mock_func)

            with patch("time.sleep"):  # 跳过实际等待
                decorated_func()

            # 验证记录了警告日志
            assert mock_log.warning.called
            warning_call = mock_log.warning.call_args
            assert "请求失败" in warning_call[0][0]
            assert "第 1/2 次重试" in warning_call[0][0]


class TestBackoffIntegration:
    """测试重试机制的集成"""

    @patch("time.sleep")
    def test_with_real_http_request(self, mock_sleep):
        """测试：与真实HTTP请求的集成"""
        mock_response = Mock()
        mock_response.status_code = 429

        def raise_429_then_success():
            if mock_response.raise_for_status.call_count == 1:
                error = requests.HTTPError("Too Many Requests")
                error.response = mock_response
                raise error
            return "success"

        mock_func = Mock(side_effect=raise_429_then_success)
        mock_response.raise_for_status = Mock(side_effect=lambda: None)

        decorated_func = retry_with_backoff(max_retries=2)(mock_func)
        result = decorated_func()

        assert result == "success"
        assert mock_func.call_count == 2
