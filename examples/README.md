# PDFGet 示例结果

本目录包含了使用 PDFGet 进行 PMCID 统计的示例结果。

## 示例文件说明

### 1. 基因家族文献统计
- **查询**: `("gene family" OR "transcription factor family") AND ("genome-wide identification" OR "genome-wide analysis")`
- **统计日期**: 2025-12-08
- **结果**: 基于200个样本的统计

## 统计结果摘要

### 基因家族相关文献
- **总文献数**: 4,505篇
- **开放获取比例**: 约79%
- **预估有PMCID**: 约3,558篇
- **预估下载大小**: 约5.3 GB

### CRISPR相关文献
- **总文献数**: 36,608篇
- **开放获取比例**: 40.0%
- **预估有PMCID**: 约14,643篇
- **预估下载大小**: 约60 MB

### COVID-19疫苗相关文献
- **总文献数**: 58,262篇
- **开放获取比例**: 46.0%
- **预估有PMCID**: 约26,800篇
- **预估下载大小**: 约34 MB

## 使用方法

```bash
# 统计PMCID数量（控制台输出）
pdfget -s "query" --count

# 统计并保存为JSON格式
pdfget -s "query" --count --format json

# 统计并保存为Markdown格式
pdfget -s "query" --count --format markdown

# 结合其他参数
pdfget -s "query" -l 500 --count --S pubmed
```

## 注意事项

1. 统计功能需要配合 `-s` 参数使用
2. 统计结果会并行处理，提高效率
3. 自动遵守PubMed API速率限制
4. 建议在统计前了解查询范围
