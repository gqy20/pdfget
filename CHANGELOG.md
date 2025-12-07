# 更新日志

本文档记录了PDFGet项目的所有重要更改。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2025-12-07

### 🎉 首次发布

#### ✨ 新增功能
- **高级文献搜索**：支持布尔运算符(AND、OR、NOT)、字段检索(title:、author:、journal:)、短语检索
- **智能缓存系统**：24小时自动过期，避免重复下载
- **并发下载**：多线程并行下载，3-5倍速度提升
- **批量处理**：支持CSV/TXT文件批量下载
- **丰富元数据**：包含作者、单位、期刊、摘要、引用等10+个字段
- **简洁命令行**：单字母参数(-s, -l, -t, -d, -v)，易于使用

#### 🔧 核心特性
- **Europe PMC API集成**：权威学术数据源
- **线程安全设计**：并发环境下的数据一致性
- **智能重试机制**：网络错误自动重试
- **优雅降级**：PDF不可用时自动获取HTML全文

#### 📊 性能表现
| 文献数量 | 单线程耗时 | 并发耗时 | 性能提升 |
|---------|-----------|----------|----------|
| 5篇     | ~25秒     | ~8秒     | 3x       |
| 20篇    | ~100秒    | ~25秒    | 4x       |
| 50篇    | ~250秒    | ~60秒    | 4x       |

#### 🛠️ 技术实现
- **Python 3.8+**：现代Python特性
- **ThreadPoolExecutor**：高效的线程池管理
- **智能缓存**：24小时自动过期
- **模块化设计**：清晰的代码结构

#### 📦 包结构
```
pdfget/
├── src/pdfget/
│   ├── __init__.py          # 包初始化
│   ├── __main__.py          # 命令行入口
│   ├── main.py              # 主程序逻辑
│   ├── fetcher.py           # 核心文献获取器
│   ├── concurrent_downloader.py  # 并发下载器
│   └── config.py            # 配置文件
├── tests/                   # 测试文件
├── data/                    # 数据目录
│   ├── pdfs/               # 下载的PDF
│   └── cache/              # 缓存文件
├── tests/                   # pytest测试
├── README.md               # 项目文档
├── CHANGELOG.md            # 更新日志
├── pyproject.toml          # 项目配置
└── pytest.ini             # 测试配置
```

#### 🧪 测试覆盖
- **28个测试用例**：100%通过率
- **核心功能覆盖**：60%+代码覆盖率
- **Mock测试**：避免实际网络请求
- **并发测试**：验证多线程安全性

#### 📖 使用示例
```bash
# 搜索文献
uv run pdfget -s "machine learning" -l 20

# 高级检索
uv run pdfget -s "cancer AND immunotherapy NOT review" -l 30

# 并发下载
uv run pdfget -s "deep learning" -l 50 -d -t 5

# 单篇下载
uv run pdfget --doi 10.1016/j.cell.2020.01.021

# 批量下载
uv run pdfget -i dois.csv -d -t 3
```

#### 🔍 高级检索语法
```bash
# 布尔运算符
uv run pdfget -s "cancer AND immunotherapy" -l 30

# 字段检索
uv run pdfget -s 'title:"deep learning" AND author:hinton'

# 短语检索
uv run pdfget -s '"quantum computing"' -l 10
```

#### 🏗️ 开发工具集成
- **ruff**：代码规范检查
- **pytest**：单元测试框架
- **pytest-cov**：测试覆盖率
- **uv**：现代Python包管理

#### 📄 许可证
- MIT License - 允许自由使用和修改

---

## 版本说明

- **主版本**：不兼容的API修改
- **次版本**：向下兼容的功能性新增
- **修订版本**：向下兼容的问题修正

## 贡献指南

欢迎提交Issue和Pull Request来改进这个工具！

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至 gqy (qingyu_ge@foxmail.com)