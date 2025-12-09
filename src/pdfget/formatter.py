#!/usr/bin/env python3
"""统计结果格式化器"""

import json
from datetime import datetime

from . import config


class StatsFormatter:
    """统计结果格式化器"""

    @staticmethod
    def format_console(stats: dict) -> str:
        """格式化为控制台输出"""
        output = []
        output.append("\n📈 PMCID统计结果:")
        output.append(
            f"   查询: {stats['query'][:80]}{'...' if len(stats['query']) > 80 else ''}"
        )
        output.append(f"   检查文献数: {stats['checked']:,}")
        output.append(f"   有PMCID: {stats['with_pmcid']:,}")
        output.append(f"   无PMCID: {stats['without_pmcid']:,}")
        output.append(f"   开放获取比例: {stats['rate']:.1f}%")
        output.append(f"   耗时: {stats['elapsed_seconds']:.1f} 秒")

        if stats.get("processing_speed"):
            output.append(f"   处理速度: {stats['processing_speed']:.1f} 篇/秒")

        # 推算总数
        if stats["total"] > stats["checked"]:
            est_rate = stats["rate"] / 100
            est_pmcid = int(stats["total"] * est_rate)
            output.append(f"\n🎯 推算全部 {stats['total']:,} 篇文献:")
            output.append(f"   预估有PMCID: {est_pmcid:,} 篇")
            output.append(f"   预估无PMCID: {stats['total'] - est_pmcid:,} 篇")

        # 下载估算
        output.append(
            f"\n💾 如果下载所有开放获取文献（已检查的{stats['checked']:,}篇）:"
        )
        output.append(f"   文件数量: {stats['with_pmcid']:,} 个PDF")
        output.append(
            f"   估算大小: {stats['estimated_size_mb']:,.0f} MB ({stats['estimated_size_mb'] / 1024:.1f} GB)"
        )

        return "\n".join(output)

    @staticmethod
    def format_json(stats: dict) -> str:
        """格式化为JSON输出"""
        # 添加时间戳
        stats_with_meta = {
            "timestamp": datetime.now().isoformat(),
            "tool": "PDFGet PMCID Counter",
            "version": "1.0",
            "statistics": stats,
        }
        return json.dumps(stats_with_meta, indent=2, ensure_ascii=False)

    @staticmethod
    def format_markdown(stats: dict) -> str:
        """格式化为Markdown报告"""
        output = []
        output.append("# PMCID统计报告")
        output.append("")
        output.append(f"**查询时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("")
        output.append("## 查询条件")
        output.append("```")
        output.append(stats["query"])
        output.append("```")
        output.append("")
        output.append("## 统计结果")
        output.append("")
        output.append("| 项目 | 数量 | 百分比 |")
        output.append("|------|------|--------|")
        output.append(f"| 总文献数 | {stats['total']:,} | 100% |")
        output.append(
            f"| 检查文献数 | {stats['checked']:,} | {stats['checked'] / stats['total'] * 100:.1f}% |"
        )
        output.append(
            f"| 有PMCID（开放获取） | {stats['with_pmcid']:,} | {stats['rate']:.1f}% |"
        )
        output.append(
            f"| 无PMCID | {stats['without_pmcid']:,} | {100 - stats['rate']:.1f}% |"
        )
        output.append("")
        output.append("### 处理效率")
        output.append(f"- 耗时: {stats['elapsed_seconds']:.1f} 秒")
        if stats.get("processing_speed"):
            output.append(f"- 处理速度: {stats['processing_speed']:.1f} 篇/秒")
        output.append("")

        # 推算总数
        if stats["total"] > stats["checked"]:
            est_rate = stats["rate"] / 100
            est_pmcid = int(stats["total"] * est_rate)
            output.append("### 总数预估")
            output.append(f"- 预估有PMCID: {est_pmcid:,} 篇")
            output.append(f"- 预估无PMCID: {stats['total'] - est_pmcid:,} 篇")
            output.append("")

        # 下载估算
        output.append("### 下载估算")
        output.append(f"- 文件数量: {stats['with_pmcid']:,} 个PDF")
        output.append(
            f"- 估算大小: {stats['estimated_size_mb']:,.0f} MB ({stats['estimated_size_mb'] / 1024:.1f} GB)"
        )
        output.append("")
        output.append("---")
        output.append("*由 PDFGet PMCID Counter 生成*")

        return "\n".join(output)

    @classmethod
    def format(cls, stats: dict, format_type: str | None = None) -> str:
        """根据配置格式化输出

        Args:
            stats: 统计结果
            format_type: 输出格式 (console, json, markdown)
                        如果为None，使用配置文件中的设置

        Returns:
            格式化后的字符串
        """
        if format_type is None:
            format_type = config.COUNT_OUTPUT_FORMAT

        if format_type == "json":
            return cls.format_json(stats)
        elif format_type == "markdown":
            return cls.format_markdown(stats)
        else:
            return cls.format_console(stats)

    @classmethod
    def save_report(
        cls, stats: dict, filename: str, format_type: str | None = None
    ) -> None:
        """保存报告到文件

        Args:
            stats: 统计结果
            filename: 文件名（不含扩展名）
            format_type: 输出格式
        """
        content = cls.format(stats, format_type)

        if format_type == "json":
            filename += ".json"
        elif format_type == "markdown":
            filename += ".md"
        else:
            filename += ".txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"\n📄 报告已保存到: {filename}")
