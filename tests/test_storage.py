"""Tests for the LocalPDFStore abstraction."""

from __future__ import annotations

import time
from pathlib import Path

from pdfget.storage import LocalPDFStore


def _record(**overrides):
    base = {"pmcid": "PMC123456", "doi": "10.1000/test", "arxiv_id": ""}
    base.update(overrides)
    return base


class TestLocalPDFStore:
    def test_path_for_with_pmcid_and_doi(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        path = store.path_for(_record())
        assert path.parent == tmp_path
        assert path.name.startswith("PMC123456_")
        assert path.name.endswith(".pdf")

    def test_path_for_with_only_pmcid(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        path = store.path_for({"pmcid": "PMC999", "doi": "", "arxiv_id": ""})
        assert path.name == "PMC999.pdf"

    def test_path_for_with_only_arxiv_id(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        path = store.path_for({"pmcid": "", "doi": "", "arxiv_id": "2301.12345"})
        assert path.name == "2301.12345.pdf"

    def test_path_for_falls_back_to_paper_pdf(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        path = store.path_for({"pmcid": "", "doi": "", "arxiv_id": ""})
        assert path.name == "paper.pdf"

    def test_has_roundtrip(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        record = _record()
        assert store.has(record) is False
        store.path_for(record).write_bytes(b"%PDF-1.4 fake")
        assert store.has(record) is True

    def test_open_writer_writes_and_cleans_up_on_error(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        record = _record()

        with store.open_writer(record) as fp:
            fp.write(b"%PDF-1.4 hello")
        assert store.path_for(record).exists()

        # Failure path: file should be removed
        bad_path = store.path_for(_record(pmcid="PMC777"))
        try:
            with store.open_writer(_record(pmcid="PMC777")) as fp:
                fp.write(b"partial")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert not bad_path.exists()

    def test_list_records_collects_metadata(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        (tmp_path / "PMC111.pdf").write_bytes(b"a")
        (tmp_path / "PMC222_10-1000-xyz.pdf").write_bytes(b"bbb")

        records = store.list_records()
        assert sorted(records) == ["PMC111.pdf", "PMC222_10-1000-xyz.pdf"]
        assert records["PMC111.pdf"]["pmcid"] == "PMC111"
        assert records["PMC111.pdf"]["size"] == 1

    def test_cleanup_older_than_removes_old_files(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        old = tmp_path / "PMC_old.pdf"
        old.write_bytes(b"x")
        old_time = time.time() - 10 * 24 * 3600  # 10 days ago
        import os

        os.utime(old, (old_time, old_time))

        new = tmp_path / "PMC_new.pdf"
        new.write_bytes(b"x")

        deleted = store.cleanup_older_than(max_age_days=5)
        assert deleted == 1
        assert not old.exists()
        assert new.exists()

    def test_cache_info_aggregates(self, tmp_path: Path):
        store = LocalPDFStore(tmp_path)
        (tmp_path / "PMC1.pdf").write_bytes(b"a")
        (tmp_path / "PMC2.pdf").write_bytes(b"bb")

        info = store.cache_info()
        assert info["file_count"] == 2
        assert info["total_size_bytes"] == 3
        assert info["total_size_mb"] >= 0
        assert info["output_dir"] == str(tmp_path)
