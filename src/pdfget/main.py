#!/usr/bin/env python3
"""
PDF下载器主程序
独立的文献PDF下载工具
"""

import argparse
import json
import sys
import time
from pathlib import Path

import logging

from .fetcher import PaperFetcher
from .config import TIMEOUT, MAX_RETRIES, DELAY, OUTPUT_DIR, LOG_LEVEL, LOG_FORMAT


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PDF文献下载器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载单个文献
  python main.py --doi 10.1016/j.cell.2020.01.021

  # 搜索文献
  python main.py --search "machine learning cancer"
  python main.py -s "title:deep learning AND author:hinton" --limit 20

  # 高级检索
  python main.py --search '"quantum computing" AND NOT review' --download
  python main.py -s "cancer AND immunotherapy" -d --limit 30

  # 批量下载（从CSV文件）
  python main.py --input dois.csv --column doi

  # 批量下载（从文本文件，每行一个DOI）
  python main.py --input dois.txt

  # 自定义输出目录
  python main.py --doi 10.1016/j.cell.2020.01.021 --output ./my_pdfs

  # 启用详细日志
  python main.py --doi 10.1016/j.cell.2020.01.021 --verbose
        """
    )

    # 输入选项
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--doi", help="单个DOI")
    group.add_argument("--input", "-i", help="输入文件路径（CSV或TXT）")
    group.add_argument("--search", "-s", help="搜索文献（支持高级检索语法）")

    # 可选参数
    parser.add_argument("--column", "-c", default="doi",
                       help="CSV文件中的DOI列名（默认: doi）")
    parser.add_argument("--output", "-o", default="data/pdfs",
                       help="输出目录（默认: data/pdfs）")
    parser.add_argument("--cache", default="data/cache",
                       help="缓存目录（默认: data/cache）")
    parser.add_argument("--delay", type=float, default=DELAY,
                       help=f"请求间延迟秒数（默认: {DELAY}）")
    parser.add_argument("--timeout", type=int, default=TIMEOUT,
                       help=f"请求超时时间（默认: {TIMEOUT}秒）")
    parser.add_argument("--limit", "-l", type=int, default=50,
                       help="搜索结果数量限制（默认: 50）")
    parser.add_argument("--download", "-d", action="store_true",
                       help="搜索后自动下载PDF")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="启用详细日志输出")

    args = parser.parse_args()

    # 设置日志
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else LOG_LEVEL,
        format=LOG_FORMAT
    )
    logger = logging.getLogger("PDFDownloader")

    # 初始化下载器
    fetcher = PaperFetcher(cache_dir=args.cache)

    logger.info("🚀 PDF下载器启动")
    logger.info(f"   输出目录: {args.output}")
    logger.info(f"   缓存目录: {args.cache}")
    logger.info(f"   请求延迟: {args.delay}秒")

    try:
        if args.doi:
            # 单个DOI下载
            logger.info(f"\n📄 下载单个文献: {args.doi}")
            result = fetcher.fetch_by_doi(args.doi, timeout=args.timeout)

            if result.get("success"):
                logger.info("✅ 下载成功!")
                if result.get("pdf_path"):
                    logger.info(f"   PDF路径: {result['pdf_path']}")
                else:
                    logger.info(f"   HTML链接: {result.get('full_text_url')}")
            else:
                logger.error(f"❌ 下载失败: {result.get('error', 'Unknown error')}")

        elif args.search:
            # 搜索文献
            logger.info(f"\n🔍 搜索文献: {args.search}")
            papers = fetcher.search_papers(args.search, limit=args.limit)

            if not papers:
                logger.error("❌ 未找到匹配的文献")
                return 1

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
            search_results_file = Path(args.output) / f"search_results_{int(time.time())}.json"
            search_results_file.parent.mkdir(parents=True, exist_ok=True)

            with open(search_results_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "query": args.search,
                    "timestamp": time.time(),
                    "total": len(papers),
                    "results": papers
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"\n💾 搜索结果已保存到: {search_results_file}")

            # 如果需要下载PDF
            if args.download:
                logger.info(f"\n📥 开始下载PDF...")

                # 只下载有PMCID的开放获取文献
                oa_papers = [p for p in papers if p['pmcid']]
                logger.info(f"   找到 {len(oa_papers)} 篇开放获取文献")

                if oa_papers:
                    # 构造DOI列表
                    dois = [p['doi'] for p in oa_papers if p['doi']]

                    if dois:
                        # 批量下载
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
                            download_results_file = Path(args.output) / "download_results.json"
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
            logger.info(f"\n📚 批量下载: {args.input}")

            # 读取DOI列表
            input_path = Path(args.input)
            if not input_path.exists():
                logger.error(f"❌ 输入文件不存在: {args.input}")
                return 1

            if input_path.suffix.lower() == '.csv':
                # 读取CSV文件
                import pandas as pd
                try:
                    df = pd.read_csv(input_path)
                    if args.column not in df.columns:
                        logger.error(f"❌ CSV文件中找不到列: {args.column}")
                        return 1

                    dois = df[args.column].dropna().unique().tolist()
                    logger.info(f"   找到 {len(dois)} 个唯一DOI")

                except Exception as e:
                    logger.error(f"❌ 读取CSV文件失败: {e}")
                    return 1

            else:
                # 读取文本文件（每行一个DOI）
                try:
                    with open(input_path, 'r') as f:
                        dois = [line.strip() for line in f if line.strip()]
                    logger.info(f"   找到 {len(dois)} 个DOI")

                except Exception as e:
                    logger.error(f"❌ 读取文件失败: {e}")
                    return 1

            # 批量处理
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
                output_file = Path(args.output) / "download_results.json"
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
        return 130
    except Exception as e:
        logger.error(f"\n💥 发生错误: {e}", exc_info=True)
        return 1

    logger.info("\n✨ 下载完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())