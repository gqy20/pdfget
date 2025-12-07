# PDFGet - 高效文献下载工具

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## ✨ 核心功能

- 🔍 **高级搜索**：支持布尔运算符、字段检索、短语检索
- 🚀 **并发下载**：多线程并行下载，3-5倍速度提升
- 📊 **丰富元数据**：包含作者、单位、期刊、摘要、引用等完整信息
- 💾 **智能缓存**：24小时缓存，避免重复下载
- 📄 **批量处理**：支持CSV/TXT文件批量下载

## 🛠️ 快速开始

### 安装
```bash
pip install pdfget
# 或使用uv
uv run pdfget
```

### 基础使用

```bash
# 搜索文献
uv run pdfget -s "machine learning" -l 20

# 搜索并下载
uv run pdfget -s "cancer immunotherapy" -d

# 并发下载（5线程）
uv run pdfget -s "deep learning" -l 50 -d -t 5

# 单篇文献下载
uv run pdfget --doi 10.1016/j.cell.2020.01.021

# 批量下载
uv run pdfget -i dois.csv -d -t 3
```

## 🎯 高级检索语法

### 布尔运算符
```bash
# AND: 同时包含多个关键词
uv run pdfget -s "cancer AND immunotherapy" -l 30

# OR: 包含任意关键词
uv run pdfget -s "machine OR deep learning" -l 20

# NOT: 排除特定词汇
uv run pdfget -s "cancer AND immunotherapy NOT review" -l 30

# 复杂组合
uv run pdfget -s "(cancer OR tumor) AND immunotherapy NOT mice" -l 25
```

### 字段检索
```bash
# 标题检索
uv run pdfget -s 'title:"deep learning"' -l 15

# 作者检索
uv run pdfget -s 'author:hinton AND title:"neural networks"' -l 10

# 期刊检索
uv run pdfget -s 'journal:nature AND cancer' -l 20

# 年份检索
uv run pdfget -s 'cancer AND year:2023' -l 15
```

### 短语和精确匹配
```bash
# 短语检索（用双引号）
uv run pdfget -s '"quantum computing"' -l 10

# 混合使用
uv run pdfget -s '"gene expression" AND (cancer OR tumor) NOT review' -l 20
```

### 实用检索技巧
- 使用括号分组复杂的布尔逻辑
- 短语用双引号确保精确匹配
- 可以组合多个字段进行精确检索
- 使用 NOT 过滤掉不相关的结果（如综述、评论等）

## 📊 性能优势

| 功能 | 单线程 | 并发下载 | 提升倍数 |
|------|--------|----------|----------|
| 5篇文献 | ~25秒 | ~8秒 | 3x |
| 20篇文献 | ~100秒 | ~25秒 | 4x |
| 50篇文献 | ~250秒 | ~60秒 | 4x |

## 📁 命令行参数

### 核心参数
- `-s QUERY` : 搜索文献
- `--doi DOI` : 下载单个文献
- `-i FILE` : 批量输入文件
- `-d` : 下载PDF

### 优化参数
- `-l NUM` : 搜索结果数量（默认50）
- `-t NUM` : 并发线程数（默认3）
- `-v` : 详细输出

## 💾 输出格式

### 搜索结果
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

### 文件结构
```
data/
├── pdfs/           # 下载的PDF
├── cache/          # 缓存文件
└── download_results.json
```

## 🔧 技术实现

- **Python 3.8+**：现代Python特性
- **ThreadPoolExecutor**：高效的线程池管理
- **Europe PMC API**：权威学术数据源
- **智能缓存**：24小时自动过期
- **线程安全**：并发环境下的数据一致性

## 📈 系统要求

- Python 3.8+
- requests
- pandas

## 📄 许可证

MIT License

## 🚀 更新日志

### v0.1.0
- ✨ 基础DOI下载功能
- ✨ 高级文献搜索
- ✅ 多线程并发下载
- ✅ 完整文献元数据
- ✅ 简洁命令行界面