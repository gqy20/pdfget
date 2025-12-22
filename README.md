# PDFGet - 智能文献搜索与批量下载工具

智能文献搜索与批量下载工具，支持高级检索和并发下载。

## 1. 项目概述

PDFGet是一个专为科研工作者设计的智能文献搜索与批量下载工具，集成了PubMed、Europe PMC等权威学术数据库，通过模块化架构提供高效的文献获取和管理功能。

### 1.1 主要特性

- 🔍 **智能文献搜索**：支持高级检索语法，可按作者、期刊、年份等精确搜索
- 📊 **PMCID统计分析**：快速统计文献的开放获取情况，支持多种输出格式
- 📥 **批量PDF下载**：自动下载开放获取文献，支持并发下载和智能重试
- 📋 **混合标识符下载**：支持从CSV文件读取PMCID/PMID混合列表，自动识别并下载（DOI支持开发中）
- 🔗 **多数据源支持**：集成PubMed（默认）和Europe PMC数据库
- 💾 **智能缓存机制**：避免重复API请求和下载，提升效率
- 🎯 **双模式操作**：统计模式（默认）和下载模式，满足不同需求
- 📝 **摘要自动补充**：自动从XML获取缺失的摘要，提高数据完整性（仅Europe PMC）

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

# 使用自己的邮箱和API密钥（可选，提高搜索请求限制）
pdfget -s "quantum" -l 30 -e your-email@example.com -k your-api-key

# 指定Europe PMC作为数据源（自动补充摘要）
pdfget -s "quantum" -S europe_pmc -l 30

# 使用多个数据源搜索
pdfget -s "cancer immunotherapy" -S both -l 100

# 从CSV文件批量下载（支持PMCID/PMID混合，DOI支持开发中）
pdfget -m examples/identifiers.csv
pdfget -m examples/identifiers.csv -c ID
pdfget -m examples/pmcids.csv -c PMCID

# 单个或多个标识符下载
pdfget -m "PMC123456"
pdfget -m "PMC123456,38238491"  # PMCID和PMID混合
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
- 邮箱和API密钥是可选的，仅用于提高搜索请求限制（3→10次/秒）
- 下载功能不需要API密钥，使用公开的开放获取服务

## 3. 高级检索语法

PDFGet 支持两种主要模式：**统计模式**（默认）和**下载模式**（使用 `-d` 参数）。

### 3.1 免费全文过滤

#### 方法一：PMC 全文过滤（推荐，100% 可下载）

使用 `pubmed pmc[sb]` 过滤器只返回在 PubMed Central 中收录的文献，所有结果都可以下载：

```bash
# 搜索 PMC 收录的癌症文献（100% 可下载）
pdfget -s "cancer AND pubmed pmc[sb]" -l 100 -d

# 基因家族研究
pdfget -s '"gene family" AND pubmed pmc[sb]' -l 200

# 配合年份限制
pdfget -s '"machine learning" AND pubmed pmc[sb] 2020:2023[pd]' -l 100 -d
```

#### 方法二：免费全文过滤

使用 `filter[free full text]` 包含所有类型的免费全文：

```bash
# 搜索有免费全文的高血压文献
pdfget -s "hypertension filter[free full text]" -l 100

# 搜索特定领域的免费全文文献
pdfget -s "machine learning filter[free full text]" -l 50 -d
```

**重要说明**：
- **`pubmed pmc[sb]`**：只返回 PMC 收录文献，**100% 可下载**（推荐）
- **`filter[free full text]`**：包含所有免费全文，约 30-40% 可下载
  - 包括：期刊官网免费全文、作者主页、机构仓库等
  - 这些免费全文**不一定被 PMC 收录**，PDFGet 无法下载
- 较新的文献（<1年）被 PMC 收录的概率较低
- 配合年份过滤效果更好，例如：`"cancer AND pubmed pmc[sb] 2020:2023[pd]"`

**为什么有这种差异？**
许多期刊提供免费的开放获取（Open Access），但这些文献：
1. 可能只存在于期刊官网
2. 可能需要 6-12 个月的延迟才被 PMC 收录
3. 有些期刊选择不在 PMC 存放全文
4. PDFGet 只能从 PMC 下载，无法处理其他来源

**建议**：
- 如果需要**确保可下载**：使用 `pubmed pmc[sb]`
- 如果想**发现更多免费文献**（即使不能使用当前软件下载）：使用 `filter[free full text]`

### 3.2 布尔运算符
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
- `-m INPUT` : 批量输入（支持三种模式）
  * CSV文件路径：`pdfget -m data.csv`
  * 单个标识符：`pdfget -m "PMC123456"`
  * 逗号分隔列表：`pdfget -m "PMC123,38238491"`（PMCID和PMID混合）
- `-c COLUMN` : CSV列名（默认自动检测：ID>PMCID>doi>pmid>第一列）
- `-d` : 下载PDF（不指定则为统计模式）

### 4.2 优化参数
- `-l NUM` : 搜索结果数量（默认200）
- `-S SOURCE` : 数据源选择（pubmed/europe_pmc/both，默认pubmed）
- `-t NUM` : 并发线程数（默认3）
- `--format FORMAT` : 统计输出格式（console/json/markdown，默认console）
- `-v` : 详细输出

### 4.3 NCBI API 配置
- `-e EMAIL` : NCBI API邮箱（提高请求限制，推荐设置）
- `-k KEY` : NCBI API密钥（推荐，便于监控使用情况）

**配置示例**：
```bash
# 使用自己的邮箱（推荐）
pdfget -s "cancer" -l 100 -e your-email@example.com

# 使用邮箱和API密钥
pdfget -s "machine learning" -l 500 -e your-email@example.com -k your-api-key
```

**为什么要配置邮箱？**
- 邮箱是可选的，但推荐配置以遵守NCBI使用政策
- 有助于 NCBI 在出现问题时联系您

**获取 NCBI API 密钥**（推荐）：
1. 访问 [NCBI 账户页面](https://www.ncbi.nlm.nih.gov/account/)
2. 创建或登录 NCBI 账户（免费）
3. 登录后访问 [账户设置](https://www.ncbi.nlm.nih.gov/account/settings/)
4. 查找 "API Key Management" 部分创建 API 密钥
5. 提供简要的应用描述并接受服务条款

**重要说明**：
- API 密钥可以将请求限制从 3 次/秒提高到 10 次/秒（仅用于搜索）
- API 密钥主要用于 NCBI 监控使用情况和问题追踪
- 虽不是必需，但建议配置以获得更好的搜索性能

**下载功能说明**：
- PDF 下载不需要 API 密钥（使用公开的 PMC OA Service）
- 下载通过以下公开服务进行：
  - PMC Open Access Web Service
  - Europe PMC 直接下载链接
- 只有 PubMed 搜索和 PMCID 获取需要使用 NCBI E-utilities API

**Europe PMC 说明**：
- Europe PMC 搜索不需要 API 密钥或邮箱
- 使用开放的 REST API，建议将请求速率控制在 10-15 次/秒以下
- 官方未明确说明速率限制，但根据第三方资料约为 20 次/秒
- 如果主要使用 Europe PMC 数据源，可以不配置任何认证信息
- **自动摘要补充**：当 API 返回的记录缺少摘要时，自动从 XML 文件获取完整摘要，将摘要覆盖率从 87% 提升到 97%

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

### 5.4 混合标识符输入格式

`-m` 参数支持三种输入模式，自动识别：

#### 模式1：CSV文件路径
```bash
# 自动检测列名（优先级：ID>PMCID>doi>pmid>第一列）
pdfget -m examples/identifiers.csv

# 手动指定列名
pdfget -m examples/identifiers.csv -c PMCID
pdfget -m examples/identifiers.csv -c ID
```

示例CSV文件：
```csv
ID,Title,Journal
PMC123456,Study on AI,Nature
38238491,Deep Learning Review,Science
PMC789012,Machine Learning Methods,Cell
37851234,Neural Network Research,Cell
```

#### 模式2：单个标识符
```bash
pdfget -m "PMC123456"  # PMCID
pdfget -m "38238491"    # PMID
# DOI示例暂略，当前版本暂不支持
```

#### 模式3：逗号分隔的多个标识符
```bash
pdfget -m "PMC123456,38238491"  # PMCID和PMID混合
```

**支持的标识符类型**：
- **PMCID**：支持带或不带PMC前缀（如"123456"或"PMC123456"）
- **PMID**：6-10位纯数字
- **DOI**：以"10."开头的字符串

**标识符处理流程**：
1. **PMCID**：直接下载
2. **PMID**：自动转换为PMCID后下载（使用NCBI ESummary API）
3. **DOI**：当前版本暂不支持（将在后续版本添加）

**高级用法**：
```bash
# 使用5个并发线程
pdfget -m examples/identifiers.csv -t 5

# 限制只下载前10个
pdfget -m examples/identifiers.csv -l 10
```

**注意事项**：
- PMID会自动转换为PMCID，转换成功率约80-90%（取决于文献是否被PMC收录）
- 无法转换的PMID会被跳过
- DOI支持将在后续版本添加（当前会跳过DOI）
- 列名检测不区分大小写

## 6. 功能实现状态

### 已实现功能 ✅
- [x] PMCID直接下载（100%成功率）
- [x] PMID自动转换为PMCID下载（80-90%成功率）
- [x] 高级检索语法支持
- [x] 并发下载管理
- [x] 智能缓存机制
- [x] 多种输出格式（console/json/markdown）
- [x] 混合标识符输入（PMCID/PMID）
- [x] 批量处理CSV文件
- [x] PMC开放获取统计分析

### 开发中功能 🚧
- [ ] DOI到PMCID转换和下载
  - [ ] Europe PMC API集成（主要数据源，90%成功率）
  - [ ] NCBI E-utilities备用方案（85%成功率）
  - [ ] CrossRef API辅助查询
  - [ ] 批量DOI转换优化（预计100个DOI/30-60秒）
  - [ ] 智能缓存机制（避免重复查询）

### 计划功能 📋
- [ ] 增强DOI转换（更多数据源）
- [ ] 用户认证支持（机构访问）
- [ ] 下载进度持久化
- [ ] GUI界面
- [ ] 插件系统

## 7. 故障排除

### 常见问题

#### PMID转换失败
**问题**：PMID无法转换为PMCID
**可能原因**：
1. 文献未被PMC收录（约10-20%的文献）
2. PMID格式不正确（应为6-10位数字）
3. NCBI API临时限制

**解决方案**：
1. 检查PMID格式：`echo "38238491" | wc -c` 应返回9
2. 使用PMC过滤搜索：`pdfget -s "your query AND pubmed pmc[sb]"`
3. 配置API密钥提高请求限制：`-e your-email@example.com -k your-api-key`

#### 下载速度较慢
**问题**：批量下载耗时较长
**优化建议**：
1. 调整并发线程数：`-t 10`（默认3）
2. 分批处理大量文献：`-l 100` 限制单次数量
3. 使用PMC过滤确保100%可下载：`pubmed pmc[sb]`

#### 网络连接问题
**问题**：API请求超时或失败
**解决方案**：
1. 检查网络连接
2. 配置代理（如需要）
3. 使用Europe PMC数据源：`-S europe_pmc`
4. 重试失败的下载（程序会自动重试）

#### 缓存问题
**问题**：使用了过期的缓存数据
**解决方案**：
```bash
# 清理搜索缓存
rm data/cache/search_*.json

# 清理PDF缓存（如需要）
rm data/pdfs/*.pdf
```

## 8. 许可证

本项目采用 MIT License，允许自由使用和修改。

## 9. 获取帮助

- 🔗 **完整更新日志**: [CHANGELOG.md](CHANGELOG.md)
- 📧 **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)

## 10. 相关链接

- **项目源码**: [GitHub Repository](https://github.com/gqy20/pdfget)
- **问题反馈**: [GitHub Issues](https://github.com/gqy20/pdfget/issues)
- **API文档**:
  - [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
  - [Europe PMC API](https://europepmc.org/RestfulWebService)
  - [Europe PMC XML Service](https://europepmc.org/RestfulWebService#fullTextXML)
