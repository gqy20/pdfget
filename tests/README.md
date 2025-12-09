# PDFget 批量 PMCID 获取功能测试

本文档描述了为批量 PMCID 获取功能编写的测试套件，采用 TDD（测试驱动开发）方法。

## 测试结构

```
tests/
├── README.md                           # 本文件
├── test_batch_pmcid_retrieval.py       # 单元测试：核心功能
├── test_performance_benchmarks.py      # 性能基准测试
└── test_integration_batch_pmcid.py     # 集成测试
```

## 测试概述

### 1. 单元测试 (`test_batch_pmcid_retrieval.py`)

测试批量 PMCID 获取的核心功能，包括：

- **PMID 收集功能** (`_collect_pmids`)
  - 从论文列表中提取有效的 PMIDs
  - 处理空列表、无效 PMIDs 等边界情况

- **批量获取功能** (`_fetch_pmcid_batch`)
  - 正确解析 NCBI ESummary API 响应
  - 处理 PMCID 格式（自动添加 PMC 前缀）
  - 处理没有找到 PMCID 的情况
  - 大量 PMIDs 的分批处理（每批最多 100 个）
  - 遵守 NCBI 速率限制
  - API 错误的优雅处理

- **论文处理功能** (`process_papers`)
  - 更新论文的 PMCID 信息
  - 保留原始数据
  - 处理混合有/无 PMIDs 的论文列表

- **错误处理测试**
  - 无效响应格式
  - 缺失字段
  - 格式错误的 PMIDs

### 2. 性能基准测试 (`test_performance_benchmarks.py`)

定义和验证性能期望：

- **API 调用效率**
  - 期望：500 个 PMIDs 从 500 次调用减少到 5 次（减少 99%）

- **延迟改善**
  - 期望：从 170 秒（逐个）减少到 1.7 秒（批量）
  - 性能提升：100 倍

- **数据传输效率**
  - JSON vs XML：减少 90-95% 的数据传输
  - 500 个 PMIDs：从 200 KB 减少到 10 KB

- **可扩展性**
  - 测试不同规模（100, 250, 500, 1000）的性能表现
  - 验证 O(n/100) 的复杂度

- **内存使用**
  - 每 100 个 PMIDs：约 7 KB
  - 1000 个 PMIDs：约 70 KB（不包括 Python 对象开销）

- **并发处理潜力**
  - 理论上可以获得 2-3 倍的额外性能提升

### 3. 集成测试 (`test_integration_batch_pmcid.py`)

测试批量功能与现有系统的集成：

- **Manager 集成**
  - 验证 `PdfManager.process_papers()` 使用批量获取
  - 确保正确传递有效的 PMIDs

- **端到端测试**
  - 模拟真实的 API 调用流程
  - 验证完整的请求-响应周期

- **结果一致性**
  - 确保批量方法返回与逐个方法相同的结果
  - 防止回归

- **大批量处理**
  - 测试超过 100 个 PMIDs 的分批处理
  - 验证 API 调用次数和批次大小

- **错误处理**
  - 部分失败的处理
  - 降级到逐个处理的机制

- **向后兼容性**
  - 确保原有接口仍然可用
  - 不破坏现有功能

- **工作流程集成**
  - 在文献搜索和获取流程中的表现
  - 与其他功能的协同工作

## TDD 开发流程

1. **编写测试** - 定义期望的行为和性能
2. **运行测试** - 观察失败（因为功能尚未实现）
3. **编写代码** - 实现功能以通过测试
4. **重构优化** - 改进代码质量
5. **重复迭代** - 继续添加功能

## 运行测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 运行特定测试文件
uv run pytest tests/test_batch_pmcid_retrieval.py -v

# 运行特定测试类
uv run pytest tests/test_batch_pmcid_retrieval.py::TestBatchPMCIDRetrieval -v

# 运行性能基准测试
uv run pytest tests/test_performance_benchmarks.py -v -s

# 运行集成测试
uv run pytest tests/test_integration_batch_pmcid.py -v
```

## 期望的测试输出

在功能实现之前，大部分测试会失败，显示：

```
FAILED tests/test_batch_pmcid_retrieval.py::TestBatchPMCIDRetrieval::test_collect_pmids_should_extract_valid_pmids
AttributeError: 'PaperFetcher' object has no attribute '_collect_pmids'
```

这些失败信息指导我们需要实现哪些功能。

## 测试覆盖率目标

- **行覆盖率**: 100%
- **分支覆盖率**: 95% 以上
- **功能覆盖率**: 所有核心功能和边界情况

## 性能指标

功能实现后，应该满足：

- ✅ 10-30 倍性能提升（vs 当前逐个处理）
- ✅ 99% 减少 API 调用次数
- ✅ 90%+ 减少数据传输量
- ✅ 支持处理 1000+ 论文而不超时
- ✅ 内存使用线性增长

## 持续集成

这些测试设计为在 CI/CD 环境中运行：

- 快速单元测试（< 1 分钟）
- 性能基准测试（< 5 分钟）
- 集成测试（< 2 分钟）

## 下一步

1. 根据测试失败信息实现 `_collect_pmids()` 方法
2. 实现 `_fetch_pmcid_batch()` 方法
3. 实现 `process_papers()` 方法
4. 添加配置选项（批量大小、并发数等）
5. 实现错误重试和降级机制
6. 性能优化和基准测试

## 注意事项

- 测试使用 mock 避免实际的 API 调用
- 性能测试跳过实际的 `sleep` 调用
- 所有测试都应该是确定性的（不依赖真实数据）
- 测试应该快速运行，适合频繁执行
