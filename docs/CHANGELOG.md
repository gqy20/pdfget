# 更新日志

本文档记录了PDFGet项目的所有重要更改。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.4] - 2025-12-24

### 🎉 新增功能
- **可配置下载延迟**：新增 `--delay` 参数支持自定义下载间隔（默认 0.5 秒）
  - 用于遵守 API 速率限制
  - 适用于批量下载场景

### 🐛 Bug 修复
- **输出目录参数**：修复 `-o/--output` 参数不生效的问题
- **文件命名优化**：移除 PDF 文件名中冗余的 "unknown" 后缀
- **CI 性能测试**：修复因 NCBI API 速率限制导致的测试失败
- **备用源返回值**：修复备用下载源的返回值处理

### 🔧 重构优化
- **配置系统统一**：移除 `TimeoutConfig` 和 `NetworkConfig` 类
  - 使用简单字典配置替代对象配置
  - 简化配置管理逻辑
- **移除冗余封装**：删除 `PaperFetcher` 中的重复封装方法
  - 移除 `_normalize_pmcid()` 和 `_detect_id_type()`
  - 直接使用 `IdentifierUtils` 工具类

### 📚 文档改进
- **文档结构重构**：将 README.md 和用户指南拆分为独立文件
  - `README.md` - 项目简介和快速开始
  - `docs/USER_GUIDE.md` - 详细使用文档
- **徽章更新**：添加 PyPI 下载徽章
- **参数说明完善**：添加 `--delay` 参数文档

### 🧪 测试更新
- **移除废弃测试**：删除已移除类的测试代码
- **类型注解完善**：添加 `ConfigDict` 类型注解以通过 mypy 检查

### 🛠️ 项目配置
- **更新 .gitignore**：优化忽略规则

---

## [0.1.3] - 2025-12-22

### 🎉 新增功能
- **DOI支持**：完整的DOI到PMCID转换和下载功能
  - 集成 Europe PMC API 作为主要数据源（转换成功率约60-80%）
  - 支持 CrossRef API 作为备选方案
  - 实现批量DOI转换优化，处理速度约100个DOI/30-60秒
  - 智能缓存机制，避免重复查询

- **混合标识符支持**：完整的PMCID/PMID/DOI混合标识符处理
  - 支持单个DOI下载：`pdfget -m "10.1186/s12916-020-01690-4"`
  - 支持混合标识符：`pdfget -m "DOI1,PMID1,PMCID1"`
  - 支持CSV文件包含DOI列，自动识别和转换

### 🔧 技术改进
- **新增DOIConverter模块**：专门的DOI转换器
  - 支持单个和批量DOI转换
  - 速率限制和重试机制
  - 内存缓存优化
  - 完整的错误处理和日志记录

- **增强测试覆盖**：
  - 15个DOI转换器单元测试
  - 10个系统集成测试
  - 覆盖正常流程、错误处理、缓存、速率限制等场景

### 📚 文档更新
- 更新README.md，将DOI支持从"开发中"更新为"已实现"
- 添加完整的使用示例和说明
- 更新功能实现状态表

### 🛠️ 代码质量
- 解决所有代码质量警告（ruff/mypy）
- 完善类型注解和错误处理
- 优化测试代码结构
- 修复GitHub Actions CI失败问题，所有233个测试通过

### ⚡ 性能优化
- DOI转换支持批量处理
- 智能缓存减少重复API请求
- 优化的网络请求和重试机制

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
