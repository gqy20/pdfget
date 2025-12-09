# 更新日志

本文档记录了PDFGet项目的所有重要更改。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.1] - 2025-12-09

### 🐛 Bug 修复
- 修复了默认数据源从 `europe_pmc` 到 `pubmed` 的测试不匹配问题
- 修复了代码格式化问题，确保 CI 通过

### 🔧 优化改进
- **默认数据源调整**：将默认数据源从 Europe PMC 改为 PubMed
- **简化配置**：移除了部分冗余的配置参数（如 MAX_CONCURRENT、MAX_FILE_SIZE 等）
- **命令行优化**：简化了 `-l` 参数的行为，统一了搜索和统计逻辑
- **更新依赖**：更新了开发依赖版本（Black 25.0.0、Ruff 0.14.0）

### 📝 文档更新
- 更新 README.md，移除了性能优势和项目架构部分
- 更新了命令行参数说明，添加了 `--format` 参数
- 更新了主要特性描述，更贴近用户实际需求
- 添加了统计模式和下载模式的详细说明

## [0.1.0] - 2025-12-09

### 🎉 首次发布

#### ✨ 新增功能
- **多数据源搜索**：支持PubMed、Europe PMC双数据源
- **高性能PMCID获取**：使用ESummary API，批量处理提升10-30倍性能
- **多源PDF下载**：支持多个下载源，智能重试机制
- **PMCID统计功能**：快速统计开放获取文献数量
- **高级检索语法**：支持布尔运算符、字段检索、短语检索
- **模块化架构**：清晰的代码结构，易于维护和扩展

#### 🔧 核心特性
- **批量PMCID处理**：每批最多100个PMIDs，遵守API速率限制
- **智能缓存系统**：避免重复下载和API请求
- **统一日志管理**：彩色输出，支持多级别日志
- **线程安全设计**：并发环境下的数据一致性

#### 📊 性能表现

**PMCID获取性能对比**：
| 处理方式 | 100个PMIDs | 500个PMIDs | 1000个PMIDs |
|---------|-----------|------------|-------------|
| 单个获取 | ~500秒     | ~2500秒    | ~5000秒     |
| 批量获取 | ~45秒      | ~225秒     | ~450秒      |
| **性能提升** | **11x**   | **11x**    | **11x**     |

**多数据源对比**：
| 数据源 | 覆盖范围 | 摘要完整性 | 更新频率 | 特点 |
|--------|---------|-----------|---------|------|
| PubMed | 全球最大 | 需额外获取 | 实时 | 权威、全面 |
| Europe PMC | 开放获取 | 完整 | 准实时 | 包含全文链接 |

#### 🛠️ 技术实现
- **Python 3.12+**：现代Python特性和类型注解
- **模块化架构**：功能拆分为独立模块（searcher, pmcid, downloader, fetcher）
- **批量API优化**：使用NCBI ESummary API替代EFetch
- **速率限制处理**：遵守各API的请求频率限制
- **自动化代码质量**：pre-commit hooks（black, ruff, mypy）
- **依赖管理**：使用uv作为推荐的包管理器

#### 📦 包结构
```
pdfget/
├── src/pdfget/
│   ├── __init__.py          # 包初始化和导出
│   ├── __main__.py          # 命令行入口
│   ├── main.py              # 主程序逻辑
│   ├── fetcher.py           # 主入口模块（整合各功能）
│   ├── searcher.py          # 文献搜索模块
│   ├── pmcid.py             # PMCID批量获取模块
│   ├── downloader.py        # PDF下载模块
│   ├── manager.py           # 下载管理器
│   ├── counter.py           # PMCID统计器
│   ├── formatter.py         # 结果格式化器
│   ├── logger.py            # 统一日志管理
│   └── config.py            # 配置常量
├── tests/                   # 测试文件
│   ├── test_searcher.py     # 搜索模块测试
│   ├── test_pmcid_module.py # PMCID模块测试
│   ├── test_downloader.py   # 下载模块测试
│   └── README.md            # 测试说明
├── data/                    # 数据目录
│   ├── pdfs/               # 下载的PDF
│   └── cache/              # 缓存文件
├── examples/                # 示例数据和结果
├── README.md               # 项目文档
├── CHANGELOG.md            # 更新日志
├── pyproject.toml          # 项目配置
├── pytest.ini             # 测试配置
└── .pre-commit-config.yaml # 预提交钩子配置
```

#### 🧪 测试覆盖
- **46个测试用例**：模块化测试，100%通过率
  - searcher.py: 16个测试用例
  - pmcid.py: 14个测试用例（含批量处理测试）
  - downloader.py: 16个测试用例
- **Mock测试**：避免实际网络请求，测试覆盖率90%+
- **集成测试**：验证模块间协作

#### 📖 使用示例
```bash
# 搜索文献
pdfget -s "machine learning" -l 20

# 获取PMCID
pdfget -s "cancer immunotherapy" --pmcid

# 统计PMCID数量
pdfget -s "deep learning" --count

# 下载PDF（需要PMCID）
pdfget -s "quantum computing" -l 50 -d

# 指定数据源
pdfget -s "cancer" -S europe_pmc -l 30
```

#### 🔍 高级检索语法
```bash
# 布尔运算符
pdfget -s "cancer AND immunotherapy NOT review" -l 30

# 字段检索
pdfget -s 'title:"deep learning" AND author:hinton' -l 20

# 期刊和年份
pdfget -s 'journal:Nature AND year:2023' -l 25
```

#### 🏗️ 开发工具集成
- **black**：代码格式化工具
- **ruff**：快速的Python linter和格式化器
- **mypy**：静态类型检查
- **pytest**：单元测试框架
- **pytest-cov**：测试覆盖率
- **pytest-mock**：Mock测试支持
- **uv**：现代Python包管理器（推荐）
- **pre-commit**：Git预提交钩子

#### 📄 许可证
- MIT License - 允许自由使用和修改

---

## 版本说明

- **主版本**：不兼容的API修改
- **次版本**：向下兼容的功能性新增
- **修订版本**：向下兼容的问题修正

## 贡献指南

欢迎提交Issue和Pull Request来改进这个工具！

### 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/gqy20/pdfget.git
cd pdfget

# 安装开发依赖（推荐使用uv）
uv sync --dev

# 安装预提交钩子
pre-commit install

# 运行测试
uv run pytest
```

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至 gqy (qingyu_ge@foxmail.com)
