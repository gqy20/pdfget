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
        prog="pdfget",
        description=(
            "PDFGet: 智能文献搜索与并发 PDF 下载（PubMed / Europe PMC / arXiv）。\n"
            "支持 CSV 与混合标识符输入；下载/搜索结果按 JSON schema 输出，\n"
            "适合作为 Agent / 自动化脚本的底层工具（schemas: paper_record.v1 /\n"
            "download_plan.v1 / download_result.v1 / run_summary.v2）"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 统计 PubMed / Europe PMC 文献的 PMCID 情况
  pdfget -s "machine learning cancer" -l 5000

  # 搜索 arXiv 文献
  pdfget -s "graph neural networks" -S arxiv -l 20

  # 搜索并下载前 N 篇文献
  pdfget -s "deep learning" -l 20 -d
  pdfget -s "vision transformer" -S arxiv -l 20 -d

  # 并发下载（多线程）
  pdfget -s "cancer immunotherapy" -l 20 -d -t 5

  # 从 CSV 下载混合标识符（支持 PMCID/PMID/DOI/arXiv ID 混合）
  pdfget -m identifiers.csv -t 5
  pdfget -m pmcids.csv -c PMCID -l 100

  # 下载单个标识符
  pdfget -m "PMC10851947"
  pdfget -m "10.1016/j.cell.2020.01.021"
  pdfget -m "2301.12345"

  # 下载多个标识符（逗号分隔）
  pdfget -m "PMC123456,38238491,10.1038/xxx,2301.12345" -t 3

  # 仅生成下载计划与运行报告，不下载
  pdfget -s "vision transformer" -S all -l 30 -d --dry-run
  pdfget --resume data/pdfs/run_summary.json -t 3
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-s",
        metavar="QUERY",
        help=(
            "搜索文献。要提高下载成功率，搜词加 'pubmed pmc[sb]' 过滤器"
            "（例如: \"cancer AND pubmed pmc[sb]\"）"
        ),
    )
    group.add_argument(
        "-m",
        metavar="INPUT",
        help=(
            "批量输入：CSV 路径、单值标识符或逗号分隔列表，自动识别"
            " PMCID/PMID/DOI/arXiv ID（含新式 YYMM.NNNNN 与旧式 cs.LG/0703001）"
        ),
    )
    group.add_argument(
        "--resume",
        metavar="REPORT_OR_PLAN",
        help=(
            "续跑：传 run_summary.json 仅重试 retryable 失败项；"
            "传 download_plan.json 按计划继续并跳过已有 PDF"
        ),
    )

    parser.add_argument(
        "-c",
        metavar="COLUMN",
        help=(
            "CSV 列名（不区分大小写；默认自动检测: ID > PMCID > doi > pmid > 第一列；"
            "示例表头: pmcid,pmid,doi,arxiv_id）"
        ),
    )
    parser.add_argument(
        "-o", metavar="DIR", default=DEFAULT_OUTPUT_DIR, help="输出目录"
    )
    parser.add_argument(
        "-l",
        metavar="N",
        type=int,
        default=DEFAULT_SEARCH_LIMIT,
        help=f"要处理的文献数量（默认: {DEFAULT_SEARCH_LIMIT}）",
    )
    parser.add_argument("-d", action="store_true", help="下载 PDF")
    parser.add_argument(
        "-t", metavar="N", type=int, default=3, help="并发线程数（默认: 3）"
    )
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
        help=(
            "统计输出格式（默认: console）。json 模式下日志走 stderr，"
            "stdout 仅输出 JSON payload，便于 Agent/脚本消费"
        ),
    )
    parser.add_argument("-e", metavar="EMAIL", help="NCBI API 邮箱（提高请求限制）")
    parser.add_argument("-k", metavar="KEY", help="NCBI API 密钥（可选）")
    parser.add_argument(
        "--delay",
        metavar="SECONDS",
        type=float,
        help="下载延迟时间（秒，默认: 1.0）",
    )
    parser.add_argument(
        "--source-priority",
        metavar="LIST",
        default="pmc,europe_pmc,arxiv,direct",
        help="下载来源优先级，逗号分隔（默认: pmc,europe_pmc,arxiv,direct）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成搜索结果、下载计划与运行报告（不实际下载）",
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
