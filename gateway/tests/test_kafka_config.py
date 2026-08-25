"""The gateway and the Flink sink must agree on how keys map to partitions."""
from gateway.config import Settings
from gateway.kafka_config import producer_config


def test_producer_uses_the_java_compatible_partitioner():
    """librdkafka's default is CRC32; the Java client Flink uses is murmur2.

    Disagreeing here splits one account's events across partitions, which
    silently destroys the per-account ordering guarantee.
    """
    assert producer_config(Settings(), client_id="x")["partitioner"] == "murmur2_random"


def test_producer_is_idempotent():
    config = producer_config(Settings(), client_id="x")
    assert config["enable.idempotence"] is True
    assert config["acks"] == "all"


def test_client_id_is_passed_through():
    assert producer_config(Settings(), client_id="gateway-seed")["client.id"] == "gateway-seed"
