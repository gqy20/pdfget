# PDFGet - 智能文献搜索与批量下载工具

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## 1. 项目概述

PDFGet是一个专为科研工作者设计的智能文献搜索与批量下载工具，集成了PubMed、Europe PMC等权威学术数据库，通过模块化架构提供高效的文献获取和管理功能。

### 1.1 主要特性

- 🔍 **智能文献搜索**：支持高级检索语法，可按作者、期刊、年份等精确搜索
- 📊 **PMCID统计分析**：快速统计文献的开放获取情况，支持多种输出格式
- 📥 **批量PDF下载**：自动下载开放获取文献，支持并发下载和智能重试
- 🔗 **多数据源支持**：集成PubMed（默认）和Europe PMC数据库
- 💾 **智能缓存机制**：避免重复API请求和下载，提升效率
- 🎯 **双模式操作**：统计模式（默认）和下载模式，满足不同需求

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
# 搜索文献（默认统计模式，显示PMCID信息）
pdfget -s "machine learning" -l 20

# 下载PDF（添加-d参数）
pdfget -s "deep learning" -l 50 -d

# 指定Europe PMC作为数据源
pdfget -s "quantum" -S europe_pmc -l 30

# 使用多个数据源搜索
pdfget -s "cancer immunotherapy" -S both -l 100
```

如果您使用 uv 作为包管理器，也可以：
```bash
# 使用uv运行
uv run pdfget -s "machine learning" -l 20
```

**说明**：
- 搜索时默认进入统计模式，显示PMCID统计信息
- 添加 `-d` 参数进入下载模式，下载开放获取的PDF
- PubMed 是默认数据源，可指定 `europe_pmc` 或 `both`

## 3. 高级检索语法

PDFGet 支持两种主要模式：**统计模式**（默认）和**下载模式**（使用 `-d` 参数）。

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

# 下载模式（添加-d）
pdfget -s "cancer AND immunotherapy" -l 30 -d
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
- **统计模式**：搜索并显示PMCID统计信息（默认行为）
- **下载模式**：搜索并下载开放获取的PDF（添加 `-d` 参数）

## 4. 命令行参数详解

### 4.1 核心参数
- `-s QUERY` : 搜索文献
- `--doi DOI` : 通过DOI下载单个文献
- `-i FILE` : 批量输入文件
- `-d` : 下载PDF（不指定则为统计模式）

### 4.2 优化参数
- `-l NUM` : 搜索结果数量（默认200）
- `-S SOURCE` : 数据源选择（pubmed/europe_pmc/both，默认pubmed）
- `-t NUM` : 并发线程数（默认3）
- `--format FORMAT` : 统计输出格式（console/json/markdown，默认console）
- `-v` : 详细输出
- `--delay SEC` : 请求延迟秒数
- `--email EMAIL` : NCBI API邮箱（提高请求限制）

## 5. 输出格式与文件结构

### 5.1 搜索结果格式
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

### 5.2 文件目录结构
```
data/
├── pdfs/           # 下载的PDF文件
├── cache/          # 缓存文件
└── search_results.json  # 搜索结果记录
```

### 5.3 PMCID统计结果
当使用搜索功能（不指定 `-d` 参数）时，会返回开放获取文献统计信息：
```json
{
  "query": "关键词",
  "total": 5000,
  "checked": 200,
  "with_pmcid": 90,
  "without_pmcid": 110,
  "rate": 45.0,
  "elapsed_seconds": 30.5,
  "processing_speed": 6.67
}
```

**字段说明**：
- `query`: 搜索的关键词
- `total`: 数据库中匹配的文献总数
- `checked`: 实际检查的文献数量（由 `-l` 参数决定）
- `with_pmcid`: 有PMCID的文献数量
- `without_pmcid`: 无PMCID的文献数量
- `rate`: 有PMCID的文献百分比
- `elapsed_seconds`: 统计耗时
- `processing_speed`: 处理速度（篇/秒）

**输出格式选项**：
- `--format console`: 控制台友好格式（默认）
- `--format json`: 结构化JSON格式，便于程序处理
- `--format markdown`: Markdown格式，便于文档生成

示例：
```bash
# 生成JSON格式的统计报告
pdfget -s "cancer" -l 100 --format json

# 生成Markdown格式的统计报告
pdfget -s "cancer" -l 100 --format markdown
```

## 7. 许可证

本项目采用 MIT License，允许自由使用和修改。

## 8. 获取帮助

- 🔗 **完整更新日志**: [CHANGELOG.md](CHANGELOG.md)
- 📧 **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)

## 9. 相关链接

- **项目源码**: [GitHub Repository](https://github.com/gqy20/pdfget)
- **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)
- **API文档**:
  - [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
  - [Europe PMC API](https://europepmc.org/RestfulWebService)
