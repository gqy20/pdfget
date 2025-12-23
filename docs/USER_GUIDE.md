# PDFGet 用户详细文档

本文档提供 PDFGet 的完整使用指南，包括高级检索语法、完整参数说明、输出格式详解等内容。

## 目录

- [高级检索语法](#高级检索语法)
- [完整参数说明](#完整参数说明)
- [输出格式详解](#输出格式详解)
- [混合标识符输入](#混合标识符输入)
- [故障排除](#故障排除)

## 高级检索语法

### 免费全文过滤

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

| 过滤器 | 可下载率 | 说明 |
|--------|----------|------|
| `pubmed pmc[sb]` | 100% | 只返回 PMC 收录文献，**推荐使用** |
| `filter[free full text]` | 30-40% | 包含所有免费全文，部分无法下载 |

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

### 布尔运算符

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

### 字段检索

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

### 短语和精确匹配

```bash
# 短语检索（用双引号）
pdfget -s '"quantum computing"' -l 10

# 混合使用
pdfget -s '"gene expression" AND (cancer OR tumor) NOT review' -l 20
```

### 实用检索技巧

- 使用括号分组复杂的布尔逻辑
- 短语用双引号确保精确匹配
- 可以组合多个字段进行精确检索
- 使用 NOT 过滤掉不相关的结果（如综述、评论等）
- **统计模式**：搜索并显示PMCID统计信息（默认行为）
- **下载模式**：搜索并下载开放获取的PDF（添加 `-d` 参数）

## 完整参数说明

### 核心参数

#### 输入参数（二选一）

**`-s QUERY`** - 搜索文献
```bash
pdfget -s "machine learning cancer" -l 50
```

**`-m INPUT`** - 批量输入，支持三种模式：
- CSV文件路径：`pdfget -m data.csv`
- 单个标识符：`pdfget -m "PMC123456"`
- 逗号分隔列表：`pdfget -m "PMC123,38238491"`

#### 输出控制

**`-c COLUMN`** - CSV列名（默认自动检测：ID>PMCID>doi>pmid>第一列）
```bash
pdfget -m data.csv -c PMCID
pdfget -m data.csv -c ID
```

**`-d`** - 下载PDF（不指定则为统计模式）
```bash
# 统计模式（默认）
pdfget -s "cancer" -l 100

# 下载模式
pdfget -s "cancer" -l 100 -d
```

### 优化参数

**`-l NUM`** - 搜索结果数量（默认200）
```bash
pdfget -s "machine learning" -l 50
```

**`-S SOURCE`** - 数据源选择（pubmed/europe_pmc/both，默认pubmed）
```bash
pdfget -s "cancer" -S europe_pmc -l 30
pdfget -s "cancer" -S both -l 50
```

**`-t NUM`** - 并发线程数（默认3）
```bash
pdfget -m data.csv -d -t 5
```

**`--delay SECONDS`** - 下载延迟时间（秒，默认1.0）
```bash
# 加快下载（适合有API密钥）
pdfget -m data.csv -d --delay 0.3

# 减慢下载（网络不稳定时）
pdfget -m data.csv -d --delay 2.0
```

**`--format FORMAT`** - 统计输出格式（console/json/markdown，默认console）
```bash
pdfget -s "cancer" -l 100 --format json
pdfget -s "cancer" -l 100 --format markdown
```

**`-v`** - 详细输出
```bash
pdfget -s "cancer" -l 100 -v
```

### 输出目录

**`-o DIR`** - 输出目录（默认 data/pdfs）
```bash
pdfget -s "machine learning" -l 50 -d -o ~/papers
```

### NCBI API 配置

**`-e EMAIL`** - NCBI API邮箱（提高请求限制，推荐设置）
```bash
pdfget -s "cancer" -l 100 -e your-email@example.com
```

**`-k KEY`** - NCBI API密钥（推荐，便于监控使用情况）
```bash
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

## 输出格式详解

### 搜索结果格式

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

### 文件目录结构

```
data/
├── pdfs/           # 下载的PDF文件
├── cache/          # 缓存文件
└── search_results.json  # 搜索结果记录
```

### PMCID统计结果

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

## 混合标识符输入

`-m` 参数支持三种输入模式，自动识别：

### 模式1：CSV文件路径

```bash
# 自动检测列名（优先级：ID>PMCID>doi>pmid>第一列）
pdfget -m examples/identifiers.csv

# 手动指定列名
pdfget -m examples/identifiers.csv -c PMCID
pdfget -m examples/identifiers.csv -c ID
```

**示例CSV文件**：
```csv
ID,Title,Journal
PMC123456,Study on AI,Nature
38238491,Deep Learning Review,Science
PMC789012,Machine Learning Methods,Cell
37851234,Neural Network Research,Cell
```

### 模式2：单个标识符

```bash
pdfget -m "PMC123456"              # PMCID
pdfget -m "38238491"                # PMID
pdfget -m "10.1186/s12916-020-01690-4"  # DOI
```

### 模式3：逗号分隔的多个标识符

```bash
pdfget -m "PMC123456,38238491"  # PMCID和PMID混合
pdfget -m "10.1186/s12916-020-01690-4,38238491,PMC123456"  # PMCID/PMID/DOI混合
```

### 支持的标识符类型

- **PMCID**：支持带或不带PMC前缀（如"123456"或"PMC123456"）
- **PMID**：6-10位纯数字
- **DOI**：以"10."开头的字符串

### 标识符处理流程

1. **PMCID**：直接下载
2. **PMID**：自动转换为PMCID后下载（使用NCBI ESummary API）
3. **DOI**：自动转换为PMCID后下载（使用Europe PMC API，支持CrossRef备选）

### 高级用法

```bash
# 使用5个并发线程
pdfget -m examples/identifiers.csv -t 5

# 限制只下载前10个
pdfget -m examples/identifiers.csv -l 10

# 调整延迟加快下载（适合有API密钥的情况）
pdfget -m examples/identifiers.csv -t 5 --delay 0.3

# 增加延迟提高稳定性（适合网络不稳定）
pdfget -m examples/identifiers.csv --delay 2.0
```

### 注意事项

- PMID会自动转换为PMCID，转换成功率约80-90%（取决于文献是否被PMC收录）
- DOI会自动转换为PMCID，转换成功率约60-80%（取决于文献是否被PMC收录）
- 无法转换的PMID/DOI会被跳过，不会影响其他标识符的下载
- 列名检测不区分大小写

## 故障排除

### PMID转换失败

**问题**：PMID无法转换为PMCID

**可能原因**：
1. 文献未被PMC收录（约10-20%的文献）
2. PMID格式不正确（应为6-10位数字）
3. NCBI API临时限制

**解决方案**：
```bash
# 1. 检查PMID格式
echo "38238491" | wc -c  # 应返回9

# 2. 使用PMC过滤搜索
pdfget -s "your query AND pubmed pmc[sb]"

# 3. 配置API密钥提高请求限制
pdfget -s "cancer" -l 100 -e your-email@example.com -k your-api-key
```

### 下载速度较慢

**问题**：批量下载耗时较长

**优化建议**：
1. 调整并发线程数：`-t 10`（默认3）
2. 调整下载延迟：`--delay 0.5` 减少延迟加快下载（默认1.0秒）
3. 分批处理大量文献：`-l 100` 限制单次数量
4. 使用PMC过滤确保100%可下载：`pubmed pmc[sb]`

**延迟参数说明**：
- 默认延迟1.0秒，适合遵守API速率限制
- 有NCBI API密钥可降低延迟：`--delay 0.3`（3请求/秒→10请求/秒）
- 网络不稳定时可增加延迟：`--delay 2.0`

### 网络连接问题

**问题**：API请求超时或失败

**解决方案**：
1. 检查网络连接
2. 配置代理（如需要）
3. 使用Europe PMC数据源：`-S europe_pmc`
4. 重试失败的下载（程序会自动重试）

### 缓存问题

**问题**：使用了过期的缓存数据

**解决方案**：
```bash
# 清理搜索缓存
rm data/cache/search_*.json

# 清理PDF缓存（如需要）
rm data/pdfs/*.pdf
```

### 文件名显示 unknown

**现象**：下载的PDF文件名如 `PMC123456_unknown.pdf`

**说明**：这是正常现象，CSV文件中只有PMCID，没有DOI信息。工具会直接使用PMCID作为文件名。

**文件命名规则**：
- 有DOI：`PMCID_DOI.pdf`（例如：`PMC123456_101000test.pdf`）
- 无DOI：`PMCID.pdf`（例如：`PMC123456.pdf`）

PDF文件完全正常，可以正常使用。

## 功能实现状态

### 已实现功能 ✅
- [x] PMCID直接下载（100%成功率）
- [x] PMID自动转换为PMCID下载（80-90%成功率）
- [x] DOI自动转换为PMCID下载（60-80%成功率）
- [x] 高级检索语法支持
- [x] 并发下载管理
- [x] 智能缓存机制
- [x] 多种输出格式（console/json/markdown）
- [x] 混合标识符输入（PMCID/PMID/DOI）
- [x] 批量处理CSV文件
- [x] PMC开放获取统计分析
- [x] Europe PMC API集成（主要数据源）
- [x] CrossRef API辅助查询
- [x] 批量DOI转换优化（100个DOI/30-60秒）
- [x] 可配置下载延迟参数

### 计划功能 📋
- [ ] 增强DOI转换（更多数据源）
- [ ] 用户认证支持（机构访问）
- [ ] 下载进度持久化
- [ ] GUI界面
- [ ] 插件系统

## API文档

- **NCBI E-utilities**: https://www.ncbi.nlm.nih.gov/books/NBK25501/
- **Europe PMC API**: https://europepmc.org/RestfulWebService
- **Europe PMC XML Service**: https://europepmc.org/RestfulWebService#fullTextXML
