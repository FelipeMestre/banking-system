"""The gateway and the Flink sink must agree on how keys map to partitions."""
from openbankapi.config import Settings
from openbankapi.infra.kafka.config.kafka_config import producer_config


def test_producer_uses_the_java_compatible_partitioner():
    """librdkafka defaults to CRC32; the Java client Flink uses is murmur2.

    Disagreeing splits one account's events across partitions, which silently
    destroys the per-account ordering guarantee.
    """
    assert producer_config(Settings(), client_id="x")["partitioner"] == "murmur2_random"


def test_producer_is_idempotent():
    config = producer_config(Settings(), client_id="x")
    assert config["enable.idempotence"] is True
    assert config["acks"] == "all"
