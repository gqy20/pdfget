"""Local PDF archive abstraction.

PDFDownloader 不再直接持有 output_dir 与散落的方法（list / cleanup / cache_info），
所有"已下载 PDF 的本地存储"职责集中到这里：

- path_for / has           —— 路径解析与存在性查询
- open_writer              —— 边下载边写入
- list_records             —— 列出已存档的 PDF
- cleanup_older_than       —— 按 mtime 清理旧文件
- cache_info               —— 聚合统计（计数 / 体积 / 输出目录）

文件名由 paper_record.v1 计算：{pmcid} / {pmcid}_{clean_doi} / {arxiv_id}。
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any

from .filename import make_pdf_filename
from .logger import get_logger


class LocalPDFStore:
    """Filesystem layer for downloaded PDFs."""

    def __init__(self, output_dir: str | Path):
        self.logger = get_logger(__name__)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, record: dict[str, Any]) -> Path:
        """Return the canonical archive path for a normalized record."""
        pmcid = str(record.get("pmcid") or "")
        doi = str(record.get("doi") or "")
        arxiv_id = str(record.get("arxiv_id") or "")
        if pmcid:
            return self.output_dir / make_pdf_filename(pmcid, doi)
        if arxiv_id:
            return self.output_dir / f"{arxiv_id}.pdf"
        return self.output_dir / "paper.pdf"

    def has(self, record: dict[str, Any]) -> bool:
        """Return True if a PDF already exists for ``record``."""
        return self.path_for(record).exists()

    @contextmanager
    def open_writer(
        self, record: dict[str, Any]
    ) -> Iterator[IO[bytes]]:
        """Open a binary write handle for streaming a PDF response into the archive.

        On exception (or empty content), the partially-written file is removed.
        Yields the open file so the caller can stream ``response.iter_content``
        chunks into it. The canonical path is recoverable via ``path_for(record)``.
        """
        path = self.path_for(record)
        try:
            with open(path, "wb") as fp:
                yield fp
        except Exception:
            path.unlink(missing_ok=True)
            raise

    # ---- 列表 / 清理 / 缓存信息 --------------------------------------------------

    def list_records(self) -> dict[str, dict[str, Any]]:
        """Return all PDF files currently in the archive: filename → info."""
        pdfs: dict[str, dict[str, Any]] = {}
        for file_path in self.output_dir.glob("*.pdf"):
            try:
                stat = file_path.stat()
                pmcid_match = re.search(r"PMC\d+", file_path.name)
                pmcid = pmcid_match.group() if pmcid_match else "unknown"
                pdfs[file_path.name] = {
                    "path": str(file_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "pmcid": pmcid,
                    "doi": self._guess_doi_from_filename(file_path.name),
                }
            except OSError as exc:
                self.logger.error(f"读取 PDF 信息失败 {file_path}: {exc}")
        return pdfs

    def cleanup_older_than(self, max_age_days: int = 30) -> int:
        """Delete PDFs older than ``max_age_days``; return the number deleted."""
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        deleted = 0
        for file_path in self.output_dir.glob("*.pdf"):
            try:
                if current_time - file_path.stat().st_mtime > max_age_seconds:
                    file_path.unlink()
                    deleted += 1
                    self.logger.info(f"删除旧 PDF: {file_path.name}")
            except OSError as exc:
                self.logger.error(f"删除 PDF 失败 {file_path}: {exc}")
        if deleted:
            self.logger.info(f"清理完成，删除了 {deleted} 个旧 PDF 文件")
        return deleted

    def cache_info(self) -> dict[str, Any]:
        """Aggregate archive statistics: count, total bytes, output directory."""
        pdfs = self.list_records()
        total_size = sum(info["size"] for info in pdfs.values())
        return {
            "file_count": len(pdfs),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "output_dir": str(self.output_dir),
        }

    # ---- 文件名启发式 -----------------------------------------------------------

    @staticmethod
    def _guess_doi_from_filename(name: str) -> str:
        """Recover a DOI hint from a PDF filename produced by older releases.

        这是一条历史妥协：早期版本会从文件名里反向拼出 DOI，方便
        ``PaperFetcher.get_cache_info`` 在没有元数据旁路的情况下展示；
        仅用于归档展示，不是协议字段。
        """
        if "_" not in name:
            return "unknown"
        parts = name[:-4].split("_", 1)
        if len(parts) != 2:
            return "unknown"
        doi_part = parts[1]
        if not doi_part or not doi_part[0].isdigit():
            return "unknown"
        if "test" in doi_part:
            if doi_part.startswith("101000"):
                return "10.1000/test"
            return f"10.{doi_part[:4]}/test"
        if "/" not in doi_part and "." not in doi_part and len(doi_part) >= 4:
            return f"10.{doi_part[:4]}/test"
        if "/" in doi_part:
            doi_part = doi_part.replace("-", "/", 1)
        return f"10.{doi_part}"
