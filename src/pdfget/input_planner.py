"""Build download plans from CSV files or direct identifier input."""

from __future__ import annotations

from typing import Protocol, cast

from .download_plan import DownloadPlan, IdentifierResolver, build_download_plan
from .input_parser import (
    auto_detect_column,
    build_papers_from_identifiers,
    detect_input_type,
    parse_identifier_string,
    read_identifier_values_from_csv,
)
from .logger import get_logger


class PlannerLogger(Protocol):
    """Minimal logger surface used while building input plans."""

    def info(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


def build_download_plan_from_unified_input(
    input_value: str,
    *,
    column: str | None = None,
    limit: int | None = None,
    resolver: IdentifierResolver | None = None,
    logger: PlannerLogger | None = None,
) -> DownloadPlan:
    """Build a download plan from a CSV path or identifier string."""
    plan_logger = logger if logger is not None else cast(PlannerLogger, get_logger(__name__))
    input_type = detect_input_type(input_value)

    if input_type == "invalid":
        raise ValueError(f"无效的输入: {input_value}")

    if input_type == "csv_file":
        plan_logger.info(f"检测到CSV文件输入: {input_value}")
        if column is None:
            try:
                detected_column = auto_detect_column(input_value)
            except Exception as exc:
                plan_logger.error(f"自动检测列名失败: {exc}")
                detected_column = None
            if detected_column:
                plan_logger.info(f"自动检测到列名: {detected_column}")
                column = detected_column
            else:
                raise ValueError(f"无法自动检测CSV列名: {input_value}")

        identifiers = read_identifier_values_from_csv(input_value, column)
        papers = build_papers_from_identifiers(identifiers)
        if limit is not None and limit > 0:
            papers = papers[:limit]
        return build_download_plan(papers, source="unified_input", resolver=resolver)

    if input_type in ["single", "multiple"]:
        identifiers = parse_identifier_string(input_value)
        if not identifiers:
            raise ValueError(f"未找到有效的标识符: {input_value}")

        plan_logger.info(f"检测到 {len(identifiers)} 个标识符")
        papers = build_papers_from_identifiers(identifiers)
        if limit:
            papers = papers[:limit]
        return build_download_plan(papers, source="unified_input", resolver=resolver)

    raise ValueError(f"未知的输入类型: {input_type}")
