#!/usr/bin/env python3
"""
测试 PMCID 模块的功能
"""

from unittest.mock import Mock, patch

import pytest

from src.pdfget.pmcid import PMCIDRetriever


class TestPMCIDRetriever:
    """测试 PMCIDRetriever 类"""

    @pytest.fixture
    def session(self):
        """创建模拟的 session"""
        return Mock()

    @pytest.fixture
    def retriever(self, session):
        """创建 PMCIDRetriever 实例"""
        return PMCIDRetriever(session)

    @pytest.fixture
    def sample_papers(self):
        """示例论文数据"""
        return [
            {
                "pmid": "32353885",
                "doi": "10.1186/s12916-020-01690-4",
                "title": "Paper 1",
            },
            {
                "pmid": "32353886",
                "doi": "10.1186/s12916-020-01690-5",
                "title": "Paper 2",
            },
            {
                "pmid": "32353887",
                "doi": "10.1186/s12916-020-01690-6",
                "title": "Paper 3",
            },
            {"title": "Paper without PMID"},  # 没有 PMID 的论文
            {
                "pmid": "",
                "doi": "10.1186/s12916-020-01690-7",
                "title": "Paper with empty PMID",
            },
            {"pmid": None, "title": "Paper with None PMID"},
            {"pmid": "  32353888  ", "title": "Paper with spaces"},  # 有空格的 PMID
            {"pmid": "32353888", "title": "Duplicate PMID"},  # 重复的 PMID
        ]

    def test_collect_pmids_should_extract_valid_pmids(self, retriever, sample_papers):
        """
        测试: 从论文列表中提取有效的 PMIDs
        """
        pmids = retriever._collect_pmids(sample_papers)

        # 应该只返回非空、数字的、唯一的 PMIDs
        assert pmids == ["32353885", "32353886", "32353887", "32353888"]

    def test_collect_pmids_should_handle_empty_list(self, retriever):
        """
        测试: 空列表应该返回空列表
        """
        pmids = retriever._collect_pmids([])
        assert pmids == []

    def test_collect_pmids_should_handle_list_without_pmids(self, retriever):
        """
        测试: 没有 PMIDs 的论文列表应该返回空列表
        """
        papers = [{"title": "Paper 1"}, {"doi": "10.1000/test"}]
        pmids = retriever._collect_pmids(papers)
        assert pmids == []

    def test_format_pmcid_should_add_prefix(self, retriever):
        """
        测试: 应该为 PMCID 添加 PMC 前缀
        """
        test_cases = [
            ("7439635", "PMC7439635"),
            ("PMC7439635", "PMC7439635"),
            ("", ""),
            (None, ""),
            ("  7439636  ", "PMC7439636"),
        ]

        for input_val, expected in test_cases:
            result = retriever._format_pmcid(input_val)
            assert result == expected

    @patch("time.sleep")  # 跳过实际的等待
    def test_fetch_pmcid_batch_success(self, mock_sleep, retriever):
        """
        测试: 成功批量获取 PMCID
        """
        # 模拟 NCBI ESummary API 响应
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885", "32353886"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                "32353886": {"articleids": [{"idtype": "pmc", "value": "7439636"}]},
            }
        }

        # Mock retriever 的 session
        retriever.session.get = Mock(return_value=mock_response)

        pmids = ["32353885", "32353886"]
        result = retriever._fetch_pmcid_batch(pmids)

        # 断言
        assert result == {"32353885": "PMC7439635", "32353886": "PMC7439636"}

        # 验证 API 调用
        retriever.session.get.assert_called_once()
        call_args = retriever.session.get.call_args
        assert "esummary.fcgi" in call_args[0][0]
        assert call_args[1]["params"]["id"] == "32353885,32353886"
        assert call_args[1]["params"]["db"] == "pubmed"
        assert call_args[1]["params"]["retmode"] == "json"

    @patch("time.sleep")
    def test_fetch_pmcid_batch_partial_success(self, mock_sleep, retriever):
        """
        测试: 部分成功的批量获取
        """
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885", "32353886"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                "32353886": {
                    "articleids": [
                        {"idtype": "doi", "value": "10.1186/test"}
                        # 没有 pmc 类型的 articleid
                    ]
                },
            }
        }
        retriever.session.get = Mock(return_value=mock_response)

        pmids = ["32353885", "32353886"]
        result = retriever._fetch_pmcid_batch(pmids)

        # 断言 - 只返回有 PMCID 的
        assert result == {"32353885": "PMC7439635"}
        assert "32353886" not in result

    @patch("time.sleep")
    def test_fetch_pmcid_batch_no_pmcid(self, mock_sleep, retriever):
        """
        测试: 没有 PMCID 的情况
        """
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885"],
                "32353885": {
                    "articleids": [{"idtype": "doi", "value": "10.1186/test"}]
                },
            }
        }

        # 正确地设置 session.get 的 mock
        retriever.session.get = Mock(return_value=mock_response)

        pmids = ["32353885"]
        result = retriever._fetch_pmcid_batch(pmids)

        # 断言 - 返回空字典
        assert result == {}

    @patch("time.sleep")
    def test_fetch_pmcid_batch_api_error(self, mock_sleep, retriever):
        """
        测试: API 错误处理
        """
        # 模拟 API 错误
        retriever.session.get = Mock(side_effect=Exception("API Error"))

        pmids = ["32353885", "32353886"]
        result = retriever._fetch_pmcid_batch(pmids)

        # 断言 - 错误时返回空字典
        assert result == {}

    @patch("time.sleep")
    def test_fetch_pmcid_batch_large_list(self, mock_sleep, retriever):
        """
        测试: 大量 PMIDs 的分批处理
        """
        # 创建 150 个 PMIDs (减少数量以适应新的批次大小50)
        pmids = [str(32353885 + i) for i in range(150)]

        # 模拟响应
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": {"uids": []}}

        # 正确地设置 session.get 的 mock
        retriever.session.get = Mock(return_value=mock_response)

        # 调用方法
        retriever._fetch_pmcid_batch(pmids)

        # 断言 - 应该调用 3 次 (50, 50, 50)
        assert retriever.session.get.call_count == 3

        # 验证第一批的参数
        first_call = retriever.session.get.call_args_list[0]
        assert len(first_call[1]["params"]["id"].split(",")) == 50

    @patch("time.sleep")
    def test_process_papers_integration(self, mock_sleep, retriever, sample_papers):
        """
        测试: 处理论文的完整流程
        """
        # 模拟批量获取结果
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885", "32353886"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                "32353886": {"articleids": [{"idtype": "pmc", "value": "7439636"}]},
            }
        }

        # 正确地设置 session.get 的 mock
        retriever.session.get = Mock(return_value=mock_response)

        # 调用处理方法
        processed = retriever.process_papers(sample_papers)

        # 断言结果
        assert len(processed) == len(sample_papers)
        assert processed[0]["pmcid"] == "PMC7439635"
        assert processed[1]["pmcid"] == "PMC7439636"
        assert "pmcid" not in processed[2]  # 没有获取到 PMCID
        assert "pmcid" not in processed[3]  # 没有 PMID
        assert "pmcid" not in processed[4]  # 空的 PMID
        assert "pmcid" not in processed[5]  # None 的 PMIDs
        assert "pmcid" not in processed[6]  # 重复的 PMIDs
        assert "pmcid" not in processed[7]  # 重复的 PMIDs

    @patch("time.sleep")
    def test_process_papers_batch_retry_mechanism(self, mock_sleep, retriever):
        """
        测试: 批量重试机制
        """
        # 创建测试论文
        papers = [
            {"pmid": "32353885"},
            {"pmid": "32353886"},
            {"pmid": "32353887"},
        ]

        # 第一次批量调用只返回部分结果
        first_response = Mock()
        first_response.raise_for_status.return_value = None
        first_response.json.return_value = {
            "result": {
                "uids": ["32353885"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                # 缺少 32353886 和 32353887
            }
        }

        # 第二次批量调用返回剩余结果
        second_response = Mock()
        second_response.raise_for_status.return_value = None
        second_response.json.return_value = {
            "result": {
                "uids": ["32353886"],
                "32353886": {"articleids": [{"idtype": "pmc", "value": "7439636"}]},
                # 仍然缺少 32353887
            }
        }

        # 第三次批量调用没有新结果
        third_response = Mock()
        third_response.raise_for_status.return_value = None
        third_response.json.return_value = {"result": {"uids": []}}

        # 设置 side_effect 模拟重试
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            elif call_count == 2:
                return second_response
            else:
                return third_response

        retriever.session.get = Mock(side_effect=side_effect)

        # 调用处理方法（默认禁用逐个重试）
        processed = retriever.process_papers(papers)

        # 验证结果
        assert processed[0]["pmcid"] == "PMC7439635"  # 第一次批量获取
        assert processed[1]["pmcid"] == "PMC7439636"  # 第二次批量重试获取
        assert "pmcid" not in processed[2]  # 3次重试后仍失败

        # 验证 API 调用次数（3次批量调用）
        assert retriever.session.get.call_count == 3

    @patch("time.sleep")
    def test_process_papers_respects_use_fallback_config(
        self, mock_sleep, retriever, sample_papers
    ):
        """
        测试: process_papers 应该使用配置中的 fallback 设置（批量重试而非单个重试）
        """
        # 模拟部分成功的批量获取
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                # 只成功一个，其他失败
            }
        }

        retriever.session.get = Mock(return_value=mock_response)

        # 调用处理方法，不指定 use_fallback（应该使用配置中的默认值）
        processed = retriever.process_papers(sample_papers)

        # 只应该有批量获取的结果，不应该有单个重试的结果
        assert processed[0]["pmcid"] == "PMC7439635"
        assert "pmcid" not in processed[1]  # 没有使用单个重试

        # 由于启用了批量重试机制（最多3次），应该有3次批量调用
        # 而不是之前的单个重试
        assert retriever.session.get.call_count == 3

    @patch("time.sleep")
    def test_process_papers_max_three_retries(self, mock_sleep, retriever):
        """
        测试: 批量重试最多重试3次
        """
        papers = [{"pmid": "32353885"}, {"pmid": "32353886"}]

        # 模拟始终失败的响应
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": {"uids": []}}  # 始终返回空结果

        retriever.session.get = Mock(return_value=mock_response)

        # 调用处理方法
        processed = retriever.process_papers(papers)

        # 验证没有任何论文获得 PMCID
        assert all("pmcid" not in p for p in processed)

        # 验证恰好调用了3次（1次初始 + 2次重试）
        assert retriever.session.get.call_count == 3

    @patch("time.sleep")
    def test_process_papers_early_stop_on_success(self, mock_sleep, retriever):
        """
        测试: 如果所有 PMIDs 都成功获取，应该提前停止重试
        """
        papers = [{"pmid": "32353885"}, {"pmid": "32353886"}]

        # 模拟第一次就完全成功的响应
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "result": {
                "uids": ["32353885", "32353886"],
                "32353885": {"articleids": [{"idtype": "pmc", "value": "7439635"}]},
                "32353886": {"articleids": [{"idtype": "pmc", "value": "7439636"}]},
            }
        }

        retriever.session.get = Mock(return_value=mock_response)

        # 调用处理方法
        processed = retriever.process_papers(papers)

        # 验证所有论文都获得了 PMCID
        assert processed[0]["pmcid"] == "PMC7439635"
        assert processed[1]["pmcid"] == "PMC7439636"

        # 验证只调用了一次（没有重试）
        assert retriever.session.get.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
