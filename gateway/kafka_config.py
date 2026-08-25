"""Kafka client configuration shared by every producer in the gateway.

Kept free of `confluent_kafka` imports so the partitioning rule below can be
asserted in tests without the native client installed.
"""
from __future__ import annotations

from typing import Any, Dict

from .config import Settings

# librdkafka defaults to `consistent_random`, which hashes keys with CRC32.
# The Java client — which is what the Flink sink uses — hashes with murmur2.
# Left at the default, the same account_id lands on a different partition
# depending on which service produced the event, so one account's log is split
# across shards, several Flink source subtasks read it concurrently, and the
# per-account ordering the whole design rests on is gone. `murmur2_random` is
# librdkafka's Java-compatible partitioner.
JAVA_COMPATIBLE_PARTITIONER = "murmur2_random"


def producer_config(settings: Settings, client_id: str) -> Dict[str, Any]:
    return {
        "bootstrap.servers": settings.bootstrap_servers,
        "partitioner": JAVA_COMPATIBLE_PARTITIONER,
        "enable.idempotence": True,
        "acks": "all",
        "linger.ms": 5,
        "client.id": client_id,
    }
