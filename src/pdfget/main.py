#!/usr/bin/env python3
"""
PDF下载器主程序
独立的文献PDF下载工具
"""

import argparse
import json
import time
from pathlib import Path

import logging

from .fetcher import PaperFetcher
from .concurrent_downloader import ConcurrentDownloader
from .config import TIMEOUT, DELAY, LOG_LEVEL, LOG_FORMAT


def main() -> None:
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PDF文献下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 搜索文献
  python -m pdfget -s "machine learning cancer"
  python -m pdfget -s "deep learning" -l 20 -d

  # 并发下载（多线程）
  python -m pdfget -s "cancer immunotherapy" -l 20 -d -t 5
  python -m pdfget -i dois.csv -t 3

  # 下载单个文献
  python -m pdfget --doi 10.1016/j.cell.2020.01.021
        """
    )

    # 输入选项
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi", help="单个DOI")
    group.add_argument("-i", help="输入文件（CSV或TXT）")
    group.add_argument("-s", help="搜索文献")

    # 可选参数
    parser.add_argument("-c", default="doi", help="CSV列名（默认: doi）")
    parser.add_argument("-o", default="data/pdfs", help="输出目录")
    parser.add_argument("--delay", type=float, default=DELAY, help="请求延迟秒数")
    parser.add_argument("-l", type=int, default=50, help="搜索结果数量")
    parser.add_argument("-d", action="store_true", help="下载PDF")
    parser.add_argument("-t", type=int, default=3, help="并发线程数（默认3）")
    parser.add_argument("-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=logging.DEBUG if args.v else LOG_LEVEL,
        format=LOG_FORMAT
    )
    logger = logging.getLogger("PDFDownloader")

    # 初始化下载器
    fetcher = PaperFetcher(cache_dir="data/cache")

    logger.info("🚀 PDF下载器启动")
    logger.info(f"   输出目录: {args.o}")

    try:
        if args.doi:
            # 单个DOI下载
            logger.info(f"\n📄 下载单个文献: {args.doi}")
            result = fetcher.fetch_by_doi(args.doi, timeout=TIMEOUT)

            if result.get("success"):
                logger.info("✅ 下载成功!")
                if result.get("pdf_path"):
                    logger.info(f"   PDF路径: {result['pdf_path']}")
                else:
                    logger.info(f"   HTML链接: {result.get('full_text_url')}")
            else:
                logger.error(f"❌ 下载失败: {result.get('error', 'Unknown error')}")

        elif args.s:
            # 搜索文献
            logger.info(f"\n🔍 搜索文献: {args.s}")
            papers = fetcher.search_papers(args.s, limit=args.l)

            if not papers:
                logger.error("❌ 未找到匹配的文献")
                exit(1)

            # 显示搜索结果
            logger.info(f"\n📊 搜索结果 ({len(papers)} 篇):")
            for i, paper in enumerate(papers, 1):
                logger.info(f"\n{i}. {paper['title']}")
                logger.info(f"   作者: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
                logger.info(f"   期刊: {paper['journal']} ({paper['year']})")
                if paper['doi']:
                    logger.info(f"   DOI: {paper['doi']}")
                logger.info(f"   开放获取: {'是' if paper['isOpenAccess'] else '否'}")

            # 保存搜索结果
            search_results_file = Path(args.o) / f"search_results_{int(time.time())}.json"
            search_results_file.parent.mkdir(parents=True, exist_ok=True)

            with open(search_results_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": args.s,
                    "timestamp": time.time(),
                    "total": len(papers),
                    "results": papers
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"\n💾 搜索结果已保存到: {search_results_file}")

            # 如果需要下载PDF
            if args.d:
                logger.info("\n📥 开始下载PDF...")

                # 只下载有PMCID的开放获取文献
                oa_papers = [p for p in papers if p['pmcid']]
                logger.info(f"   找到 {len(oa_papers)} 篇开放获取文献")

                if oa_papers:
                    # 构造DOI列表
                    dois = [p['doi'] for p in oa_papers if p['doi']]

                    if dois:
                        # 根据线程数决定是否使用并发下载
                        if len(dois) > 1 and args.t > 1:
                            logger.info(f"\n🚀 使用 {args.t} 个线程并发下载 {len(dois)} 篇文献")
                            concurrent_downloader = ConcurrentDownloader(
                                max_workers=args.t,
                                base_delay=args.delay,
                                fetcher=fetcher
                            )
                            results = concurrent_downloader.download_batch(dois, timeout=TIMEOUT)
                        else:
                            # 单线程下载（保持原有逻辑）
                            results = fetcher.fetch_batch(dois, delay=args.delay)

                        # 统计结果
                        success_count = sum(1 for r in results if r.get("success"))
                        pdf_count = sum(1 for r in results if r.get("pdf_path"))
                        html_count = sum(1 for r in results if r.get("full_text_url"))

                        logger.info("\n📊 下载统计:")
                        logger.info(f"   总计: {len(results)}")
                        logger.info(f"   成功: {success_count}")
                        logger.info(f"   PDF: {pdf_count}")
                        logger.info(f"   HTML: {html_count}")
                        logger.info(f"   失败: {len(results) - success_count}")

                        # 保存下载结果
                        if success_count > 0:
                            download_results_file = Path(args.o) / "download_results.json"
                            with open(download_results_file, 'w', encoding='utf-8') as f:
                                json.dump({
                                    "timestamp": time.time(),
                                    "total": len(results),
                                    "success": success_count,
                                    "results": results
                                }, f, indent=2, ensure_ascii=False)

                            logger.info(f"\n💾 下载结果已保存到: {download_results_file}")

        else:
            # 批量下载
            logger.info(f"\n📚 批量下载: {args.i}")

            # 读取DOI列表
            input_path = Path(args.i)
            if not input_path.exists():
                logger.error(f"❌ 输入文件不存在: {args.i}")
                exit(1)

            if input_path.suffix.lower() == '.csv':
                # 读取CSV文件
                import pandas as pd
                try:
                    df = pd.read_csv(input_path)
                    if args.c not in df.columns:
                        logger.error(f"❌ CSV文件中找不到列: {args.c}")
                        exit(1)

                    dois = df[args.c].dropna().unique().tolist()
                    logger.info(f"   找到 {len(dois)} 个唯一DOI")

                except Exception as e:
                    logger.error(f"❌ 读取CSV文件失败: {e}")
                    exit(1)

            else:
                # 读取文本文件（每行一个DOI）
                try:
                    with open(input_path, 'r') as f:
                        dois = [line.strip() for line in f if line.strip()]
                    logger.info(f"   找到 {len(dois)} 个DOI")

                except Exception as e:
                    logger.error(f"❌ 读取文件失败: {e}")
                    exit(1)

            # 根据线程数决定是否使用并发下载
            if len(dois) > 1 and args.t > 1:
                logger.info(f"\n🚀 使用 {args.t} 个线程并发下载 {len(dois)} 篇文献")
                concurrent_downloader = ConcurrentDownloader(
                    max_workers=args.t,
                    base_delay=args.delay,
                    fetcher=fetcher
                )
                results = concurrent_downloader.download_batch(dois, timeout=TIMEOUT)
            else:
                # 单线程下载（保持原有逻辑）
                results = fetcher.fetch_batch(dois, delay=args.delay)

            # 统计结果
            success_count = sum(1 for r in results if r.get("success"))
            pdf_count = sum(1 for r in results if r.get("pdf_path"))
            html_count = sum(1 for r in results if r.get("full_text_url"))

            logger.info("\n📊 下载统计:")
            logger.info(f"   总计: {len(results)}")
            logger.info(f"   成功: {success_count}")
            logger.info(f"   PDF: {pdf_count}")
            logger.info(f"   HTML: {html_count}")
            logger.info(f"   失败: {len(results) - success_count}")

            # 保存结果
            if success_count > 0:
                output_file = Path(args.o) / "download_results.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": time.time(),
                        "total": len(results),
                        "success": success_count,
                        "results": results
                    }, f, indent=2, ensure_ascii=False)

                logger.info(f"\n💾 结果已保存到: {output_file}")

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