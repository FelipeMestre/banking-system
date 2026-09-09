"""RED for the job sink for withdrawal-status — mirrors test_job_deposit_sink.py."""

import pathlib


def test_withdrawal_status_tag_exists():
    text = pathlib.Path("account-service/job.py").read_text()
    assert "WITHDRAWAL_STATUS_TAG" in text
    assert "WITHDRAWAL_STATUS_TOPIC" in text
    assert "withdrawal-status" in text
    assert "OutputTag" in text
    assert "withdrawal-status-events" in text


def test_process_element_routes_withdrawal():
    text = pathlib.Path("account-service/job.py").read_text()
    assert "WITHDRAWAL_STATUS_TAG" in text
    assert "WITHDRAWAL_STATUS_TOPIC" in text
    assert "process_element" in text
    assert "withdrawal_status_events" in text
    assert "_kafka_sink(WITHDRAWAL_STATUS_TOPIC)" in text or "WITHDRAWAL_STATUS_TOPIC" in text
    assert "get_side_output(WITHDRAWAL_STATUS_TAG)" in text
    assert "Row" in text
