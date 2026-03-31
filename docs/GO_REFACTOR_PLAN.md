# Go 重构评估与设计草案

## 1. 背景

当前 `pdfget` 是一个以命令行为入口的文献检索与 PDF 批量下载工具，核心能力集中在以下几类流程：

1. 检索：PubMed、Europe PMC、多源合并。
2. 标识符处理：PMCID、PMID、DOI 检测、标准化、转换。
3. 下载：PMC OA Service 优先，失败后回退到其他下载源。
4. 缓存：搜索结果和 PDF 文件缓存。
5. 统计与格式化：结果分析、输出展示、导出。

当前代码结构已经比较清晰，核心模块主要包括：

- `src/pdfget/fetcher.py`
- `src/pdfget/searcher.py`
- `src/pdfget/downloader.py`
- `src/pdfget/manager.py`
- `src/pdfget/pmcid.py`
- `src/pdfget/doi_converter.py`
- `src/pdfget/counter.py`
- `src/pdfget/formatter.py`
- `src/pdfget/utils/cache_manager.py`

从架构形态看，这个项目本质上是“CLI + 多外部 API 编排 + 并发下载 + 本地缓存”的工具型项目，和 Go 的能力模型是匹配的。

## 2. 是否值得用 Go 重构

结论：适合做 Go 版本，但不建议直接全量推倒重写，建议采用渐进式重构或并行实现 Go 版本。

### 2.1 适合 Go 的原因

1. 项目是典型的 I/O 密集型 CLI 工具。
2. 并发下载、批量任务、超时控制、取消控制都很适合 Go。
3. 单二进制分发对最终用户更友好，尤其是没有 Python 环境的用户。
4. 类型约束能显著减少当前 `dict[str, Any]` 带来的边界模糊问题。
5. 模块职责天然可以映射为 provider、service、worker、cache 等 Go 包。

### 2.2 暂不建议一次性重写的原因

1. 当前 Python 依赖很轻，维护成本并不高。
2. 业务复杂度主要来自外部 API 细节，而不是语言本身。
3. 现有测试已经覆盖了大量核心逻辑，重写意味着同时重建测试体系。
4. 一次性迁移容易在边角行为上出现不兼容，尤其是标识符处理、CSV 自动识别、下载回退和缓存策略。

## 3. 当前项目规模

基于仓库现状的粗略统计：

- Python 源码：约 `4255` 行
- Python 测试：约 `3461` 行

较大的核心文件包括：

- `src/pdfget/fetcher.py`
- `src/pdfget/searcher.py`
- `src/pdfget/counter.py`
- `src/pdfget/downloader.py`
- `src/pdfget/pmcid.py`
- `src/pdfget/main.py`
- `src/pdfget/doi_converter.py`

这说明当前项目已经不是一个很小的脚本，而是一个中等规模的 CLI 应用。

## 4. Go 重构的预期收益

### 4.1 工程收益

1. 发布更简单：可直接提供 Windows、macOS、Linux 单文件二进制。
2. 部署更简单：不再要求 Python 3.12 环境。
3. 并发更自然：worker pool、channel、context 会比线程池和共享状态更清晰。
4. 类型更清晰：统一的 `Paper`、`DownloadTask`、`DownloadResult` 等结构体可减少字段不一致。
5. 基础设施更统一：重试、限流、超时控制更容易下沉到通用层。

### 4.2 用户收益

1. 安装门槛更低。
2. 大批量下载时更稳定。
3. 命令行工具启动更快。
4. 更容易做跨平台发布与后续集成。

## 5. Go 重构的主要风险

1. 开发初期速度会变慢。
2. 类型、错误处理、接口定义会引入更多样板代码。
3. 迁移期功能对齐成本高。
4. 如果目标仅仅是“代码更优雅”，收益不足以覆盖重写成本。

重点风险点：

1. PubMed / Europe PMC 查询字段兼容性。
2. PMID / DOI 转 PMCID 的回退策略。
3. PMC OA Service 的下载与 PDF 提取细节。
4. CSV 列自动识别和混合输入兼容。
5. 现有缓存命名与过期逻辑迁移。

## 6. 重构目标建议

建议把 Go 版本先定义为“功能对齐的 CLI 工具”，优先保证以下能力：

1. 搜索：支持 `pubmed`、`europe_pmc`、`both`。
2. 下载：支持 PMCID 优先下载与并发批量下载。
3. 输入：支持单个标识符、逗号分隔标识符、CSV 输入。
4. 转换：支持 PMCID、PMID、DOI 混合输入的处理。
5. 缓存：支持搜索结果缓存和 PDF 文件缓存。
6. 输出：支持基本 console 输出和 JSON 导出。

不建议第一阶段就追求所有现有边角行为完全复刻，先优先主链路。

## 7. Python 到 Go 的模块映射

Go 版本不建议直接按照 Python 文件一比一翻译，而应按更适合 Go 的边界进行拆分。

建议目录结构如下：

```text
pdfget-go/
  cmd/pdfget/
    main.go

  internal/app/
    app.go
    run_search.go
    run_download.go
    run_count.go

  internal/model/
    paper.go
    identifier.go
    result.go
    options.go

  internal/config/
    config.go

  internal/cli/
    root.go
    search.go
    download.go
    count.go

  internal/provider/pubmed/
    client.go
    search.go
    summary.go

  internal/provider/europepmc/
    client.go
    search.go

  internal/provider/pmcoa/
    client.go
    download.go

  internal/identifier/
    detect.go
    normalize.go
    convert.go
    csv_input.go

  internal/search/
    service.go
    merge.go
    query_parser.go

  internal/download/
    service.go
    manager.go
    worker.go
    filename.go

  internal/cache/
    file_cache.go

  internal/httpx/
    client.go
    retry.go
    ratelimit.go

  internal/output/
    formatter.go
    json.go
    table.go
    markdown.go

  internal/logx/
    logger.go
```

### 7.1 入口与 CLI

Python：

- `src/pdfget/main.py`
- `src/pdfget/__main__.py`

Go：

- `cmd/pdfget/main.go`
- `internal/cli/*`
- `internal/app/*`

建议：

1. `cli` 负责参数定义和命令组织。
2. `app` 负责调用各 service 并完成流程编排。
3. 避免把业务逻辑直接堆在 `main.go` 中。

### 7.2 总协调器

Python：

- `src/pdfget/fetcher.py`

Go：

- `internal/app/app.go`
- `internal/search/service.go`
- `internal/download/service.go`
- `internal/identifier/convert.go`

建议：

1. 不保留一个过大的 `Fetcher` 类。
2. 用 `app` 层统一编排 `search`、`identifier`、`download`、`output`。
3. 业务能力拆分成多个独立 service，降低耦合。

### 7.3 搜索

Python：

- `src/pdfget/searcher.py`

Go：

- `internal/search/service.go`
- `internal/search/query_parser.go`
- `internal/search/merge.go`
- `internal/provider/pubmed/*`
- `internal/provider/europepmc/*`

建议：

1. provider 负责 API 请求与响应解析。
2. `search.Service` 负责 source 分发、查询转换、结果去重和统一输出。
3. 所有 provider 输出统一转换为 `model.Paper`。

### 7.4 下载

Python：

- `src/pdfget/downloader.py`
- `src/pdfget/manager.py`
- `src/pdfget/pmc_oa_service.py`

Go：

- `internal/download/service.go`
- `internal/download/manager.go`
- `internal/download/worker.go`
- `internal/download/filename.go`
- `internal/provider/pmcoa/*`

建议：

1. `download.Service` 负责单篇下载逻辑。
2. `download.Manager` 负责批量调度与结果汇总。
3. `provider/pmcoa` 负责 PMC OA 的特定下载逻辑。
4. 文件命名逻辑单独收口，避免分散。

### 7.5 标识符处理

Python：

- `src/pdfget/pmcid.py`
- `src/pdfget/doi_converter.py`
- `src/pdfget/fetcher.py` 中的 CSV / 混合输入处理
- `src/pdfget/utils/identifier_utils.py`

Go：

- `internal/identifier/detect.go`
- `internal/identifier/normalize.go`
- `internal/identifier/convert.go`
- `internal/identifier/csv_input.go`

建议：

1. 单独建设标识符层。
2. 把检测、标准化、转换、CSV 输入解析拆开。
3. 让下载和搜索都复用同一套标识符逻辑。

### 7.6 缓存

Python：

- `src/pdfget/utils/cache_manager.py`

Go：

- `internal/cache/file_cache.go`

建议：

1. 第一阶段继续使用文件缓存即可。
2. 保持 key 到文件名的映射和 TTL 语义清晰。
3. 后续若有性能诉求，再替换为 BoltDB 或 SQLite。

### 7.7 HTTP、重试、限流

Python：

- `src/pdfget/base/ncbi_base.py`
- `src/pdfget/retry.py`
- 以及相关 utils

Go：

- `internal/httpx/client.go`
- `internal/httpx/retry.go`
- `internal/httpx/ratelimit.go`

建议：

1. HTTP client 统一封装。
2. 重试逻辑不要分散在 provider 内部。
3. 限流器要支持按数据源区分。
4. 所有 provider 都复用统一基础设施。

### 7.8 输出与统计

Python：

- `src/pdfget/formatter.py`
- `src/pdfget/counter.py`

Go：

- `internal/output/*`
- 或拆出 `internal/analysis/*`

建议：

1. 格式化只负责渲染。
2. 统计逻辑和输出逻辑分开。
3. 先保留 console 与 JSON，其他格式后补。

## 8. 建议的核心数据结构

Go 重构最值得优先稳定的是数据模型层。建议至少定义以下结构：

```go
type Paper struct {
    PMID     string
    PMCID    string
    DOI      string
    Title    string
    Authors  []string
    Journal  string
    Year     string
    Abstract string
    Source   string
    InPMC    string
}

type Identifier struct {
    Raw        string
    Type       IdentifierType
    Normalized string
}

type SearchOptions struct {
    Query        string
    Limit        int
    Source       string
    FetchPMCID   bool
    UseCache     bool
    RequirePMCID bool
}

type DownloadTask struct {
    PMID   string
    PMCID  string
    DOI    string
    Title  string
    Source string
}

type DownloadResult struct {
    PMID          string
    PMCID         string
    DOI           string
    Success       bool
    Path          string
    Source        string
    Error         string
    ContentLength int64
}
```

这些结构体能直接替代当前大量松散的字典结构。

## 9. 代码量预估

### 9.1 Go 源码量

按“功能基本对齐”的目标估算：

- MVP：`2500 - 4000` 行 Go 代码
- 完整版：`4500 - 7000` 行 Go 代码

### 9.2 Go 测试代码量

- MVP 测试：`1200 - 2200` 行
- 完整测试：`2500 - 4500` 行

### 9.3 为什么 Go 往往不会更短

1. 结构体定义会增多。
2. 错误处理更显式。
3. provider、service、cache、worker 的分层更明确。
4. 测试通常要写 fake client、stub provider、`httptest` server。

因此，Go 版本的总行数大概率不会明显低于 Python，甚至会略高，但可维护性通常会更好。

## 10. 分阶段实施建议

建议采用“并行实现新版本”的方式，而不是在现有 Python 项目上直接硬切换。

### 阶段 1：基础设施

目标：

1. 初始化 Go 项目。
2. 建立 `model`、`config`、`httpx`、`logx`。
3. 跑通最基本的 CLI 骨架。

阶段产出：

1. 可执行的 `pdfget-go` 命令。
2. 统一的数据模型。
3. HTTP 客户端、重试、限流骨架。

### 阶段 2：搜索链路

目标：

1. 实现 PubMed 搜索。
2. 实现 Europe PMC 搜索。
3. 支持 `source=both` 合并去重。

阶段产出：

1. `pdfget-go search` 可用。
2. 基本检索功能可独立验证。

### 阶段 3：标识符与输入处理

目标：

1. 实现 PMCID / PMID / DOI 检测与标准化。
2. 实现 PMID -> PMCID 和 DOI -> PMCID 转换。
3. 实现 CSV 输入与列自动识别。

阶段产出：

1. 可以用统一入口处理单个、多值、CSV 输入。

### 阶段 4：下载链路

目标：

1. 实现 PMC OA Service 下载。
2. 实现回退下载源。
3. 实现并发下载 manager。

阶段产出：

1. `pdfget-go download` 主链路可用。
2. 支持批量并发下载。

### 阶段 5：缓存、输出与统计

目标：

1. 搜索缓存。
2. PDF 存在性检查与缓存语义。
3. 基本统计与格式化输出。

阶段产出：

1. Go 版本具备接近当前 Python 主版本的用户体验。

## 11. 推荐迁移策略

建议优先采用以下策略：

1. Python 保持维护，Go 版本作为并行实现。
2. 先做 MVP，不追求首版完全替代。
3. 以“用户主链路可用”为验收标准，而不是以“所有边角行为全部一致”为验收标准。
4. 每完成一条主链路，就拿现有 Python 版本做行为对照。

不建议：

1. 直接在当前 Python 仓库中把源码逐文件改写为 Go。
2. 第一阶段就试图完整复刻所有细节行为。
3. 没有测试对照就开始迁移下载逻辑和转换逻辑。

## 12. 最终判断

从项目类型、未来维护性和发布体验来看，`pdfget` 很适合有一个 Go 版本。

但从当前工程状态、业务复杂度和测试资产来看，更合理的路线是：

1. 先写一版 Go MVP。
2. 优先覆盖搜索、标识符处理、并发下载三条主链路。
3. 逐步对齐缓存、统计、输出格式等细节。
4. 最终再决定是替换 Python 主版本，还是双版本并存。

如果后续准备真正启动 Go 版本开发，下一份最有价值的文档应该是：

1. Go 版本的包职责与接口草案。
2. MVP 开发清单与里程碑。
3. 关键测试对照表。
