"""CLI workflow helpers for search, download, resume, and reporting."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from .config import DOWNLOAD_BASE_DELAY, TIMEOUT
from .download_plan import (
    DownloadPlan,
    build_download_plan,
    load_download_plan,
    ready_papers,
    save_download_plan,
)
from .download_service import DownloadManagerFactory
from .input_planner import build_download_plan_from_unified_input
from .logger import Logger
from .protocols import DownloadContext, SearchProvider
from .run_report import build_run_summary, load_failed_papers, save_run_summary
from .schemas import DownloadPayload, DownloadResult, PmcidStats, SearchPayload


class CliFetcher(SearchProvider, DownloadContext, Protocol):
    """Fetcher capabilities required by CLI workflows."""


class Counter(Protocol):
    """PMCID counter instance used by search workflows."""

    def count_pmcid(self, query: str, limit: int = 1000) -> PmcidStats: ...


class CounterFactory(Protocol):
    """Factory for PMCID counter instances."""

    def __call__(
        self,
        *,
        email: str | None = None,
        api_key: str | None = None,
        source: str = "pubmed",
    ) -> Counter: ...


class StatsFormatterProtocol(Protocol):
    """Statistics formatter API used by CLI workflows."""

    def format(self, stats: PmcidStats, format_type: str | None = None) -> str: ...

    def save_report(
        self,
        stats: PmcidStats,
        filename: str,
        format_type: str | None = None,
    ) -> None: ...


class CommonWorkflowArgs(Protocol):
    """CLI argument attributes shared by workflow modes."""

    o: str
    t: int
    format: str | None
    delay: float | None
    dry_run: bool
    source_priority: str


class SearchWorkflowArgs(CommonWorkflowArgs, Protocol):
    """CLI argument attributes for search mode."""

    s: str
    S: str
    l: int  # noqa: E741 - argparse attribute from the public -l option.
    d: bool


class UnifiedInputWorkflowArgs(CommonWorkflowArgs, Protocol):
    """CLI argument attributes for unified input mode."""

    m: str
    c: str | None
    l: int  # noqa: E741 - argparse attribute from the public -l option.


class ResumeWorkflowArgs(CommonWorkflowArgs, Protocol):
    """CLI argument attributes for resume mode."""

    resume: str


def log_download_stats(
    logger: Logger, results: list[DownloadResult]
) -> dict[str, int]:
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


def parse_source_priority(value: str) -> list[str]:
    """Parse and validate a comma-separated download source priority string."""
    allowed = {"pmc", "europe_pmc", "arxiv", "direct"}
    sources = [source.strip() for source in value.split(",") if source.strip()]
    unknown = [source for source in sources if source not in allowed]
    if unknown:
        raise ValueError(f"不支持的下载来源: {', '.join(unknown)}")
    return sources or ["pmc", "europe_pmc", "arxiv", "direct"]


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Persist JSON output, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def build_search_payload(query: str, papers: list[dict[str, Any]]) -> SearchPayload:
    """Build a schema-first payload for search output."""
    return {
        "schema": "paper_record.v1",
        "query": query,
        "timestamp": time.time(),
        "total": len(papers),
        "results": papers,
    }


def build_download_payload(
    results: list[DownloadResult], *, source: str, input_value: str | None = None
) -> DownloadPayload:
    """Build a schema-first payload for download output."""
    success_count = sum(1 for result in results if result.get("success"))
    payload: DownloadPayload = {
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


def is_downloadable(paper: dict[str, Any]) -> bool:
    """Whether the paper has a direct download route."""
    return bool(paper.get("pmcid") or paper.get("arxiv_id") or paper.get("pdf_url"))


def log_download_plan(logger: Logger, plan: dict[str, Any]) -> None:
    """Log a compact download plan summary."""
    duplicate_count = sum(
        1 for entry in plan["entries"] if entry.get("skip_reason") == "duplicate"
    )
    no_route_count = sum(
        1 for entry in plan["entries"] if entry.get("skip_reason") == "no_download_route"
    )
    logger.info(
        f"\n下载计划: 总计 {plan['total']}，可下载 {plan['ready']}，跳过 {plan['skipped']}"
    )
    if duplicate_count or no_route_count:
        logger.info(f"   跳过原因: 重复 {duplicate_count}，无下载路径 {no_route_count}")


def emit_download_plan(logger: Logger, plan: dict[str, Any], output_dir: str) -> Path:
    """Persist the download plan for audit and dry-run workflows."""
    plan_file = save_download_plan(output_dir, plan)  # type: ignore[arg-type]
    logger.info(f"\n下载计划已保存到: {plan_file}")
    return plan_file


def get_primary_identifier_display(paper: dict[str, Any]) -> tuple[str, str]:
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


def display_search_results(logger: Logger, papers: list[dict[str, Any]]) -> None:
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


def save_search_results(output_dir: str, query: str, papers: list[dict[str, Any]]) -> Path:
    """Save search results to a timestamped JSON file."""
    path = Path(output_dir) / f"search_results_{int(time.time())}.json"
    save_json(path, build_search_payload(query, papers))
    return path


def emit_search_results(
    logger: Logger,
    query: str,
    papers: list[dict[str, Any]],
    output_dir: str,
    output_format: str | None,
    *,
    stream_output: bool = True,
) -> Path:
    """Render search results for humans and save a schema-first payload."""
    if output_format == "json" and stream_output:
        print(json.dumps(build_search_payload(query, papers), ensure_ascii=False, indent=2))
    else:
        display_search_results(logger, papers)

    search_results_file = save_search_results(output_dir, query, papers)
    logger.info(f"\n搜索结果已保存到: {search_results_file}")
    return search_results_file


def emit_download_results(
    logger: Logger,
    results: list[DownloadResult],
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


def emit_run_summary(
    logger: Logger,
    results: list[DownloadResult],
    output_dir: str,
    *,
    papers: list[dict[str, Any]] | None = None,
    plan_entries: Sequence[Mapping[str, Any]] | None = None,
    source: str,
    input_value: str | None = None,
    previous_report: str | None = None,
    download_plan_path: str | None = None,
) -> Path:
    """Save a retryable run summary for every download run."""
    summary = build_run_summary(
        results,
        papers=papers,
        plan_entries=plan_entries,
        source=source,
        output_dir=output_dir,
        input_value=input_value,
        previous_report=previous_report,
        download_plan_path=download_plan_path,
    )
    summary_file = save_run_summary(output_dir, summary)
    logger.info(f"\n运行报告已保存到: {summary_file}")
    return summary_file


def load_resume_plan_or_papers(
    resume_path: str,
    *,
    fetcher: CliFetcher,
) -> tuple[DownloadPlan, str]:
    """Load a resume source as a download plan, preserving old run-summary resume."""
    with open(resume_path, encoding="utf-8") as file:
        payload = json.load(file)

    schema = payload.get("schema")
    if schema == "download_plan.v1":
        return load_download_plan(resume_path), "download_plan"
    if schema == "run_summary.v1":
        papers = load_failed_papers(resume_path)
        return build_download_plan(papers, source="resume", resolver=fetcher), "run_summary"
    raise ValueError(f"不支持的续跑文件 schema: {schema}")


def print_pmcid_stats(stats: PmcidStats) -> None:
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


def run_search_workflow(
    args: SearchWorkflowArgs,
    *,
    logger: Logger,
    fetcher: CliFetcher,
    download_manager_cls: DownloadManagerFactory,
    counter_cls: CounterFactory,
    stats_formatter: StatsFormatterProtocol,
) -> None:
    """Run search mode, optionally followed by download."""
    logger.info(f"\n搜索文献: {args.s} (数据源: {args.S})")

    if args.d:
        fetch_pmcid = args.S == "pubmed"
        papers = fetcher.search_papers(
            args.s, limit=args.l, source=args.S, fetch_pmcid=fetch_pmcid
        )

        if not papers:
            logger.error("未找到匹配的文献")
            raise SystemExit(1)

        emit_search_results(
            logger,
            args.s,
            papers,
            args.o,
            args.format,
            stream_output=args.format != "json",
        )

        plan = build_download_plan(papers, source="search", resolver=fetcher)
        log_download_plan(logger, plan)
        plan_file = emit_download_plan(logger, plan, args.o)
        downloadable_papers = ready_papers(plan)
        if args.dry_run:
            logger.info("\nDry run 完成，未执行下载")
            return
        logger.info(f"\n开始下载 PDF，找到 {len(downloadable_papers)} 篇可下载文献")

        results: list[DownloadResult] = []
        if downloadable_papers:
            download_manager = download_manager_cls(
                fetcher=fetcher,
                max_workers=args.t,
                base_delay=args.delay if args.delay is not None else DOWNLOAD_BASE_DELAY,
                source_priority=parse_source_priority(args.source_priority),
            )
            results = download_manager.download_batch(downloadable_papers, timeout=TIMEOUT)
            log_download_stats(logger, results)
        else:
            logger.info("没有可下载文献，已将跳过原因写入运行报告")

        emit_run_summary(
            logger,
            results,
            args.o,
            papers=downloadable_papers,
            plan_entries=plan["entries"],
            source="search",
            input_value=args.s,
            download_plan_path=str(plan_file),
        )
        emit_download_results(
            logger,
            results,
            args.o,
            args.format,
            source="search",
        )
        return

    if args.S == "arxiv":
        papers = fetcher.search_papers(args.s, limit=args.l, source=args.S)
        if not papers:
            logger.error("未找到匹配的文献")
            raise SystemExit(1)

        emit_search_results(logger, args.s, papers, args.o, args.format)
        return

    counter = counter_cls(email=fetcher.email, api_key=fetcher.api_key, source=args.S)
    stats = counter.count_pmcid(args.s, limit=args.l)

    if args.format and args.format != "console":
        formatted_output = stats_formatter.format(stats, args.format)
        print(formatted_output)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"pmcid_stats_{timestamp}"
        stats_formatter.save_report(stats, filename, args.format)
    else:
        print_pmcid_stats(stats)


def run_unified_input_workflow(
    args: UnifiedInputWorkflowArgs,
    *,
    logger: Logger,
    fetcher: CliFetcher,
    download_manager_cls: DownloadManagerFactory,
) -> None:
    """Run CSV or direct identifier download mode."""
    logger.info(f"\n批量输入下载: {args.m}")
    plan = build_download_plan_from_unified_input(
        args.m,
        column=args.c,
        limit=args.l,
        resolver=fetcher,
        logger=logger,
    )
    log_download_plan(logger, plan)
    plan_file = emit_download_plan(logger, plan, args.o)
    downloadable_papers = ready_papers(plan)
    if args.dry_run:
        logger.info("\nDry run 完成，未执行下载")
        return
    download_manager = download_manager_cls(
        fetcher=fetcher,
        max_workers=args.t,
        base_delay=args.delay if args.delay is not None else DOWNLOAD_BASE_DELAY,
        source_priority=parse_source_priority(args.source_priority),
    )
    results = download_manager.download_batch(downloadable_papers, timeout=TIMEOUT)

    log_download_stats(logger, results)
    emit_run_summary(
        logger,
        results,
        args.o,
        papers=downloadable_papers,
        plan_entries=plan["entries"],
        source="unified_input",
        input_value=args.m,
        download_plan_path=str(plan_file),
    )
    emit_download_results(
        logger,
        results,
        args.o,
        args.format,
        source="unified_input",
        input_value=args.m,
    )


def run_resume_workflow(
    args: ResumeWorkflowArgs,
    *,
    logger: Logger,
    fetcher: CliFetcher,
    download_manager_cls: DownloadManagerFactory,
) -> None:
    """Retry failed items from a run summary."""
    logger.info(f"\n重试失败下载: {args.resume}")
    plan, resume_source = load_resume_plan_or_papers(args.resume, fetcher=fetcher)
    log_download_plan(logger, plan)
    plan_file = emit_download_plan(logger, plan, args.o)
    downloadable_papers = ready_papers(plan)
    if not downloadable_papers:
        logger.info("续跑文件中没有可下载或可重试的项目")
        return
    if args.dry_run:
        logger.info("\nDry run 完成，未执行下载")
        return
    logger.info(f"准备续跑 {len(downloadable_papers)} 个项目")
    download_manager = download_manager_cls(
        fetcher=fetcher,
        max_workers=args.t,
        base_delay=args.delay if args.delay is not None else DOWNLOAD_BASE_DELAY,
        source_priority=parse_source_priority(args.source_priority),
    )
    results = download_manager.download_batch(downloadable_papers, timeout=TIMEOUT)
    log_download_stats(logger, results)
    emit_run_summary(
        logger,
        results,
        args.o,
        papers=downloadable_papers,
        plan_entries=plan["entries"],
        source="resume",
        input_value=resume_source,
        previous_report=args.resume,
        download_plan_path=str(plan_file),
    )
    emit_download_results(
        logger,
        results,
        args.o,
        args.format,
        source="resume",
        input_value=args.resume,
    )
