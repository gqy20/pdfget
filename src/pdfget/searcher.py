"""
Paper search module.

Supports searching across multiple scholarly data sources.
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests

from .base.ncbi_base import NCBIBaseModule
from .config import DEFAULT_SOURCE, NCBI_API_KEY, NCBI_EMAIL


class PaperSearcher(NCBIBaseModule):
    """Search papers across supported sources."""

    def __init__(
        self,
        session: requests.Session,
        email: str = "",
        api_key: str = "",
    ):
        email = email or NCBI_EMAIL
        api_key = api_key or NCBI_API_KEY
        super().__init__(session=session, email=email, api_key=api_key)
        self.europe_pmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest"
        self.default_source = DEFAULT_SOURCE

    def _parse_query_pubmed(self, query: str) -> str:
        if "year:" in query:
            year_match = re.search(r"year:(\d{4})", query)
            if year_match:
                year = year_match.group(1)
                query = query.replace(f"year:{year}", f"{year}[pdat]")

        if "journal:" in query:
            journal_match = re.search(r"journal:([^\s]+)", query)
            if journal_match:
                journal = journal_match.group(1)
                query = query.replace(f"journal:{journal}", f'"{journal}"[TA]')

        if "author:" in query:
            author_match = re.search(r"author:([^\s]+)", query)
            if author_match:
                author = author_match.group(1)
                query = query.replace(f"author:{author}", f"{author}[AU]")

        return query

    def _parse_query_europepmc(self, query: str) -> str:
        if "year:" in query:
            year_match = re.search(r"year:(\d{4})", query)
            if year_match:
                year = year_match.group(1)
                query = query.replace(f"year:{year}", f"FIRST_PDATE:{year}")
        return query

    def _normalize_paper_data(
        self, paper: dict[str, Any], source: str
    ) -> dict[str, Any]:
        normalized = {
            "pmid": paper.get("pmid", ""),
            "doi": paper.get("doi", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "journal": paper.get("journal", ""),
            "year": paper.get("year", ""),
            "abstract": paper.get("abstract", ""),
            "source": source,
            "pmcid": paper.get("pmcid", ""),
            "inPMC": paper.get("inPMC", ""),
            "arxiv_id": paper.get("arxiv_id", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "repository": paper.get("repository", ""),
            "download_type": paper.get("download_type", ""),
        }

        if isinstance(normalized["authors"], str):
            normalized["authors"] = [normalized["authors"]]

        if normalized["year"]:
            year_match = re.search(r"\d{4}", str(normalized["year"]))
            normalized["year"] = year_match.group() if year_match else ""

        return normalized

    def _search_pubmed_api(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            self._rate_limit()
            search_response = self.session.get(
                f"{self.base_url}esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": limit,
                    **({"email": self.email} if self.email else {}),
                    **({"api_key": self.api_key} if self.api_key else {}),
                },
                timeout=self.config["timeouts"]["request"],
            )
            search_response.raise_for_status()
            pmids = search_response.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            all_batches = []
            batch_size = 50
            for i in range(0, len(pmids), batch_size):
                batch_pmids = pmids[i : i + batch_size]
                self._rate_limit()
                summary_response = self.session.get(
                    f"{self.base_url}esummary.fcgi",
                    params={
                        "db": "pubmed",
                        "id": ",".join(batch_pmids),
                        "retmode": "json",
                        **({"email": self.email} if self.email else {}),
                        **({"api_key": self.api_key} if self.api_key else {}),
                    },
                    timeout=self.config["timeouts"]["request"],
                )
                summary_response.raise_for_status()
                all_batches.append(summary_response.json())

            papers: list[dict[str, Any]] = []
            for pmid in pmids:
                article_data = None
                for batch_data in all_batches:
                    article_data = batch_data.get("result", {}).get(pmid)
                    if article_data:
                        break

                if not article_data:
                    continue

                authors = [
                    author["name"]
                    for author in article_data.get("authors", [])
                    if "name" in author
                ]
                pubdate = article_data.get("pubdate", "")
                year_match = re.search(r"\d{4}", pubdate)
                year = year_match.group() if year_match else ""
                doi = ""
                for aid in article_data.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                        break

                papers.append(
                    self._normalize_paper_data(
                        {
                            "pmid": pmid,
                            "doi": doi,
                            "title": article_data.get("title", ""),
                            "authors": authors,
                            "journal": article_data.get("fulljournalname", ""),
                            "year": year,
                            "abstract": "",
                        },
                        "pubmed",
                    )
                )

            return papers
        except requests.exceptions.Timeout:
            self.logger.error("PubMed search timed out")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PubMed search request failed: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"PubMed search error: {str(e)}")
            return []

    def _search_europepmc_api(
        self, query: str, limit: int = 50, require_pmcid: bool = False
    ) -> list[dict[str, Any]]:
        try:
            search_url = f"{self.europe_pmc_url}/search"
            all_papers: list[dict[str, Any]] = []
            cursor_mark = "*"
            page_size = min(500, limit)
            total_fetched = 0

            full_query = f"({query}) AND pmcid:*" if require_pmcid and query.strip() else query
            if require_pmcid and not query.strip():
                full_query = "pmcid:*"

            while total_fetched < limit:
                response = self.session.get(
                    search_url,
                    params={
                        "query": full_query,
                        "resulttype": "core",
                        "format": "json",
                        "pageSize": page_size,
                        "cursorMark": cursor_mark,
                        "synonym": "true",
                        "fields": (
                            "pmid,doi,title,authorString,journalTitle,pubYear,"
                            "abstractText,pmcid,inPMC,source"
                        ),
                    },
                    timeout=self.config["timeouts"]["request"],
                )
                response.raise_for_status()
                data = response.json()

                for item in data.get("resultList", {}).get("result", []):
                    authors = [
                        author.strip()
                        for author in item.get("authorString", "").split(";")
                        if author.strip()
                    ]
                    all_papers.append(
                        self._normalize_paper_data(
                            {
                                "pmid": item.get("pmid", ""),
                                "doi": item.get("doi", ""),
                                "title": item.get("title", ""),
                                "authors": authors,
                                "journal": item.get("journalTitle", ""),
                                "year": str(item.get("pubYear", "")),
                                "abstract": item.get("abstractText", ""),
                                "pmcid": item.get("pmcid", ""),
                                "inPMC": item.get("inPMC", ""),
                            },
                            "europe_pmc",
                        )
                    )

                total_fetched = len(all_papers)
                next_cursor_mark = data.get("nextCursorMark", "")
                if not next_cursor_mark or next_cursor_mark == cursor_mark:
                    break
                cursor_mark = next_cursor_mark
                remaining = limit - total_fetched
                if remaining < page_size:
                    page_size = remaining
                time.sleep(0.1)

            return all_papers[:limit]
        except requests.exceptions.Timeout:
            self.logger.error("Europe PMC search timed out")
            return []
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Europe PMC search request failed: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Europe PMC search error: {str(e)}")
            return []

    def _search_arxiv_api(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        try:
            time.sleep(3.0)
            response = self.session.get(
                "http://export.arxiv.org/api/query",
                params={
                    "search_query": f"all:{query}" if query.strip() else "all:*",
                    "start": 0,
                    "max_results": limit,
                },
                timeout=self.config["timeouts"]["request"],
            )
            response.raise_for_status()

            namespace = {
                "atom": "http://www.w3.org/2005/Atom",
                "arxiv": "http://arxiv.org/schemas/atom",
            }
            root = ET.fromstring(response.text)
            papers: list[dict[str, Any]] = []

            for entry in root.findall("atom:entry", namespace):
                entry_id = entry.findtext("atom:id", default="", namespaces=namespace)
                arxiv_id = entry_id.rsplit("/", 1)[-1] if entry_id else ""
                title = " ".join(
                    entry.findtext("atom:title", default="", namespaces=namespace).split()
                )
                abstract = " ".join(
                    entry.findtext("atom:summary", default="", namespaces=namespace).split()
                )
                published = entry.findtext(
                    "atom:published", default="", namespaces=namespace
                )
                authors = [
                    author.text.strip()
                    for author in entry.findall("atom:author/atom:name", namespace)
                    if author.text
                ]
                doi = entry.findtext("arxiv:doi", default="", namespaces=namespace)

                pdf_url = ""
                for link in entry.findall("atom:link", namespace):
                    if (
                        link.attrib.get("title") == "pdf"
                        or link.attrib.get("type") == "application/pdf"
                    ):
                        pdf_url = link.attrib.get("href", "")
                        break

                papers.append(
                    self._normalize_paper_data(
                        {
                            "pmid": "",
                            "doi": doi,
                            "title": title,
                            "authors": authors,
                            "journal": "",
                            "year": published[:4] if published else "",
                            "abstract": abstract,
                            "pmcid": "",
                            "inPMC": "",
                            "arxiv_id": arxiv_id,
                            "pdf_url": pdf_url,
                            "repository": "arxiv",
                            "download_type": "arxiv",
                        },
                        "arxiv",
                    )
                )

            return papers
        except requests.exceptions.Timeout:
            self.logger.error("arXiv search timed out")
            return []
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            self.logger.error(f"arXiv search failed: {str(e)}")
            return []

    def search_pubmed(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        self.logger.info(f"Searching papers (PubMed): {query}")
        papers = self._search_pubmed_api(self._parse_query_pubmed(query), limit)
        return papers

    def search_europepmc(
        self, query: str, limit: int = 50, require_pmcid: bool = False
    ) -> list[dict[str, Any]]:
        self.logger.info(f"Searching papers (Europe PMC): {query}")
        papers = self._search_europepmc_api(
            self._parse_query_europepmc(query), limit, require_pmcid=require_pmcid
        )
        return papers

    def search_arxiv(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        self.logger.info(f"Searching papers (arXiv): {query}")
        return self._search_arxiv_api(query, limit)

    def search_all_sources(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        all_papers = []
        all_papers.extend(self.search_pubmed(query, limit))
        all_papers.extend(self.search_europepmc(query, limit))

        seen_pmids: set[str] = set()
        unique_papers: list[dict[str, Any]] = []
        for paper in all_papers:
            pmid = paper.get("pmid", "")
            if pmid:
                if pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    unique_papers.append(paper)
            else:
                unique_papers.append(paper)
        return unique_papers

    def search_papers(
        self, query: str, limit: int = 50, source: str | None = None
    ) -> list[dict[str, Any]]:
        source = source or self.default_source

        if source == "pubmed":
            return self.search_pubmed(query, limit)
        if source == "europe_pmc":
            return self.search_europepmc(query, limit)
        if source == "arxiv":
            return self.search_arxiv(query, limit)
        if source == "both":
            return self.search_all_sources(query, limit)

        self.logger.warning(f"Unknown data source: {source}, falling back to default")
        return self.search_pubmed(query, limit)
