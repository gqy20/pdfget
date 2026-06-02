# PDFGet Schema Guide

本文档描述 PDFGet 面向程序和智能体消费的结构化输出协议。

当前稳定版本：

- 搜索结果：`paper_record.v1`
- 下载计划：`download_plan.v1`
- 下载结果：`download_result.v1`
- 运行报告：`run_summary.v1`

## paper_record.v1

`paper_record.v1` 是单条论文记录的标准化结构。搜索结果中的 `results` 数组由该结构组成。

核心字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 当前记录来源，例如 `pubmed` / `europe_pmc` / `arxiv` |
| `raw_source` | string | 原始来源标记，通常与 `source` 一致 |
| `raw_id` | string | 源站原始主标识 |
| `title` | string | 标题 |
| `authors` | string[] | 作者列表 |
| `year` | string | 标准化年份，格式通常为 `YYYY` |
| `published_at` | string | 发布时间字段，当前至少保证可回退到年份 |
| `abstract` | string | 摘要 |
| `journal` | string | 期刊名 |
| `repository` | string | 仓库/平台名，例如 `arXiv` |
| `pmid` | string | PubMed ID |
| `pmcid` | string | PubMed Central ID |
| `doi` | string | DOI |
| `arxiv_id` | string | arXiv ID |
| `pdf_url` | string | 源记录中直接提供的 PDF URL |
| `download_url` | string | 标准化后的推荐下载 URL |
| `download_type` | string | 下载类型，例如 `pmc` / `arxiv` / `pdf` |
| `identifier` | string | 推荐主标识 |
| `identifier_type` | string | 推荐主标识类型，可能为 `pmcid` / `doi` / `arxiv` / `pmid` |
| `is_downloadable` | bool | 是否可直接进入下载流程 |
| `matched_by` | string | 记录是通过哪种标识符构造或命中的 |
| `inPMC` | string | Europe PMC 提供的 PMC 收录标记 |

标识符优先级：

1. `pmcid`
2. `doi`
3. `arxiv_id`
4. `pmid`

## 搜索 JSON 输出

当搜索模式使用 `--format json` 时，stdout 和保存文件都会输出如下结构：

```json
{
  "schema": "paper_record.v1",
  "query": "transformer",
  "timestamp": 1775012150.0,
  "total": 1,
  "results": [
    {
      "source": "arxiv",
      "identifier": "2401.00001",
      "identifier_type": "arxiv",
      "arxiv_id": "2401.00001",
      "is_downloadable": true
    }
  ]
}
```

说明：

- stdout 输出与 `search_results_*.json` 落盘内容使用同一 payload 结构
- `schema` 字段用于让上层智能体或脚本显式识别协议版本

## download_plan.v1

下载计划是搜索、直接输入、失败续跑和下载器之间的统一中间协议。它决定哪些论文进入下载器，哪些被跳过，以及跳过原因。

每次下载或 `--dry-run` 都会在输出目录保存下载计划：

- `download_plan.json`：最近一次下载计划
- `download_plan_YYYYMMDD_HHMMSS.json`：同一内容的归档副本

顶层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema` | string | 固定为 `download_plan.v1` |
| `source` | string | 计划来源，例如 `search` / `unified_input` / `resume` |
| `total` | number | 输入条目总数 |
| `ready` | number | 可进入下载器的条目数 |
| `skipped` | number | 被跳过的条目数 |
| `entries` | object[] | 单条计划条目 |

单条 `entries[]` 条目：

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | number | 原始输入顺序 |
| `status` | string | `ready` 或 `skipped` |
| `strategy` | string | 下载策略：`pmc` / `arxiv` / `direct_pdf` |
| `identifier` | string | 推荐主标识 |
| `identifier_type` | string | 主标识类型 |
| `download_url` | string | 推荐下载 URL |
| `skip_reason` | string | 跳过原因，当前为 `duplicate` / `no_download_route` / 空字符串 |
| `duplicate_of` | number | 重复项指向的保留条目 index；非重复时为 `null` |
| `dedupe_key` | string | 去重键 |
| `merged_sources` | string[] | 被合并到保留条目的来源列表 |
| `source` | string | 计划来源 |
| `paper` | object | 标准化论文记录，遵循 `paper_record.v1` |

去重优先级：

1. `pmcid`
2. `doi`
3. `arxiv_id`
4. `pmid`
5. 标准化标题

默认行为：

- 第一个可下载条目保留为 `ready`
- 后续重复条目标记为 `skipped`，`skip_reason=duplicate`
- 重复来源会合并到保留条目的 `merged_sources`
- 缺少 `pmcid`、`arxiv_id` 和 `pdf_url` 的条目标记为 `skipped`，`skip_reason=no_download_route`

## download_result.v1

下载结果 payload 使用 `download_result.v1`。

顶层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema` | string | 固定为 `download_result.v1` |
| `timestamp` | number | 生成时间戳 |
| `source` | string | 下载来源入口，例如 `search` / `unified_input` |
| `input_value` | string | 当来源为统一输入时，保留原始输入 |
| `total` | number | 结果总数 |
| `success` | number | 成功数 |
| `results` | object[] | 单条下载结果列表 |

当下载模式使用 `--format json` 时：

- stdout 会输出 `download_result.v1`
- `download_results.json` 会保存同一 payload 结构

单条下载结果常见字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `path` | string | 本地文件路径 |
| `error` | string | 失败原因 |
| `stage` | string | 失败阶段，成功时可能为空 |
| `pmcid` | string | 关联 PMCID |
| `doi` | string | 关联 DOI |
| `arxiv_id` | string | 关联 arXiv ID |

## run_summary.v1

每次下载都会在输出目录保存运行报告：

- `run_summary.json`：最近一次下载运行报告
- `run_summary_YYYYMMDD_HHMMSS.json`：同一内容的归档副本

报告用于人工排查，也用于 `--resume` 重试失败项。

顶层字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema` | string | 固定为 `run_summary.v1` |
| `timestamp` | number | 生成时间戳 |
| `source` | string | 下载入口，例如 `search` / `unified_input` / `resume` |
| `output_dir` | string | 本次运行输出目录 |
| `input_value` | string | 原始搜索词、统一输入值或报告路径 |
| `previous_report` | string | 当 `source=resume` 时，记录被重试的报告路径 |
| `download_plan_path` | string | 本次运行对应的 `download_plan.json` 路径 |
| `total` | number | 条目总数 |
| `success` | number | 成功条目数 |
| `failed` | number | 失败条目数 |
| `results` | object[] | 单条运行条目 |

单条 `results[]` 条目：

| 字段 | 类型 | 说明 |
|------|------|------|
| `index` | number | 本次运行中的顺序 |
| `status` | string | `success` 或 `failed` |
| `stage` | string | 失败阶段，成功时可能为空 |
| `identifier` | string | 推荐主标识 |
| `identifier_type` | string | 主标识类型 |
| `paper` | object | 可重试的标准化论文记录，遵循 `paper_record.v1` |
| `result` | object | 原始下载结果，遵循 `download_result.v1` 单条结果约定 |
| `path` | string | 本地文件路径 |
| `error` | string | 失败原因 |

标准失败阶段：

| 阶段 | 说明 |
|------|------|
| `resolve_identifier` | 输入记录缺少可下载标识符或 URL |
| `download_pdf` | 下载请求失败、超时或所有下载源失败 |
| `validate_response` | 下载响应不是 PDF 等内容校验失败 |
| `save_file` | PDF 文件保存失败或响应体为空 |
| `worker_error` | 并发 worker 执行时捕获到未预期异常 |

`--resume` 行为：

- 只读取 `run_summary.v1` 中 `status=failed` 的条目
- 优先使用条目中的 `paper` 字段重试
- 不可下载的失败项会被跳过
- 新运行会生成新的 `run_summary.v1`，并在 `previous_report` 中记录来源报告

## 兼容性约定

- 新增字段应尽量保持向后兼容
- 已存在字段的语义不应在同一 schema 版本内改变
- 如需破坏性调整，应提升 schema 版本，例如 `paper_record.v2`
