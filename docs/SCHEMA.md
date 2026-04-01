# PDFGet Schema Guide

本文档描述 PDFGet 面向程序和智能体消费的结构化输出协议。

当前稳定版本：

- 搜索结果：`paper_record.v1`
- 下载结果：`download_result.v1`

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

单条下载结果常见字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | bool | 是否成功 |
| `path` | string | 本地文件路径 |
| `error` | string | 失败原因 |
| `pmcid` | string | 关联 PMCID |
| `doi` | string | 关联 DOI |
| `arxiv_id` | string | 关联 arXiv ID |

## 兼容性约定

- 新增字段应尽量保持向后兼容
- 已存在字段的语义不应在同一 schema 版本内改变
- 如需破坏性调整，应提升 schema 版本，例如 `paper_record.v2`
