"""PDF downloader — single public entry: ``PDFDownloader.download_paper``.

The class is responsible for one thing: given a normalized paper record,
try the configured download sources in priority order and persist a PDF
on disk. Filesystem concerns (path resolution, listing, cache info,
cleanup, atomic write) live in :class:`pdfget.storage.LocalPDFStore`;
this module owns protocol I/O and attempt aggregation only.
"""

from __future__ import annotations

from typing import Any

import requests

from .logger import get_logger
from .paper_schema import normalize_paper_record
from .pmc_oa_service import PMCOAService
from .retry import retry_with_backoff
from .storage import LocalPDFStore


class PDFDownloader:
    """Download one normalized paper record per call.

    Public API:

    - ``download_paper(record)`` — the only download entry point.

    All other methods are private strategy/internal helpers and may
    change between releases without notice.
    """

    DOWNLOAD_CHUNK_SIZE = 8192

    def __init__(
        self,
        output_dir: str,
        session: requests.Session,
        source_priority: list[str] | None = None,
    ):
        self.logger = get_logger(__name__)
        self.session = session
        self.source_priority = source_priority or [
            "pmc",
            "europe_pmc",
            "arxiv",
            "direct",
        ]
        self.store = LocalPDFStore(output_dir)
        self.pmc_oa_service = PMCOAService(str(self.store.output_dir), session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_paper(self, paper: dict[str, Any]) -> dict[str, Any]:
        """Try each configured source in priority order; return the first success.

        ``paper`` is any dict with at least one of ``pmcid``, ``doi``,
        ``arxiv_id``, ``pdf_url``. The function normalizes it via
        ``paper_schema.normalize_paper_record`` before dispatch.
        """
        record = normalize_paper_record(paper, str(paper.get("source") or ""))
        for source in self.source_priority:
            if source in {"pmc", "europe_pmc"} and record.get("pmcid"):
                return self._via_pmcid(record)
            if source == "arxiv" and record.get("arxiv_id"):
                return self._via_arxiv(record)
            if source == "direct" and record.get("pdf_url"):
                return self._via_direct(record)
        return self._build_result(
            success=False,
            stage="resolve_identifier",
            source="resolver",
            error="No downloadable identifier found",
            attempts=[
                {
                    "source": "resolver",
                    "success": False,
                    "stage": "resolve_identifier",
                    "error": "No downloadable identifier found",
                }
            ],
        )

    # ------------------------------------------------------------------
    # Per-source strategies
    # ------------------------------------------------------------------

    def _via_pmcid(self, record: dict[str, Any]) -> dict[str, Any]:
        """PMC → Europe PMC URL fallback, with cache-hit short-circuit."""
        if self.store.has(record):
            path = self.store.path_for(record)
            self.logger.info(f"PDF 已存在: {path}")
            return self._build_result(
                success=True,
                stage="cache_hit",
                source="cache",
                path=str(path),
                pmcid=record.get("pmcid", ""),
                doi=record.get("doi", ""),
                message="PDF 已存在，无需重新下载",
                skipped_existing=True,
                attempts=[
                    {
                        "source": "cache",
                        "success": True,
                        "stage": "cache_hit",
                        "path": str(path),
                    }
                ],
            )

        pmcid = self._normalize_pmcid(record.get("pmcid", ""))
        doi = record.get("doi", "")
        attempts: list[dict[str, Any]] = []

        for source in self._allowed_sources(["pmc", "europe_pmc"]):
            if source == "pmc":
                attempts.append(
                    self._try_pmc_oa(pmcid, doi, record.get("arxiv_id", ""))
                )
                last = attempts[-1]
                if last["success"]:
                    return self._build_result(
                        success=True,
                        stage="download_pdf",
                        source=last.get("source", "pmc"),
                        path=str(self.store.path_for(record)),
                        pmcid=pmcid,
                        doi=doi,
                        content_length=last.get("content_length") or 0,
                        attempts=attempts,
                    )
                continue

            for source_name, url_template in self.pdf_sources:
                if source_name != source:
                    continue
                url = url_template.format(pmcid=pmcid)
                result = self._try_download_from_url(url, pmcid, doi)
                attempts.append(self._attempt_from_result(source_name, result, url=url))
                if result["success"]:
                    self.logger.info(f"PDF 下载成功（{source_name}）")
                    result["source"] = source_name
                    result["attempts"] = attempts
                    return result
                self.logger.debug(
                    f"{source_name} 失败: {result.get('error', '未知错误')}"
                )

        error_msg = f"所有 {len(attempts)} 个 PDF 源都失败"
        self.logger.error(error_msg)
        return self._build_result(
            success=False,
            stage="download_pdf",
            source="pmc",
            error=error_msg,
            pmcid=pmcid,
            doi=doi,
            attempts=attempts,
        )

    def _via_arxiv(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_arxiv_id(record.get("arxiv_id", ""))
        url = f"https://arxiv.org/pdf/{normalized}.pdf"
        result = self._try_download_from_url(url, normalized, "")
        result["arxiv_id"] = normalized
        result["source"] = "arxiv"
        result["attempts"] = [self._attempt_from_result("arxiv", result, url=url)]
        return result

    def _via_direct(self, record: dict[str, Any]) -> dict[str, Any]:
        pdf_url = record.get("pdf_url", "")
        name = record.get("identifier") or record.get("title", "paper")
        result = self._try_download_from_url(pdf_url, name, record.get("doi", ""))
        result["pdf_url"] = pdf_url
        result["source"] = "direct"
        result["attempts"] = [
            self._attempt_from_result("direct", result, url=pdf_url)
        ]
        return result

    # ------------------------------------------------------------------
    # PMC OA + URL strategies
    # ------------------------------------------------------------------

    @property
    def pdf_sources(self) -> list[tuple[str, str]]:
        return self._pdf_sources

    _pdf_sources: list[tuple[str, str]] = [
        ("europe_pmc", "https://europepmc.org/articles/{pmcid}?pdf=render"),
    ]

    def _allowed_sources(self, candidates: list[str]) -> list[str]:
        return [source for source in self.source_priority if source in candidates]

    def _try_pmc_oa(
        self, pmcid: str, doi: str, arxiv_id: str
    ) -> dict[str, Any]:
        """Drive the PMC OA Service; returns an attempt dict."""
        self.logger.info("尝试 PMC OA Service")
        try:
            processed = self.pmc_oa_service.process_pmcid(pmcid, doi)
        except Exception as exc:
            self.logger.info(f"PMC OA Service 抛错: {exc}")
            return {
                "source": "PMC OA Service",
                "success": False,
                "stage": "download_pdf",
                "error": f"PMC OA Service 异常: {exc}",
            }

        if not processed:
            self.logger.info("PMC OA Service 失败，尝试其他源")
            return {
                "source": "PMC OA Service",
                "success": False,
                "stage": "download_pdf",
                "error": "PMC OA Service 失败",
            }

        record = {"pmcid": pmcid, "doi": doi, "arxiv_id": arxiv_id}
        path = self.store.path_for(record)
        if not path.exists():
            candidates = list(self.store.output_dir.glob(f"{pmcid}*/**/*.pdf"))
            if candidates:
                path.rename(self.store.output_dir / path.name)

        if path.exists():
            self.logger.info(f"PDF 下载成功（PMC OA Service）: {path}")
            return {
                "source": "PMC OA Service",
                "success": True,
                "stage": "download_pdf",
                "path": str(path),
                "content_length": path.stat().st_size,
            }
        return {
            "source": "PMC OA Service",
            "success": False,
            "stage": "download_pdf",
            "error": "PMC OA Service 处理成功但未找到PDF文件",
        }

    def _try_download_from_url(
        self, url: str, pmcid: str, doi: str
    ) -> dict[str, Any]:
        """Stream one URL into the archive; returns the unified result dict."""
        try:
            self.logger.debug(f"尝试下载 PDF: {url}")
            response = self._download_with_retry(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if "application/pdf" not in content_type:
                self.logger.debug(f"不是 PDF 文件: {content_type}")
                return self._build_result(
                    success=False,
                    stage="validate_response",
                    source="url",
                    error=f"不是 PDF 文件 (content-type: {content_type})",
                    pmcid=pmcid if pmcid.startswith("PMC") else "",
                    doi=doi,
                    source_url=url,
                    content_type=content_type,
                )

            save_result = self._save_pdf_stream(response, pmcid, doi)
            if not pmcid.startswith("PMC"):
                save_result.pop("pmcid", None)
            if save_result["success"]:
                save_result["source_url"] = url
                save_result["content_type"] = content_type
                save_result["source"] = "url"
            return save_result

        except requests.exceptions.Timeout:
            return self._build_result(
                success=False,
                stage="download_pdf",
                source="url",
                error="下载超时",
                pmcid=pmcid if pmcid.startswith("PMC") else "",
                doi=doi,
                source_url=url,
            )
        except requests.exceptions.RequestException as e:
            return self._build_result(
                success=False,
                stage="download_pdf",
                source="url",
                error=f"下载失败: {e}",
                pmcid=pmcid if pmcid.startswith("PMC") else "",
                doi=doi,
                source_url=url,
            )
        except Exception as e:
            return self._build_result(
                success=False,
                stage="download_pdf",
                source="url",
                error=f"未知错误: {e}",
                pmcid=pmcid if pmcid.startswith("PMC") else "",
                doi=doi,
                source_url=url,
            )

    def _save_pdf_stream(
        self, response: requests.Response, pmcid: str, doi: str
    ) -> dict[str, Any]:
        """Save a PDF response incrementally through the LocalPDFStore."""
        record = {"pmcid": pmcid, "doi": doi, "arxiv_id": ""}
        path = self.store.path_for(record)
        content_length = 0

        try:
            with self.store.open_writer(record) as fp:
                for chunk in response.iter_content(chunk_size=self.DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    content_length += len(chunk)

            if content_length == 0:
                path.unlink(missing_ok=True)
                return self._build_result(
                    success=False,
                    stage="save_file",
                    source="file",
                    path=str(path),
                    error="PDF 内容为空",
                    pmcid=pmcid,
                    doi=doi,
                )
            self.logger.info(f"PDF 保存成功: {path}")
            return self._build_result(
                success=True,
                stage="save_file",
                source="file",
                path=str(path),
                pmcid=pmcid,
                doi=doi,
                content_length=content_length,
            )
        except Exception as e:
            self.logger.error(f"PDF 保存失败: {e}")
            return self._build_result(
                success=False,
                stage="save_file",
                source="file",
                path=str(path),
                error=str(e),
                pmcid=pmcid,
                doi=doi,
            )

    # ------------------------------------------------------------------
    # Result / retry helpers (private)
    # ------------------------------------------------------------------

    def _build_result(
        self,
        *,
        success: bool,
        stage: str,
        source: str = "",
        path: str = "",
        error: str = "",
        message: str = "",
        pmcid: str = "",
        doi: str = "",
        arxiv_id: str = "",
        pdf_url: str = "",
        source_url: str = "",
        content_type: str = "",
        content_length: int | None = None,
        skipped_existing: bool = False,
        attempts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build the canonical download_result.v1 record."""
        result: dict[str, Any] = {
            "success": success,
            "stage": stage,
            "source": source,
            "path": path,
            "error": error,
        }
        if message:
            result["message"] = message
        if pmcid:
            result["pmcid"] = pmcid
        if doi:
            result["doi"] = doi
        if arxiv_id:
            result["arxiv_id"] = arxiv_id
        if pdf_url:
            result["pdf_url"] = pdf_url
        if source_url:
            result["source_url"] = source_url
        if content_type:
            result["content_type"] = content_type
        if content_length is not None:
            result["content_length"] = content_length
        if skipped_existing:
            result["skipped_existing"] = skipped_existing
        if attempts:
            result["attempts"] = attempts
        return result

    def _attempt_from_result(
        self, source: str, result: dict[str, Any], url: str = ""
    ) -> dict[str, Any]:
        attempt: dict[str, Any] = {
            "source": source,
            "success": result.get("success", False),
            "stage": result.get("stage", ""),
        }
        if result.get("error"):
            attempt["error"] = result["error"]
        if url:
            attempt["url"] = url
        if result.get("content_type"):
            attempt["content_type"] = result["content_type"]
        if result.get("path"):
            attempt["path"] = result["path"]
        return attempt

    def _download_with_retry(self, url: str) -> requests.Response:
        retry = retry_with_backoff()

        @retry
        def _fetch() -> requests.Response:
            return self.session.get(url, timeout=30, stream=True)

        return _fetch()

    # ------------------------------------------------------------------
    # Identifier normalization helpers (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_pmcid(value: str) -> str:
        """Make sure ``PMC`` prefix is present."""
        if not value:
            return ""
        return value if value.startswith("PMC") else f"PMC{value}"

    @staticmethod
    def _normalize_arxiv_id(value: str) -> str:
        stripped = (value or "").strip()
        if stripped.lower().startswith("arxiv:"):
            return stripped[6:].strip()
        return stripped
