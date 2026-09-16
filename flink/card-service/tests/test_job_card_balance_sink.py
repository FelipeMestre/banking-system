"""RED for Flink job card-balances sink (task 3.3)."""
from __future__ import annotations

import json


def test_card_balances_tag_and_topic_exist():
    import importlib.util
    from pathlib import Path

    job_path = Path(__file__).resolve().parents[1] / "job.py"
    spec = importlib.util.spec_from_file_location("card_job", job_path)
    mod = importlib.util.module_from_spec(spec)
    # Don't execute full build_job, just load module
    import sys

    # Mock flink dependencies minimally to allow import
    # But easier: read source text
    text = job_path.read_text()
    assert "CARD_BALANCES_TAG" in text, "CARD_BALANCES_TAG missing"
    assert "CARD_BALANCES_TOPIC" in text, "CARD_BALANCES_TOPIC missing"
    assert "card-balances" in text, "default topic card-balances missing"
    # check OutputTag name
    assert 'OutputTag("card-balance-events"' in text or "OutputTag('card-balance-events'" in text
    # check Row shape
    assert "Row(card_account_id" in text
    assert "json.dumps" in text
    # check AT_LEAST_ONCE
    assert "AT_LEAST_ONCE" in text
    # check sink usage
    assert "get_side_output(CARD_BALANCES_TAG)" in text
    assert "_kafka_sink(CARD_BALANCES_TOPIC" in text


def test_card_balance_row_keyed_and_sink_config():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "job.py").read_text()
    # Row[kafka_key,payload] and RECORD_TYPE
    assert "RECORD_TYPE" in text
    # Check that CardProcessor yields CARD_BALANCES_TAG
    assert "CARD_BALANCES_TAG, Row(" in text
    # Ensure murmur2 comment or partitioner not configured (design says no partitioner config)
    assert "murmur2" in text.lower() or "No partitioner" in text
