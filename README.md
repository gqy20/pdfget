# PDFGet - 智能文献搜索与批量下载工具

![PyPI](https://img.shields.io/pypi/v/pdfget) ![Python](https://img.shields.io/pypi/pyversions/pdfget) ![License](https://img.shields.io/pypi/l/pdfget)

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## 项目概述

PDFGet 是一个专为科研工作者设计的智能文献获取工具，集成 PubMed、Europe PMC 等权威学术数据库。

### 核心特性

- 🔍 **智能搜索** - 支持高级检索语法，精确查找文献
- 📥 **批量下载** - 自动下载开放获取 PDF，支持并发
- 📋 **混合输入** - 支持 CSV 文件（PMCID/PMID/DOI）批量下载
- 🎯 **PMC 过滤** - 使用 `pubmed pmc[sb]` 确保 100% 可下载
- 💾 **智能缓存** - 避免重复下载，提升效率

## 快速开始

### 安装

```bash
# 使用 pip 安装
pip install pdfget

# 使用 uv 安装（推荐）
uv add pdfget
```

### 5分钟上手

```bash
# 1. 搜索并下载 20 篇癌症相关文献
pdfget -s "cancer AND pubmed pmc[sb]" -l 20 -d

# 2. 从 CSV 文件批量下载
pdfget -m pmcids.csv -c pmcid -d

# 3. 下载单个文献
pdfget -m "PMC5764346" -d

# 4. 查看统计信息（不下载）
pdfget -s "machine learning" -l 100
```

## 常见使用场景

### 场景1：搜索并下载可下载的文献

使用 PMC 过滤器确保所有结果都能下载：

```bash
# 搜索并下载 50 篇机器学习相关的 PMC 收录文献
pdfget -s "machine learning AND pubmed pmc[sb]" -l 50 -d -o my_papers
```

### 场景2：CSV 批量下载

从 CSV 文件批量下载 PMCID：

```bash
# CSV 文件格式：
# pmcid
# PMC5764346
# PMC5761748
# ...

# 执行下载
pdfget -m pmcids.csv -c pmcid -d -t 5
```

### 场景3：统计开放获取情况

了解某个领域的开放获取比例：

```bash
# 统计癌症免疫疗法文献的 PMCID 情况
pdfget -s "cancer immunotherapy" -l 1000
```

### 场景4：混合标识符下载

支持 PMCID、PMID、DOI 混合输入：

```bash
# 单个或多个标识符
pdfget -m "PMC123456"
pdfget -m "PMC123456,38238491,10.1186/s12916-020-01690-4" -d
```

## 安装

### 系统要求
- Python 3.12 或更高版本
- 推荐 uv 包管理器

### 安装方法

```bash
# 从 PyPI 安装
pip install pdfget

# 从源码安装
git clone https://github.com/gqy20/pdfget.git
cd pdfget
pip install -e .
```

### 使用 uv 运行

```bash
uv run pdfget -s "machine learning" -l 20
```

## 核心参数

### 必需参数（二选一）
- `-s QUERY` - 搜索文献
- `-m INPUT` - 批量输入（CSV文件/标识符）

### 常用参数
- `-d` - 下载 PDF（默认为统计模式）
- `-l NUM` - 处理数量（默认 200）
- `-t NUM` - 并发线程数（默认 3）
- `--delay SEC` - 下载延迟秒数（默认 1.0）
- `-o DIR` - 输出目录（默认 data/pdfs）
- `-v` - 详细输出

### 数据源选择
- `-S pubmed` - PubMed（默认）
- `-S europe_pmc` - Europe PMC
- `-S both` - 同时使用两个数据源

### API 配置（可选）
- `-e EMAIL` - NCBI API 邮箱
- `-k KEY` - NCBI API 密钥

**获取 API 密钥**：访问 [NCBI 账户设置](https://www.ncbi.nlm.nih.gov/account/settings/)

## 使用示例

### 基础搜索和下载

```bash
# 搜索并显示 PMCID 统计
pdfget -s "cancer immunotherapy" -l 100

# 搜索并下载 PDF
pdfget -s "cancer immunotherapy AND pubmed pmc[sb]" -l 20 -d

# 指定输出目录
pdfget -s "machine learning" -l 50 -d -o ~/papers
```

### CSV 批量下载

```bash
# 自动检测列名
pdfget -m identifiers.csv -d

# 指定列名
pdfget -m data.csv -c pmcid -d -t 5

# 调整下载速度
pdfget -m pmcids.csv -d --delay 0.5
```

### PMC 过滤技巧

```bash
# 确保 100% 可下载（推荐）
pdfget -s "your-topic AND pubmed pmc[sb]" -l 50 -d

# 包含所有免费全文（部分可下载）
pdfget -s "your-topic filter[free full text]" -l 100

# 按年份过滤
pdfget -s "machine learning AND pubmed pmc[sb] 2020:2023[pd]" -l 30 -d
```

## 详细文档

完整使用指南请查看：[📚 用户详细文档](docs/USER_GUIDE.md)

详细文档包含：
- 高级检索语法
- 完整参数说明
- 输出格式详解
- 故障排除

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 相关链接

- 🏠 **项目主页**: [GitHub Repository](https://github.com/gqy20/pdfget)
- 📧 **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)
- 📝 **更新日志**: [CHANGELOG.md](CHANGELOG.md)
