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
- **PaperFetcher** (`fetcher.py`) - 核心协调器，整合所有功能
- **PaperSearcher** (`searcher.py`) - 文献搜索，支持 PubMed 和 Europe PMC
- **PDFDownloader** (`downloader.py`) - PDF 下载，多源智能重试
- **PMCIDRetriever** (`pmcid.py`) - 批量 PMCID 获取，使用 ESummary API 优化
- **UnifiedDownloadManager** (`manager.py`) - 并发下载管理器
- **Counter** (`counter.py`) - PMCID 统计分析
- **Formatter** (`formatter.py`) - 结果格式化输出

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
- **Europe PMC REST API**：用于开放获取文献搜索和下载

### 命令行工具
项目提供 `pdfget` 命令行工具，主要功能：
- 文献搜索：`pdfget -s "query" -l 50`
- PDF 下载：`pdfget -s "query" -d`
- PMCID 获取：`pdfget -s "query" --pmcid`
- 统计分析：`pdfget -s "query" --count`

### 扩展性设计
- 模块化架构支持添加新数据源
- 下载源可在 `pdf_sources` 配置中扩展
- 支持多种输出格式（console、json、markdown）

### 数据流
1. 搜索流程：搜索 → 缓存 → 结果格式化
2. 下载流程：搜索结果 → PMCID 获取 → PDF 下载 → 文件保存
3. 统计流程：搜索结果 → PMCID 批量查询 → 统计分析
