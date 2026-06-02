#!/usr/bin/env python3
"""Command line entry point for pdfget."""

import argparse

from .cli_workflows import (
    get_primary_identifier_display,
    run_resume_workflow,
    run_search_workflow,
    run_unified_input_workflow,
)
from .config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SOURCE,
    NCBI_API_KEY,
    NCBI_EMAIL,
)
from .counter import PMCIDCounter
from .download_plan import build_download_plan
from .fetcher import PaperFetcher
from .formatter import StatsFormatter
from .logger import configure_logging, get_main_logger
from .manager import UnifiedDownloadManager

__all__ = [
    "build_download_plan",
    "build_parser",
    "get_primary_identifier_display",
    "main",
]


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
    group.add_argument("--resume", help="从 run_summary.json 或 download_plan.json 续跑")

    parser.add_argument(
        "-c",
        help="CSV 列名（默认自动检测: ID > PMCID > doi > pmid > 第一列）",
    )
    parser.add_argument("-o", default=DEFAULT_OUTPUT_DIR, help="输出目录")
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
    parser.add_argument(
        "--source-priority",
        default="pmc,europe_pmc,arxiv,direct",
        help="下载来源优先级，逗号分隔: pmc,europe_pmc,arxiv,direct",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成搜索结果和下载计划，不实际下载",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="日志输出格式（默认: text，始终写入 stderr）",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别（默认使用配置文件 LOG_LEVEL）",
    )
    parser.add_argument("--quiet", action="store_true", help="仅输出错误日志")
    return parser


def main() -> None:
    """Run the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    log_level = "DEBUG" if args.v else args.log_level
    configure_logging(
        level=log_level,
        log_format=args.log_format,
        quiet=args.quiet,
        force=True,
    )
    logger = get_main_logger()

    email = args.e or NCBI_EMAIL
    api_key = args.k or NCBI_API_KEY
    fetcher = PaperFetcher(
        output_dir=args.o,
        default_source=args.S,
        email=email,
        api_key=api_key,
    )

    logger.info("PDF 下载器启动")
    logger.info(f"   输出目录: {args.o}")

    try:
        if args.s:
            run_search_workflow(
                args,
                logger=logger,
                fetcher=fetcher,
                download_manager_cls=UnifiedDownloadManager,
                counter_cls=PMCIDCounter,
                stats_formatter=StatsFormatter,
            )
        elif args.m:
            run_unified_input_workflow(
                args,
                logger=logger,
                fetcher=fetcher,
                download_manager_cls=UnifiedDownloadManager,
            )
        elif args.resume:
            run_resume_workflow(
                args,
                logger=logger,
                fetcher=fetcher,
                download_manager_cls=UnifiedDownloadManager,
            )
        else:
            logger.error("请指定 -s、-m 或 --resume 参数")
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
