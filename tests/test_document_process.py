"""Document parsers are isolated from web workers and cannot run indefinitely."""

import time

import pytest

from app import documents
from .test_bills import PNG, pdf


@pytest.mark.parametrize("data,kind,pages", [(PNG, "png", 1), (pdf(2), "pdf", 2)])
def test_real_parser_subprocess(data, kind, pages):
    result = documents.inspect_bounded(data)
    assert result["kind"] == kind and result["page_count"] == pages


def test_parser_process_deadline_kills_a_stuck_parser(tmp_path, monkeypatch):
    script = tmp_path / "stuck_parser.py"
    script.write_text("import time\ntime.sleep(30)\n")
    monkeypatch.setattr(documents, "PARSER_SCRIPT", script)
    monkeypatch.setattr(documents, "PARSE_SECONDS", 0.1)
    started = time.monotonic()
    with pytest.raises(documents.UploadError, match="too long"):
        documents.inspect_bounded(PNG)
    assert time.monotonic() - started < 5


def test_corrupt_document_is_not_accepted_by_subprocess():
    with pytest.raises(documents.UploadError, match="damaged"):
        documents.inspect_bounded(b"%PDF-1.7\ninvalid")
