# 更新日志

本文档记录了PDFGet项目的所有重要更改。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.3] - 2025-12-12

### 🚀 新增功能

- **统一批量输入接口**：重构参数结构，简化CLI使用
  - 移除冗余参数：`--doi` 和 `-i` 参数
  - 升级 `-m` 参数为统一批量输入入口，支持三种模式：
    * CSV文件路径（支持自动列名检测）
    * 单个标识符（PMCID/PMID/DOI）
    * 逗号分隔的多个标识符
  - 统一 `-c` 和 `-p` 参数（`-p` 作为 `-c` 的别名，向后兼容）

- **智能输入识别**：
  - CSV列名自动检测（优先级：ID>PMCID>doi>pmid>第一列）
  - 输入类型智能识别（文件/单个/多个/无效）
  - 标识符字符串解析（支持逗号分隔，自动去空格）

- **新增方法**（`fetcher.py`）：
  - `_detect_input_type()`: 检测输入类型
  - `_auto_detect_column()`: 自动检测CSV列名
  - `_parse_identifier_string()`: 解析标识符字符串
  - `download_from_unified_input()`: 统一的输入处理入口

### 🔧 优化改进

- **参数简化**：CLI参数从4个输入参数（`--doi`、`-i`、`-m`、`-s`）简化为2个（`-m`、`-s`）
- **用户体验**：使用更直观，无需记忆多个参数
  - `pdfget -m "PMC123,456,10.1038/xxx"`
  - `pdfget -m data.csv`（自动检测列名）
- **向后兼容**：旧代码使用 `-p` 参数仍能正常工作
- **TDD开发**：遵循测试驱动开发模式，37个测试用例先行

### 🧪 测试

- 新增 `test_unified_input.py`（37个测试用例）：
  - TestInputTypeDetection: 9个测试（输入类型检测）
  - TestColumnAutoDetection: 7个测试（CSV列名自动检测）
  - TestIdentifierStringParsing: 9个测试（标识符字符串解析）
  - TestUnifiedInputDownload: 7个测试（统一下载功能）
  - TestBackwardCompatibility: 2个测试（向后兼容性）
  - TestEdgeCases: 3个测试（边界情况）
- 所有57个测试通过（37新增+20现有）
- 通过pre-commit钩子检查（ruff, black, mypy）

### 📝 文档更新

- 更新README.md，反映新的参数结构和使用方式
- 更新命令行参数文档，说明统一输入接口
- 添加三种输入模式的使用示例
- 说明列名自动检测优先级

### ⚠️ 破坏性更改

- 移除 `--doi` 参数：单个DOI下载现在通过 `-m` 参数实现
- 移除 `-i` 参数：文件输入现在通过 `-m` 参数实现
- 移除 `-p` 参数：完全删除向后兼容的 `-p` 参数，统一使用 `-c` 参数
- `-c` 参数默认值改为自动检测（不再有默认列名）

### 🔄 迁移指南

**旧版本用法 → 新版本用法**：
```bash
# 单个DOI下载
旧: pdfget --doi 10.1038/s41586-024-07146-0
新: pdfget -m "10.1038/s41586-024-07146-0"

# 批量文件输入
旧: pdfget -i data.csv -p ID
新: pdfget -m data.csv -c ID

# 使用-p参数（已移除）
旧: pdfget -m data.csv -p ID
新: pdfget -m data.csv -c ID

# 多个标识符
新: pdfget -m "PMC123,456,10.1038/xxx"
```

## [0.1.4] - 2025-12-12

### 🚀 新增功能

- **混合标识符下载**：支持从CSV文件读取并自动识别PMCID/PMID/DOI混合类型标识符
  - 自动检测标识符类型（PMCID、PMID、DOI）
  - PMID自动转换为PMCID后下载（使用NCBI ESummary API）
  - 支持带或不带PMC前缀的PMCID格式
  - 智能跳过空行和无效标识符
  - 支持自定义CSV列名（默认为"ID"）

- **新增方法**（`fetcher.py`）：
  - `_detect_id_type()`: 自动检测标识符类型
  - `_read_identifiers_from_csv()`: 从CSV读取并分类混合标识符
  - `_convert_pmids_to_pmcids()`: 批量将PMID转换为PMCID
  - `download_from_identifiers()`: 统一的混合标识符下载入口

### 🔧 优化改进

- **命令行增强**：
  - `-m` 参数现在支持混合标识符（原仅支持PMCID）
  - `-p` 参数默认值从"PMCID"改为"ID"，更符合混合标识符场景
  - 添加了混合标识符下载的使用示例

- **类型安全**：增强了类型注解和错误处理
- **测试覆盖**：新增20个测试用例，覆盖所有新功能（100%通过）

### 📝 文档更新

- 更新README.md，添加混合标识符下载功能说明
- 更新命令行参数文档，说明支持的标识符类型
- 添加CSV文件格式示例和使用指南
- 说明PMID转换流程和成功率

### 🧪 测试

- 新增 `test_identifier_download.py`（20个测试用例）：
  - TestIdentifierDetection: 5个测试
  - TestCSVIdentifierReading: 8个测试
  - TestPMIDConversion: 3个测试
  - TestIdentifierDownloadIntegration: 4个测试
- 所有新功能测试100%通过

### 📦 依赖更新

- 添加 `requests-mock>=1.12.1` 用于HTTP请求模拟测试

### ⚠️ 注意事项

- DOI支持将在后续版本添加（当前版本会跳过DOI）
- PMID转换成功率约80-90%（取决于文献是否被PMC收录）
- 无法转换的PMID会被自动跳过

## [0.1.2] - 2025-12-10

### 🚀 新增功能

- **摘要自动补充**：新增从 XML 文件自动补充缺失摘要的功能（仅 Europe PMC 数据源）
  - 智能检测无摘要的记录
  - 自动获取完整 XML 内容并解析摘要
  - 将 Europe PMC 摘要覆盖率从 87% 提升到 97%
  - 添加摘要来源标识（api/xml/none）

### 🔧 优化改进
- **数据源优化**：修复了 Europe PMC 搜索只返回 100 条记录的问题，支持分页获取更多记录
- **字段映射修复**：修正了 Europe PMC 的字段名称错误（`inPmc` → `inPMC`）
- **性能提升**：优化了 PMCID 批量获取逻辑，支持并发处理

### 🐛 Bug 修复
- **分页问题**：解决了 Europe PMC 总是返回最多 100 条记录的 bug
- **字段错误**：修复了 `require_pmcid` 参数导致的查询失败问题
- **缓存集成**：确保补充的摘要能够正确缓存和复用

### 📝 文档更新
- 更新 README.md，添加摘要自动补充功能的说明
- 整理了临时文件，优化了项目结构
- 更新了数据源对比表格，包含摘要覆盖率信息

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
