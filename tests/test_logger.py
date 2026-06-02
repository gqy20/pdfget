import json

from pdfget.logger import configure_logging, get_logger


def test_json_logging_writes_structured_records_to_stderr(capsys):
    configure_logging(level="INFO", log_format="json", force=True)
    logger = get_logger("tests.logger.json")

    logger.info("download_start", pmcid="PMC123", source="pmc")

    captured = capsys.readouterr()
    assert captured.out == ""

    record = json.loads(captured.err)
    assert record["message"] == "download_start"
    assert record["pmcid"] == "PMC123"
    assert record["source"] == "pmc"
    assert record["level"] == "info"
    assert record["logger"] == "tests.logger.json"
    assert "timestamp" in record


def test_quiet_logging_suppresses_non_error_records(capsys):
    configure_logging(level="DEBUG", log_format="json", quiet=True, force=True)
    logger = get_logger("tests.logger.quiet")

    logger.warning("should_not_be_emitted")
    logger.error("should_be_emitted", code="download_failed")

    captured = capsys.readouterr()
    records = [
        json.loads(line)
        for line in captured.err.splitlines()
        if line.strip()
    ]

    assert [record["message"] for record in records] == ["should_be_emitted"]
    assert records[0]["code"] == "download_failed"
