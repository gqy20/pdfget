#!/usr/bin/env python3
"""Command line entry point for pdfget."""

import argparse
import json
import logging
import time
from pathlib import Path

from .config import (
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SOURCE,
    DOWNLOAD_BASE_DELAY,
    NCBI_API_KEY,
    NCBI_EMAIL,
    TIMEOUT,
)
from .counter import PMCIDCounter
from .fetcher import PaperFetcher
from .formatter import StatsFormatter
from .logger import get_main_logger
from .manager import UnifiedDownloadManager


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="PDF文献下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 统计 PubMed / Europe PMC 文献的 PMCID 情况
  python -m pdfget -s "machine learning cancer" -l 5000

  # 搜索 arXiv 文献
  python -m pdfget -s "graph neural networks" -S arxiv -l 20

  # 搜索并下载前 N 篇文献
  python -m pdfget -s "deep learning" -l 20 -d
  python -m pdfget -s "vision transformer" -S arxiv -l 20 -d

  # 并发下载（多线程）
  python -m pdfget -s "cancer immunotherapy" -l 20 -d -t 5

  # 从 CSV 下载混合标识符（支持 PMCID/PMID/DOI/arXiv ID 混合）
  python -m pdfget -m identifiers.csv -t 5
  python -m pdfget -m pmcids.csv -c PMCID -l 100

  # 下载单个标识符
  python -m pdfget -m "PMC10851947"
  python -m pdfget -m "10.1016/j.cell.2020.01.021"
  python -m pdfget -m "2301.12345"

  # 下载多个标识符（逗号分隔）
  python -m pdfget -m "PMC123456,38238491,10.1038/xxx,2301.12345" -t 3
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", help="搜索文献")
    group.add_argument(
        "-m",
        help="批量输入（CSV文件/单个标识符/逗号分隔列表），支持混合 PMCID/PMID/DOI/arXiv ID",
    )

    parser.add_argument(
        "-c",
        help="CSV 列名（默认自动检测: ID > PMCID > doi > pmid > 第一列）",
    )
    parser.add_argument("-o", default="data/pdfs", help="输出目录")
    parser.add_argument(
        "-l", type=int, default=DEFAULT_SEARCH_LIMIT, help="要处理的文献数量"
    )
    parser.add_argument("-d", action="store_true", help="下载 PDF")
    parser.add_argument("-t", type=int, default=3, help="并发线程数（默认 3）")
    parser.add_argument("-v", action="store_true", help="详细输出")
    parser.add_argument(
        "-S",
        choices=["pubmed", "europe_pmc", "arxiv", "both", "all"],
        default=DEFAULT_SOURCE,
        help=f"数据源（默认: {DEFAULT_SOURCE}）",
    )
    parser.add_argument(
        "--format",
        choices=["console", "json", "markdown"],
        help="统计输出格式",
    )
    parser.add_argument("-e", help="NCBI API 邮箱（提高请求限制）")
    parser.add_argument("-k", help="NCBI API 密钥（可选）")
    parser.add_argument("--delay", type=float, help="下载延迟时间（秒，默认 1.0）")
    return parser


def log_download_stats(logger, results: list[dict]) -> dict:
    """Log download statistics and return the summary."""
    success_count = sum(1 for r in results if r.get("success"))
    pdf_count = sum(1 for r in results if r.get("path"))
    html_count = sum(1 for r in results if r.get("full_text_url"))

    logger.info("\n下载统计:")
    logger.info(f"   总计: {len(results)}")
    logger.info(f"   成功: {success_count}")
    logger.info(f"   PDF: {pdf_count}")
    logger.info(f"   HTML: {html_count}")
    logger.info(f"   失败: {len(results) - success_count}")

    return {
        "total": len(results),
        "success_count": success_count,
        "pdf_count": pdf_count,
        "html_count": html_count,
    }


def save_json(path: Path, payload: dict) -> None:
    """Persist JSON output, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def build_search_payload(query: str, papers: list[dict]) -> dict:
    """Build a schema-first payload for search output."""
    return {
        "schema": "paper_record.v1",
        "query": query,
        "timestamp": time.time(),
        "total": len(papers),
        "results": papers,
    }


def build_download_payload(
    results: list[dict], *, source: str, input_value: str | None = None
) -> dict:
    """Build a schema-first payload for download output."""
    success_count = sum(1 for result in results if result.get("success"))
    payload = {
        "schema": "download_result.v1",
        "timestamp": time.time(),
        "source": source,
        "total": len(results),
        "success": success_count,
        "results": results,
    }
    if input_value is not None:
        payload["input_value"] = input_value
    return payload


def is_downloadable(paper: dict) -> bool:
    """Whether the paper has a direct download route."""
    return bool(paper.get("pmcid") or paper.get("arxiv_id") or paper.get("pdf_url"))


def get_primary_identifier_display(paper: dict) -> tuple[str, str]:
    """Return the most user-friendly identifier label/value pair."""
    identifier = str(paper.get("identifier") or "")
    identifier_type = str(paper.get("identifier_type") or "")

    if identifier and identifier_type == "pmcid":
        return "PMCID", identifier
    if identifier and identifier_type == "arxiv":
        return "arXiv", identifier
    if identifier and identifier_type == "doi":
        return "DOI", identifier
    if identifier and identifier_type == "pmid":
        return "PMID", identifier

    if paper.get("pmcid"):
        return "PMCID", str(paper["pmcid"])
    if paper.get("arxiv_id"):
        return "arXiv", str(paper["arxiv_id"])
    if paper.get("doi"):
        return "DOI", str(paper["doi"])
    if paper.get("pmid"):
        return "PMID", str(paper["pmid"])

    return "", ""


def display_search_results(logger, papers: list[dict]) -> None:
    """Render a compact search result list to the logger."""
    logger.info(f"\n搜索结果 ({len(papers)} 篇):")
    for index, paper in enumerate(papers, 1):
        authors = paper.get("authors") or []
        author_text = ", ".join(authors[:3])
        if len(authors) > 3:
            author_text += "..."

        venue = (
            paper.get("journal")
            or paper.get("repository")
            or paper.get("source")
            or "Unknown"
        )
        year = paper.get("year") or "Unknown"

        logger.info(f"\n{index}. {paper.get('title', 'Untitled')}")
        if author_text:
            logger.info(f"   作者: {author_text}")
        logger.info(f"   来源: {venue} ({year})")
        identifier_label, identifier_value = get_primary_identifier_display(paper)
        if identifier_label and identifier_value:
            logger.info(f"   {identifier_label}: {identifier_value}")
        if paper.get("doi") and identifier_label != "DOI":
            logger.info(f"   DOI: {paper['doi']}")
        if paper.get("pmcid") and identifier_label != "PMCID":
            logger.info(f"   PMCID: {paper['pmcid']}")
        if paper.get("arxiv_id") and identifier_label != "arXiv":
            logger.info(f"   arXiv: {paper['arxiv_id']}")
        logger.info(f"   可下载: {'是' if is_downloadable(paper) else '否'}")


def save_search_results(output_dir: str, query: str, papers: list[dict]) -> Path:
    """Save search results to a timestamped JSON file."""
    path = Path(output_dir) / f"search_results_{int(time.time())}.json"
    save_json(path, build_search_payload(query, papers))
    return path


def emit_search_results(
    logger, query: str, papers: list[dict], output_dir: str, output_format: str | None
) -> Path:
    """Render search results for humans and save a schema-first payload."""
    if output_format == "json":
        print(json.dumps(build_search_payload(query, papers), ensure_ascii=False, indent=2))
    else:
        display_search_results(logger, papers)

    search_results_file = save_search_results(output_dir, query, papers)
    logger.info(f"\n搜索结果已保存到: {search_results_file}")
    return search_results_file


def emit_download_results(
    logger,
    results: list[dict],
    output_dir: str,
    output_format: str | None,
    *,
    source: str,
    input_value: str | None = None,
) -> Path:
    """Render download results for machines and save a schema-first payload."""
    payload = build_download_payload(results, source=source, input_value=input_value)
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    download_results_file = Path(output_dir) / "download_results.json"
    save_json(download_results_file, payload)
    logger.info(f"\n下载结果已保存到: {download_results_file}")
    return download_results_file


def print_pmcid_stats(stats: dict) -> None:
    """Print PMCID statistics in console mode."""
    print("\nPMCID统计结果:")
    print(f"   查询: {stats['query']}")
    print(f"   总文献数: {stats['total']:,} 篇")
    print(f"   检查了: {stats['checked']:,} 篇 (由 -l 参数指定)")
    print(f"   其中有 PMCID: {stats['with_pmcid']:,} 篇 ({stats['rate']:.1f}%)")
    print(f"   无 PMCID: {stats['without_pmcid']:,} 篇")
    print(f"   耗时: {stats['elapsed_seconds']:.1f} 秒")
    if stats["elapsed_seconds"] > 0:
        speed = stats["checked"] / stats["elapsed_seconds"]
        print(f"   处理速度: {speed:.1f} 篇/秒")
    else:
        print("   处理速度: N/A (使用缓存)")

    if stats["with_pmcid"] > 0:
        print("\n如果下载所有开放获取文献:")
        print(f"   文件数量: {stats['with_pmcid']:,} 个 PDF")
        size_mb = stats["estimated_size_mb"]
        size_gb = size_mb / 1024
        print(f"   估算大小: {size_mb:.1f} MB ({size_gb:.2f} GB)")

    if stats["checked"] < stats["total"]:
        print(f"\n说明: 仅检查了前 {stats['checked']:,} 篇文献的 PMCID 状态")


def main() -> None:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    logger = get_main_logger()
    if args.v:
        logger.setLevel(logging.DEBUG)

    fetcher = PaperFetcher(cache_dir="data/cache", output_dir=args.o, default_source=args.S)

    logger.info("PDF 下载器启动")
    logger.info(f"   输出目录: {args.o}")

    try:
        if args.s:
            logger.info(f"\n搜索文献: {args.s} (数据源: {args.S})")

            if args.d:
                fetch_pmcid = args.S == "pubmed"
                papers = fetcher.search_papers(
                    args.s, limit=args.l, source=args.S, fetch_pmcid=fetch_pmcid
                )

                if not papers:
                    logger.error("未找到匹配的文献")
                    raise SystemExit(1)

                emit_search_results(logger, args.s, papers, args.o, args.format)

                downloadable_papers = [paper for paper in papers if is_downloadable(paper)]
                logger.info(f"\n开始下载 PDF，找到 {len(downloadable_papers)} 篇可下载文献")

                if downloadable_papers:
                    download_manager = UnifiedDownloadManager(
                        fetcher=fetcher,
                        max_workers=args.t,
                        base_delay=(
                            args.delay if args.delay is not None else DOWNLOAD_BASE_DELAY
                        ),
                    )
                    results = download_manager.download_batch(
                        downloadable_papers, timeout=TIMEOUT
                    )
                    stats = log_download_stats(logger, results)

                    if stats["success_count"] > 0:
                        emit_download_results(
                            logger,
                            results,
                            args.o,
                            args.format,
                            source="search",
                        )
            else:
                if args.S == "arxiv":
                    papers = fetcher.search_papers(args.s, limit=args.l, source=args.S)
                    if not papers:
                        logger.error("未找到匹配的文献")
                        raise SystemExit(1)

                    emit_search_results(logger, args.s, papers, args.o, args.format)
                    return

                email = args.e or NCBI_EMAIL
                api_key = args.k or NCBI_API_KEY
                counter = PMCIDCounter(email=email, api_key=api_key, source=args.S)
                stats = counter.count_pmcid(args.s, limit=args.l)

                if args.format and args.format != "console":
                    formatted_output = StatsFormatter.format(stats, args.format)
                    print(formatted_output)
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"pmcid_stats_{timestamp}"
                    StatsFormatter.save_report(stats, filename, args.format)
                else:
                    print_pmcid_stats(stats)
                return

        elif args.m:
            logger.info(f"\n批量输入下载: {args.m}")
            results = fetcher.download_from_unified_input(
                input_value=args.m,
                column=args.c,
                limit=args.l,
                max_workers=args.t,
                base_delay=args.delay,
            )

            stats = log_download_stats(logger, results)

            if stats["success_count"] > 0:
                emit_download_results(
                    logger,
                    results,
                    args.o,
                    args.format,
                    source="unified_input",
                    input_value=args.m,
                )
        else:
            logger.error("请指定 -s 或 -m 参数")
            raise SystemExit(1)

    except KeyboardInterrupt:
        logger.info("\n用户中断下载")
        raise SystemExit(1) from None
    except SystemExit:
        raise
    except Exception as exc:
        logger.error(f"\n发生错误: {exc}", exc_info=True)
        raise SystemExit(1) from exc

    logger.info("\n下载完成")


if __name__ == "__main__":
    main()
