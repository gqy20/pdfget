#!/usr/bin/env python3
"""
PDF下载器主程序
独立的文献PDF下载工具
"""

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


def log_download_stats(logger, results: list[dict]) -> dict:
    """记录下载统计信息并返回统计结果"""
    success_count = sum(1 for r in results if r.get("success"))
    pdf_count = sum(1 for r in results if r.get("path"))
    html_count = sum(1 for r in results if r.get("full_text_url"))

    logger.info("\n📊 下载统计:")
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


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PDF文献下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 统计文献的PMCID情况
  python -m pdfget -s "machine learning cancer" -l 5000

  # 搜索并下载前N篇文献
  python -m pdfget -s "deep learning" -l 20 -d

  # 并发下载（多线程）
  python -m pdfget -s "cancer immunotherapy" -l 20 -d -t 5

  # 从CSV下载混合标识符（支持PMCID/PMID/DOI混合，自动检测列名）
  python -m pdfget -m identifiers.csv -t 5
  python -m pdfget -m pmcids.csv -c PMCID -l 100

  # 下载单个标识符
  python -m pdfget -m "PMC10851947"
  python -m pdfget -m "10.1016/j.cell.2020.01.021"

  # 下载多个标识符（逗号分隔）
  python -m pdfget -m "PMC123456,38238491,10.1038/xxx" -t 3
        """,
    )

    # 输入选项
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", help="搜索文献")
    group.add_argument(
        "-m",
        help="批量输入（CSV文件/单个标识符/逗号分隔列表），支持混合PMCID/PMID/DOI",
    )

    # 可选参数
    parser.add_argument(
        "-c",
        help="CSV列名（默认自动检测: ID>PMCID>doi>pmid>第一列）",
    )
    parser.add_argument("-o", default="data/pdfs", help="输出目录")
    parser.add_argument(
        "-l", type=int, default=DEFAULT_SEARCH_LIMIT, help="要处理的文献数量"
    )
    parser.add_argument("-d", action="store_true", help="下载PDF")
    parser.add_argument("-t", type=int, default=3, help="并发线程数（默认3）")
    parser.add_argument("-v", action="store_true", help="详细输出")
    parser.add_argument(
        "-S",
        choices=["pubmed", "europe_pmc", "arxiv", "both"],
        default=DEFAULT_SOURCE,
        help=f"数据源（默认: {DEFAULT_SOURCE}）",
    )
    parser.add_argument(
        "--format",
        choices=["console", "json", "markdown"],
        help="统计输出格式",
    )
    parser.add_argument("-e", help="NCBI API邮箱（提高请求限制）")
    parser.add_argument("-k", help="NCBI API密钥（可选）")
    parser.add_argument("--delay", type=float, help="下载延迟时间（秒，默认1.0）")

    args = parser.parse_args()

    # 设置日志
    logger = get_main_logger()
    if args.v:
        logger.setLevel(logging.DEBUG)

    # 初始化下载器
    fetcher = PaperFetcher(
        cache_dir="data/cache", output_dir=args.o, default_source=args.S
    )

    logger.info("🚀 PDF下载器启动")
    logger.info(f"   输出目录: {args.o}")

    try:
        if args.s:
            # 搜索文献
            logger.info(f"\n🔍 搜索文献: {args.s} (数据源: {args.S})")

            # 如果需要下载PDF，则只搜索少量文献
            # 如果不需要下载，则进行全量统计
            if args.d:
                # 下载模式：只获取前l篇文献
                fetch_pmcid = args.S == "pubmed"
                papers = fetcher.search_papers(
                    args.s, limit=args.l, source=args.S, fetch_pmcid=fetch_pmcid
                )

                if not papers:
                    logger.error("❌ 未找到匹配的文献")
                    exit(1)

                # 显示搜索结果
                logger.info(f"\n📊 搜索结果 ({len(papers)} 篇):")
                for i, paper in enumerate(papers, 1):
                    logger.info(f"\n{i}. {paper['title']}")
                    logger.info(
                        f"   作者: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}"
                    )
                    logger.info(f"   期刊: {paper['journal']} ({paper['year']})")
                    if paper["doi"]:
                        logger.info(f"   DOI: {paper['doi']}")
                    logger.info(f"   PMCID: {paper.get('pmcid', '无')}")
                    logger.info(f"   开放获取: {'是' if paper.get('pmcid') else '否'}")

                # 保存搜索结果
                search_results_file = (
                    Path(args.o) / f"search_results_{int(time.time())}.json"
                )
                search_results_file.parent.mkdir(parents=True, exist_ok=True)

                with open(search_results_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "query": args.s,
                            "timestamp": time.time(),
                            "total": len(papers),
                            "results": papers,
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                logger.info(f"\n💾 搜索结果已保存到: {search_results_file}")

            else:
                # 统计模式：获取全部文献的PMCID信息
                # 使用命令行参数或配置文件中的邮箱/API密钥
                email = args.e or NCBI_EMAIL
                api_key = args.k or NCBI_API_KEY

                counter = PMCIDCounter(
                    email=email,
                    api_key=api_key,
                    source=args.S,  # 传递数据源
                )

                # 执行统计
                stats = counter.count_pmcid(args.s, limit=args.l)

                # 格式化输出
                if args.format and args.format != "console":
                    formatted_output = StatsFormatter.format(stats, args.format)
                    print(formatted_output)

                    # 保存报告
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"pmcid_stats_{timestamp}"
                    StatsFormatter.save_report(stats, filename, args.format)
                else:
                    # 简单的控制台输出
                    print("\n📈 PMCID统计结果:")
                    print(f"   查询: {stats['query']}")
                    print(f"   总文献数: {stats['total']:,} 篇")
                    print(f"   检查了: {stats['checked']:,} 篇 (由-l参数指定)")
                    print(
                        f"   其中有PMCID: {stats['with_pmcid']:,} 篇 ({stats['rate']:.1f}%)"
                    )
                    print(f"   无PMCID: {stats['without_pmcid']:,} 篇")
                    print(f"   耗时: {stats['elapsed_seconds']:.1f} 秒")
                    # 避免除零错误
                    if stats["elapsed_seconds"] > 0:
                        print(
                            f"   处理速度: {stats['checked'] / stats['elapsed_seconds']:.1f} 篇/秒"
                        )
                    else:
                        print("   处理速度: N/A (使用缓存)")

                    if stats["with_pmcid"] > 0:
                        print("\n💾 如果下载所有开放获取文献:")
                        print(f"   文件数量: {stats['with_pmcid']:,} 个PDF")
                        size_mb = stats["estimated_size_mb"]
                        size_gb = size_mb / 1024
                        print(f"   估算大小: {size_mb:.1f} MB ({size_gb:.2f} GB)")

                    # 如果检查的样本数小于总数，提供说明
                    if stats["checked"] < stats["total"]:
                        print(
                            f"\n📝 说明: 仅检查了前 {stats['checked']:,} 篇文献的PMCID状态"
                        )

                return

            # 下载PDF
            logger.info("\n📥 开始下载PDF...")

            # 只下载有PMCID的开放获取文献
            oa_papers = [
                p
                for p in papers
                if p.get("pmcid") or p.get("arxiv_id") or p.get("pdf_url")
            ]
            logger.info(f"   找到 {len(oa_papers)} 篇开放获取文献")

            if oa_papers:
                # 使用统一下载管理器
                download_manager = UnifiedDownloadManager(
                    fetcher=fetcher,
                    max_workers=args.t,
                    base_delay=args.delay
                    if args.delay is not None
                    else DOWNLOAD_BASE_DELAY,
                )
                results = download_manager.download_batch(oa_papers, timeout=TIMEOUT)

                # 统计结果
                stats = log_download_stats(logger, results)

                # 保存下载结果
                if stats["success_count"] > 0:
                    download_results_file = Path(args.o) / "download_results.json"
                    with open(download_results_file, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "timestamp": time.time(),
                                "total": stats["total"],
                                "success": stats["success_count"],
                                "results": results,
                            },
                            f,
                            indent=2,
                            ensure_ascii=False,
                        )

                    logger.info(f"\n💾 下载结果已保存到: {download_results_file}")

        elif args.m:
            # 统一批量输入（CSV文件/单个标识符/逗号分隔列表）
            logger.info(f"\n📋 批量输入下载: {args.m}")

            # 使用统一输入下载方法
            results = fetcher.download_from_unified_input(
                input_value=args.m,
                column=args.c,
                limit=args.l,
                max_workers=args.t,
                base_delay=args.delay,
            )

            # 统计结果
            stats = log_download_stats(logger, results)

            # 保存下载结果
            if stats["success_count"] > 0:
                download_results_file = Path(args.o) / "download_results.json"
                download_results_file.parent.mkdir(parents=True, exist_ok=True)

                with open(download_results_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "timestamp": time.time(),
                            "source": "unified_input",
                            "input_value": args.m,
                            "total": stats["total"],
                            "success": stats["success_count"],
                            "results": results,
                        },
                        f,
                        indent=2,
                        ensure_ascii=False,
                    )

                logger.info(f"\n💾 下载结果已保存到: {download_results_file}")

        else:
            # 不应该到达这里，因为参数是required=True
            logger.error("❌ 请指定 -s 或 -m 参数")
            exit(1)

    except KeyboardInterrupt:
        logger.info("\n⏹️ 用户中断下载")
        exit(1)
    except Exception as e:
        logger.error(f"\n💥 发生错误: {e}", exc_info=True)
        exit(1)

    logger.info("\n✨ 下载完成")
    exit(0)


if __name__ == "__main__":
    main()
