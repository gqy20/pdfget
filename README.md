# PDFGet - 智能文献搜索与批量下载工具

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## 1. 项目概述

PDFGet是一个专为科研工作者设计的智能文献搜索与批量下载工具，集成了PubMed、Europe PMC等权威学术数据库，通过模块化架构提供高效的文献获取和管理功能。

### 1.1 主要特性

- 🔍 **多数据源搜索**：支持PubMed、Europe PMC双数据源
- 🚀 **高性能PMCID获取**：使用ESummary API，批量处理提升10-30倍性能
- 📥 **多源下载**：支持多个PDF下载源，智能重试机制
- 📊 **丰富元数据**：包含作者、期刊、年份、PMCID、DOI等完整信息
- 💾 **智能缓存**：避免重复下载和API请求
- 🧪 **模块化架构**：清晰的代码结构，易于维护和扩展

## 2. 安装与配置

### 2.1 系统要求

- Python 3.12 或更高版本
- 推荐使用 uv 包管理器以获得最佳体验

详细依赖信息请查看 [pyproject.toml](pyproject.toml) 文件。

### 2.2 安装方法

```bash
# 使用pip安装
pip install pdfget

# 使用uv安装（推荐）
uv add pdfget

# 或从源码安装
git clone https://github.com/gqy20/pdfget.git
cd pdfget
pip install -e .
```

### 2.3 快速开始

安装完成后，您可以直接使用 `pdfget` 命令：

```bash
# 搜索文献
pdfget -s "machine learning" -l 20

# 搜索并获取PMCID
pdfget -s "cancer immunotherapy" --pmcid

# 下载PDF（需要PMCID）
pdfget -s "deep learning" -l 50 -d

# 统计PMCID数量
pdfget -s "cancer" --count

# 指定数据源
pdfget -s "quantum" -S europe_pmc -l 30
```

如果您使用 uv 作为包管理器，也可以：
```bash
# 使用uv运行
uv run pdfget -s "machine learning" -l 20
```

## 3. 高级检索语法

### 3.1 布尔运算符
```bash
# AND: 同时包含多个关键词
pdfget -s "cancer AND immunotherapy" -l 30

# OR: 包含任意关键词
pdfget -s "machine OR deep learning" -l 20

# NOT: 排除特定词汇
pdfget -s "cancer AND immunotherapy NOT review" -l 30

# 复杂组合
pdfget -s "(cancer OR tumor) AND immunotherapy NOT mice" -l 25
```

### 3.2 字段检索
```bash
# 标题检索
pdfget -s 'title:"deep learning"' -l 15

# 作者检索
pdfget -s 'author:hinton AND title:"neural networks"' -l 10

# 期刊检索
pdfget -s 'journal:Nature AND cancer' -l 20

# 年份检索
pdfget -s 'cancer AND year:2023' -l 15

# 组合检索（PubMed风格）
pdfget -s '"machine learning"[TI] AND author:hinton' -S pubmed -l 10
```

### 3.3 短语和精确匹配
```bash
# 短语检索（用双引号）
pdfget -s '"quantum computing"' -l 10

# 混合使用
pdfget -s '"gene expression" AND (cancer OR tumor) NOT review' -l 20
```

### 3.4 实用检索技巧
- 使用括号分组复杂的布尔逻辑
- 短语用双引号确保精确匹配
- 可以组合多个字段进行精确检索
- 使用 NOT 过滤掉不相关的结果（如综述、评论等）

## 4. 性能优势

### 4.1 PMCID获取性能优化

通过使用NCBI ESummary API替代传统EFetch，实现了显著的性能提升：

| 处理方式 | 100个PMIDs | 500个PMIDs | 1000个PMIDs |
|---------|-----------|------------|-------------|
| 单个获取 | ~500秒     | ~2500秒    | ~5000秒     |
| 批量获取 | ~45秒      | ~225秒     | ~450秒      |
| **性能提升** | **11x**   | **11x**    | **11x**     |

### 4.2 多数据源对比

| 数据源 | 覆盖范围 | 摘要完整性 | 更新频率 | 特点 |
|--------|---------|-----------|---------|------|
| PubMed | 全球最大 | 需额外获取 | 实时 | 权威、全面 |
| Europe PMC | 开放获取 | 完整 | 准实时 | 包含全文链接 |

## 5. 命令行参数详解

### 5.1 核心参数
- `-s QUERY` : 搜索文献
- `--doi DOI` : 通过DOI下载单个文献
- `-i FILE` : 批量输入文件
- `-d` : 下载PDF
- `--pmcid` : 获取PMCID（不下载）
- `--count` : 统计PMCID数量

### 5.2 优化参数
- `-l NUM` : 搜索结果数量（默认50）
- `-S SOURCE` : 数据源选择（pubmed/europe_pmc/both）
- `-v` : 详细输出
- `--email EMAIL` : NCBI API邮箱（提高请求限制）

## 6. 输出格式与文件结构

### 6.1 搜索结果格式
```json
[
  {
    "pmid": "32353885",
    "doi": "10.1186/s12916-020-01690-4",
    "title": "文献标题",
    "authors": ["作者1", "作者2"],
    "journal": "期刊名称",
    "year": "2023",
    "abstract": "摘要内容",
    "pmcid": "PMC7439635",
    "source": "pubmed"
  }
]
```

### 6.2 文件目录结构
```
data/
├── pdfs/           # 下载的PDF文件
├── cache/          # 缓存文件
└── search_results.json  # 搜索结果记录
```

### 6.3 PMCID统计结果
当使用 `--count` 参数时，会返回开放获取文献统计信息：
```json
{
  "query": "关键词",
  "checked": 1000,
  "with_pmcid": 450,
  "without_pmcid": 550,
  "rate": 45.0,
  "elapsed_seconds": 30.5,
  "processing_speed": 32.8
}
```

## 7. 许可证

本项目采用 MIT License，允许自由使用和修改。

## 8. 项目架构

PDFGet采用模块化架构设计，将功能拆分为独立的模块：

- `searcher.py` - 文献搜索模块（支持PubMed和Europe PMC）
- `pmcid.py` - PMCID批量获取模块（ESummary API优化）
- `downloader.py` - PDF下载模块（多源下载）
- `fetcher.py` - 主入口模块（整合各模块功能）
- `logger.py` - 统一日志管理
- `config.py` - 配置常量

## 9. 获取帮助

- 🔗 **完整更新日志**: [CHANGELOG.md](CHANGELOG.md)
- 📧 **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)

## 🔗 相关链接

- **项目源码**: [GitHub Repository](https://github.com/gqy20/pdfget)
- **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)
- **API文档**:
  - [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
  - [Europe PMC API](https://europepmc.org/RestfulWebService)
