# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 开发命令

### 环境管理
```bash
# 使用 uv 安装依赖（推荐）
uv sync --dev

# 或使用 pip
pip install -e ".[dev]"
```

### 代码质量
```bash
# 代码格式化
black src tests
ruff format src tests

# 代码检查
ruff check src tests
mypy src

# 类型检查
mypy src/pdfget
```

### 测试
```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_searcher.py
pytest tests/test_downloader.py
pytest tests/test_pmcid_module.py

# 运行测试并生成覆盖率报告
pytest --cov=src/pdfget --cov-report=html
```

### 构建和发布
```bash
# 构建包
hatchling build

# 发布到 TestPyPI
twine upload --repository testpypi dist/*

# 发布到 PyPI
twine upload dist/*
```

## 项目架构

### 核心模块结构
- **PaperFetcher** (`fetcher.py`) - 搜索、元数据补全、PMID/DOI 解析协调器
- **PaperSearcher** (`searcher.py`) - 文献搜索；单公开入口 `search_papers(query, limit, source)`，source ∈ `pubmed/europe_pmc/arxiv/both/all`；内部按源 raw API 调用全部下划线化（`_search_*_api`）
- **input_parser** (`input_parser.py`) - CSV/标识符输入解析（列名、混分隔、单值）
- **input_planner** (`input_planner.py`) - CSV/标识符 → `download_plan.v1`
- **download_plan** (`download_plan.py`) - 搜索结果、直接输入、续跑、下载器之间的统一计划协议 (`download_plan.v1`)
- **download_service** (`download_service.py`) - `execute_download_plan` 纯函数（plan → 实际下载）+ `download_from_unified_input` 组合 façade；CLI workflow 复用 `execute_download_plan`，不复刻 façade 逻辑
- **LocalPDFStore** (`storage.py`) - 本地 PDF 存档抽象（`path_for / has / open_writer / list_records / cleanup_older_than / cache_info`）；`PDFDownloader` 通过注入持有，所有文件 IO 委托给它
- **PDFDownloader** (`downloader.py`) - 单公开入口 `download_paper(record)`；内部按源策略 `_via_pmcid / _via_arxiv / _via_direct`
- **pmc_oa_service** (`pmc_oa_service.py`) - PMC Open Access Web Service 的封装
- **UnifiedDownloadManager** (`manager.py`) - 并发下载管理器，只按下载计划中的论文记录执行下载
- **PMCIDRetriever** (`pmcid.py`) - 批量 PMCID 获取，使用 ESummary API 优化
- **Counter** (`counter.py`) - PMCID 统计分析，显示 PMC 比例
- **Formatter** (`formatter.py`) - 结果格式化输出（`format_type="console"|"json"|"markdown"`）
- **doi_converter** (`doi_converter.py`) - DOI ↔ PMCID 转换
- **filename** (`filename.py`) - PDF 文件名生成
- **retry** (`retry.py`) - 通用重试/退避工具
- **run_report** (`run_report.py`) - `run_summary.v2` 运行报告与失败诊断
- **schemas** (`schemas.py`) - CLI / 运行报告的字段与序列化定义
- **protocols** (`protocols.py`) - 服务边界 Protocol
- **cli_workflows** (`cli_workflows.py`) - CLI 业务流编排（与 `main.py` 解耦）
- **abstract_supplementor** (`abstract_supplementor.py`) - 通过 XML 补充缺失摘要（Europe PMC）
- **paper_schema** (`paper_schema.py`) - `paper_record.v1` 标准化字段
- **base/utils** (`base/`, `utils/`) - 基础抽象与工具子包

### 配置管理
- 全局配置在 `config.py` 中管理
- 支持 NCBI API 邮箱配置以提高请求限制
- 缓存目录结构：`data/.cache/`（API 缓存）、`data/pdfs/`（PDF 文件）

### 性能优化要点
1. **批量 PMCID 获取**：使用 ESummary API 替代 EFetch，性能提升 10-30 倍
2. **智能缓存**：避免重复 API 请求和下载
3. **并发控制**：支持多线程下载，使用延迟策略遵守 API 限制
4. **流式处理**：避免大对象占用内存

### API 集成
- **NCBI E-utilities**：用于 PubMed 搜索和 PMCID 获取
  - 支持 `pubmed pmc[sb]` 过滤器确保 100% PMC 收录
  - 支持 `filter[free full text]` 过滤器获取所有免费全文
- **Europe PMC REST API**：用于开放获取文献搜索和下载

### 命令行工具
项目提供 `pdfget` 命令行工具，主要功能：
- 文献搜索：`pdfget -s "query" -l 50`
- PMC 过滤搜索：`pdfget -s "cancer AND pubmed pmc[sb]" -l 100`
- PDF 下载：`pdfget -s "query" -d`
- 混合输入下载：`pdfget -m examples/pmcids.csv`
- 统计分析：`pdfget -s "query" --count`

### 扩展性设计
- 检索、输入解析和下载之间通过 `download_plan.v1` 连接；下载管理器不再兼容裸 DOI 字符串列表，调用方需要先生成论文记录或使用 `download_from_unified_input()`（或 `execute_download_plan(plan, ...)` 当 plan 已构造好）
- 三大核心类的公开表面收口到单入口：`PDFDownloader.download_paper(record)`、`PaperSearcher.search_papers(query, limit, source)`、`download_service.execute_download_plan(plan, ...)`；其余全部下划线化
- 运行报告使用 `run_summary.v2`，包含成功、失败、计划阶段跳过、失败诊断、下载来源尝试明细和聚合统计；`--resume` 支持从 `run_summary.v2` 或 `download_plan.v1` 续跑
- 搜索结果导出使用 `format_type` 参数，日志初始化由 `configure_logging()` / `get_logger()` 负责，不保留旧参数别名
- 下载来源优先级通过 `--source-priority` 或 Python API 的 `source_priority` 控制，支持 `pmc`、`europe_pmc`、`arxiv`、`direct`
- 本地 PDF 存档由 `LocalPDFStore` 抽象，可单独注入到下载器；新增下载源时可复用同一存储
- 模块化架构支持添加新数据源
- 下载源可在 `pdf_sources` 配置中扩展
- 支持多种输出格式（console、json、markdown）

### 数据流
1. 搜索流程：搜索 → 跨源去重 → 缓存 → 结果格式化
2. 下载流程：搜索结果 → 下载计划 → 来源优先级策略 → PDF 下载 → 尝试明细 → 文件保存
3. CSV/标识符下载流程：输入解析 → 下载计划 → 并发下载
4. 统计流程：搜索结果 → PMCID 批量查询 → 统计分析

### 重要功能说明
- **PMC 过滤优化**：使用 `pubmed pmc[sb]` 确保所有结果都有 PMCID，100% 可下载
- **混合输入下载**：支持从 CSV 或命令行读取 PMCID/PMID/DOI/arXiv ID，自动规划可下载项
- **并发下载管理**：下载计划驱动的并发策略，自动处理标识符映射和结果顺序
