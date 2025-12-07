# PDF文献下载器

独立的文献PDF下载工具，专门用于从开放获取资源下载学术论文。

## 🚀 功能特性

- **智能文献获取**: 基于DOI自动获取开放获取文献
- **多源下载**: 支持多个PDF源，自动切换
- **缓存机制**: 24小时智能缓存，避免重复下载
- **批量处理**: 支持从CSV或TXT文件批量下载
- **详细日志**: 完整的下载过程记录
- **优雅降级**: PDF不可用时自动获取HTML全文

## 📋 系统要求

- Python 3.8+
- requests库
- pandas库（CSV文件支持）

## 🛠️ 安装配置

### 1. 安装依赖
```bash
pip install requests pandas
```

### 2. 运行环境
```bash
# 进入PDF下载器目录
cd pdf_downloader

# 创建必要的数据目录
mkdir -p data/{pdfs,cache,logs}
```

## 📖 使用方法

### 基本使用

#### 下载单个文献
```bash
# 下载指定DOI的文献
python main.py --doi 10.1016/j.cell.2020.01.021

# 启用详细日志
python main.py --doi 10.1016/j.cell.2020.01.021 --verbose

# 自定义输出目录
python main.py --doi 10.1016/j.cell.2020.01.021 --output ./my_pdfs
```

#### 批量下载
```bash
# 从CSV文件批量下载（默认doi列）
python main.py --input dois.csv

# 指定CSV文件中的DOI列名
python main.py --input papers.csv --column paper_doi

# 从文本文件批量下载（每行一个DOI）
python main.py --input dois.txt

# 自定义请求延迟（避免被限制）
python main.py --input dois.csv --delay 2.0
```

### 高级选项

```bash
# 自定义超时时间
python main.py --doi 10.1016/j.cell.2020.01.021 --timeout 60

# 自定义缓存目录
python main.py --input dois.csv --cache ./my_cache

# 组合使用多个选项
python main.py --input papers.csv \
    --column doi_identifier \
    --output ./downloads \
    --delay 1.5 \
    --timeout 45 \
    --verbose
```

## 📁 输入格式

### CSV文件
包含DOI列的CSV文件：
```csv
title,authors,doi,year
Paper Title 1,Author1,Author2,10.1016/j.cell.2020.01.021,2020
Paper Title 2,Author3,Author4,10.1038/nature.2021.12345,2021
```

### 文本文件
每行一个DOI的文本文件：
```
10.1016/j.cell.2020.01.021
10.1038/nature.2021.12345
10.1126/science.2022.67890
```

## 📁 输出结构

```
pdf_downloader/
├── data/
│   ├── pdfs/              # 下载的PDF文件
│   │   ├── PMC123456_10.1016.j.cell.2020.01.021.pdf
│   │   └── ...
│   ├── cache/             # 缓存文件
│   │   ├── cache_abc123def.json
│   │   └── ...
│   └── logs/              # 日志文件
│       ├── downloader.log
│       └── fetcher.log
├── download_results.json  # 批量下载结果
└── ...
```

## ⚙️ 配置说明

### 下载配置 (config/settings.py)
```python
DOWNLOAD_CONFIG = {
    "timeout": 30,                    # 请求超时时间（秒）
    "max_retries": 3,                 # 最大重试次数
    "delay_between_requests": 1.0,    # 请求间延迟（秒）
    "max_concurrent": 5,              # 最大并发数
    "cache_expiry_hours": 24,         # 缓存过期时间（小时）
}
```

### PDF源配置
支持的PDF下载源：
1. NCBI PMC主源
2. NCBI PMC文件名源
3. Europe PMC源

### 缓存策略
- 使用DOI的MD5哈希作为缓存键
- 24小时自动过期
- 检查PDF文件是否存在
- 自动清理损坏的缓存

## 🔍 故障排除

### 常见问题

1. **文献未找到**
   ```
   ❌ 获取失败: Not found in Europe PMC
   ```
   - 确认DOI格式正确
   - 检查文献是否为开放获取

2. **网络超时**
   ```
   ❌ 获取失败: Request timeout
   ```
   - 增加超时时间: `--timeout 60`
   - 减少并发数或增加延迟

3. **非开放获取**
   ```
   ⏭️ 无PMCID，非开放获取文献
   ```
   - 该文献不是开放获取，无法免费下载

4. **PDF下载失败**
   ```
   ❌ 获取失败: All PDF sources failed
   ```
   - 系统会自动返回HTML全文链接
   - 检查日志了解详细错误信息

### 日志查看
```bash
# 查看主日志
tail -f data/logs/downloader.log

# 查看获取器日志
tail -f data/logs/fetcher.log

# 启用详细日志
python main.py --doi YOUR_DOI --verbose
```

## 📊 性能指标

基于测试数据：
- **下载速度**: 约2-5秒/篇（取决于网络和文件大小）
- **成功率**: 开放获取文献>90%
- **缓存命中**: 24小时内重复请求100%命中
- **并发能力**: 建议同时下载不超过10篇

## 🛠️ 开发指南

### 代码结构
```
pdf_downloader/
├── core/
│   ├── __init__.py
│   └── fetcher.py          # 核心下载器
├── utils/
│   ├── __init__.py
│   └── logger.py           # 日志工具
├── config/
│   ├── __init__.py
│   └── settings.py         # 配置文件
├── scripts/
│   ├── unified_downloader.py
│   ├── enhanced_downloader.py
│   └── optimized_downloader.py
├── tests/
├── data/
│   ├── pdfs/
│   ├── cache/
│   └── logs/
├── main.py                 # 主程序入口
└── README.md
```

### 扩展功能

1. **添加新的PDF源**
   在`config/settings.py`中的`PDF_SOURCES`添加新URL

2. **自定义缓存策略**
   修改`fetcher.py`中的缓存相关方法

3. **添加输出格式**
   在`main.py`中添加新的输出处理逻辑

## 📄 许可证

本项目遵循MIT许可证。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个工具。

## 📞 联系方式

如有问题或建议，请通过以下方式联系：
- 提交Issue
- 发送邮件至项目维护者

---

**注意**: 本工具仅用于下载开放获取的学术文献，请遵守相关的版权和使用条款。