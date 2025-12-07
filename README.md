# PDFGet - 高效文献下载工具

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## 1. 项目概述

PDFGet是一个专为科研工作者设计的智能文献搜索与批量下载工具，集成了Europe PMC等权威学术数据库，提供高效的文献获取和管理功能。

### 1.1 主要特性

- 🔍 **高级搜索**：支持布尔运算符、字段检索、短语检索
- 🚀 **并发下载**：多线程并行下载，3-5倍速度提升
- 📊 **丰富元数据**：包含作者、单位、期刊、摘要、引用等完整信息
- 💾 **智能缓存**：24小时缓存，避免重复下载
- 📄 **批量处理**：支持CSV/TXT文件批量下载

## 2. 安装与配置

### 2.1 系统要求

详细的系统要求和依赖信息请查看 [pyproject.toml](pyproject.toml) 文件。

### 2.2 安装方法

```bash
# 使用pip安装
pip install pdfget

# 使用uv安装
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

# 搜索并下载
pdfget -s "cancer immunotherapy" -d

# 并发下载（5线程）
pdfget -s "deep learning" -l 50 -d -t 5

# 单篇文献下载
pdfget --doi 10.1016/j.cell.2020.01.021

# 批量下载
pdfget -i dois.csv -d -t 3
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
pdfget -s 'journal:nature AND cancer' -l 20

# 年份检索
pdfget -s 'cancer AND year:2023' -l 15
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

### 4.1 并发下载效率对比

| 文献数量 | 单线程耗时 | 并发耗时 | 性能提升 |
|---------|-----------|----------|----------|
| 5篇     | ~25秒     | ~8秒     | 3x       |
| 20篇    | ~100秒    | ~25秒    | 4x       |
| 50篇    | ~250秒    | ~60秒    | 4x       |

## 5. 命令行参数详解

### 5.1 核心参数
- `-s QUERY` : 搜索文献
- `--doi DOI` : 下载单个文献
- `-i FILE` : 批量输入文件
- `-d` : 下载PDF

### 5.2 优化参数
- `-l NUM` : 搜索结果数量（默认50）
- `-t NUM` : 并发线程数（默认3）
- `-v` : 详细输出

## 6. 输出格式与文件结构

### 6.1 搜索结果格式
```json
{
  "query": "关键词",
  "total": 10,
  "results": [
    {
      "title": "文献标题",
      "authors": ["作者1", "作者2"],
      "journal": "期刊名称",
      "year": "2025",
      "doi": "10.1016/xxx",
      "affiliation": "作者单位",
      "citedBy": 0,
      "keywords": ["关键词1", "关键词2"]
    }
  ]
}
```

### 6.2 文件目录结构
```
data/
├── pdfs/           # 下载的PDF文件
├── cache/          # 缓存文件
└── download_results.json  # 下载结果记录
```

## 7. 技术实现架构

### 7.1 核心技术栈
- **Python 3.12+**：现代Python特性和类型注解
- **ThreadPoolExecutor**：高效的线程池管理
- **Europe PMC API**：权威学术数据源
- **智能缓存**：24小时自动过期机制
- **线程安全**：并发环境下的数据一致性保证

## 8. 开发与贡献

### 8.1 开发环境设置
```bash
# 克隆仓库
git clone https://github.com/gqy20/pdfget.git
cd pdfget

# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest tests/ -v

# 代码质量检查
uv run ruff check .
uv run mypy src/
```

### 8.2 项目结构
```
pdfget/
├── src/pdfget/
│   ├── __init__.py          # 包初始化
│   ├── __main__.py          # 命令行入口
│   ├── main.py              # 主程序逻辑
│   ├── fetcher.py           # 核心文献获取器
│   ├── downloader.py        # 并发下载器
│   └── config.py            # 配置文件
├── tests/                   # 测试文件
├── data/                    # 数据目录
├── .github/workflows/       # CI/CD配置
├── README.md               # 项目文档
├── CHANGELOG.md            # 更新日志
└── pyproject.toml          # 项目配置
```

## 9. 许可证与更新日志

### 9.1 许可证
本项目采用 MIT License，允许自由使用和修改。

### 9.2 更新日志

#### v0.1.0 (2025-12-07)
- ✨ 基础DOI下载功能
- ✨ 高级文献搜索（支持布尔运算、字段检索、短语检索）
- ✅ 多线程并发下载（3-5倍性能提升）
- ✅ 完整文献元数据（10+个字段信息）
- ✅ 智能缓存系统（24小时自动过期）
- ✅ 简洁命令行界面（单字母参数）
- ✅ 完整的CI/CD流程
- ✅ 28个单元测试，60%+代码覆盖率
