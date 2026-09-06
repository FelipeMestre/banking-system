"""RED for Task 4.3 — job sink for deposit-status."""

import json
import pathlib


def test_deposit_status_tag_exists():
    text = pathlib.Path("account-service/job.py").read_text()
    assert "DEPOSIT_STATUS_TAG" in text
    assert "DEPOSIT_STATUS_TOPIC" in text
    assert 'deposit-status' in text
    assert "OutputTag" in text
    assert "deposit-status-events" in text
    assert 'DEPOSIT_STATUS_TOPIC' in text


def test_process_element_routes_deposit():
    import pathlib

    text = pathlib.Path("account-service/job.py").read_text()
    assert "DEPOSIT_STATUS_TAG" in text
    assert "DEPOSIT_STATUS_TOPIC" in text
    # process_element should yield to DEPOSIT_STATUS_TAG and handle deposit
    assert "process_element" in text
    assert "deposit" in text.lower()
    # must sink to deposit-status topic via _kafka_sink
    assert "_kafka_sink(DEPOSIT_STATUS_TOPIC)" in text or "DEPOSIT_STATUS_TOPIC" in text
    # must route status_events with new_balance
    assert "new_balance" in text
    # ensure side output sink configured
    assert "get_side_output(DEPOSIT_STATUS_TAG)" in text
    # Check that sink uses Row(request_id, json.dumps(status))
    assert "Row" in text
