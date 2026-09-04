"""Card Service — PyFlink DataStream job (design §2).

Consumes `card-events`, keyed by `card_account_id` (the credit pool a
`purchase_requested` event draws against — design §6: the running total is
per credit line, not per physical card), applies the authorization rules
from `domain.py` against Flink keyed state, and writes back to `card-events`
(the approved/declined legs) and `purchase-status` (the client-facing
confirmations).

This module is a sibling of `account-service/job.py`, not a modification of
it (design §2's explicit "sibling, not modification" requirement) — same
PyFlink wiring pattern, same JAR-backed Kafka key/value split, pointed at
`card-service/`'s own code, image, and topics.

Deviations from the naive PyFlink sketch, all forced by the real API — see
`account-service/job.py`'s own docstring for the underlying reasoning,
reproduced here because it applies identically:

* Side outputs are emitted by yielding `(tag, value)`. PyFlink's
  `KeyedProcessFunction.Context` has no `output()` method.
* `set_key_serialization_schema` takes a JVM-backed `SerializationSchema`, not
  a Python lambda, and PyFlink ships no schema that can pick one field out of
  a record. `RowFieldSerializationSchema` (see java/) supplies one, and is
  reached through py4j.
* `from_source` requires a real `WatermarkStrategy`; `None` is not accepted.
* `StateTtlConfig.new_builder` takes a `pyflink.common.time.Time`.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from pyflink.common import Row, Types, WatermarkStrategy
from pyflink.common.serialization import SerializationSchema, SimpleStringSchema
from pyflink.common.time import Time
from pyflink.datastream import CheckpointingMode, StreamExecutionEnvironment
from pyflink.datastream.connectors.base import DeliveryGuarantee
from pyflink.datastream.connectors.kafka import (
    KafkaOffsetsInitializer,
    KafkaRecordSerializationSchema,
    KafkaSink,
    KafkaSource,
)
from pyflink.datastream.functions import KeyedProcessFunction, RuntimeContext
from pyflink.datastream.output_tag import OutputTag
from pyflink.datastream.state import (
    MapStateDescriptor,
    StateTtlConfig,
    ValueStateDescriptor,
)
from pyflink.datastream.state_backend import EmbeddedRocksDBStateBackend
from pyflink.java_gateway import get_gateway

from domain import CardState, PURCHASE_REQUESTED, decide

LOG = logging.getLogger("card-service")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092")
CARD_EVENTS_TOPIC = os.getenv("CARD_EVENTS_TOPIC", "card-events")
PURCHASE_STATUS_TOPIC = os.getenv("PURCHASE_STATUS_TOPIC", "purchase-status")
CONSUMER_GROUP = os.getenv("CARD_SERVICE_GROUP_ID", "card-service")
CHECKPOINT_INTERVAL_MS = int(os.getenv("CHECKPOINT_INTERVAL_MS", "5000"))
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "file:///tmp/flink-checkpoints")
PROCESSED_IDS_TTL_DAYS = int(os.getenv("PROCESSED_IDS_TTL_DAYS", "7"))
JOB_NAME = "card-service"

# Every record leaving this job is a (Kafka message key, JSON payload) pair. The
# key is what routes the record to its credit line's shard on the way out.
RECORD_TYPE = Types.ROW_NAMED(["kafka_key", "payload"], [Types.STRING(), Types.STRING()])
STATUS_TAG = OutputTag("status-events", RECORD_TYPE)

KEY_FIELD, PAYLOAD_FIELD = 0, 1

# A record that is malformed, or that names no credit line, still has to be
# keyed somewhere: key_by runs before the operator, so an exception there
# would crash-loop the whole job on one poison message instead of dropping it.
UNROUTABLE_KEY = "__unroutable__"


def _routing_key(record: str) -> str:
    """The Kafka message key for both the source keying and the output sinks
    is `card_account_id`: the credit limit and running total this job
    authorizes against belong to the credit line (account), not the
    individual physical card (design §6)."""
    try:
        event = json.loads(record)
        return str(event["card_account_id"])
    except (TypeError, ValueError, KeyError):
        return UNROUTABLE_KEY


class _MapStateMembership:
    """Adapts Flink's MapState to the `in` protocol `domain.CardState` expects."""

    __slots__ = ("_map_state",)

    def __init__(self, map_state):
        self._map_state = map_state

    def __contains__(self, key: str) -> bool:
        return self._map_state.contains(key)


class CardProcessor(KeyedProcessFunction):
    """One instance per keyed subtask; state below is scoped per `card_account_id`."""

    def open(self, ctx: RuntimeContext):
        used_credit_descriptor = ValueStateDescriptor("used_credit", Types.LONG())

        # Old request_ids stop mattering once nothing will retry that far back,
        # so the dedup guard is TTL'd rather than grown forever.
        ttl = (
            StateTtlConfig.new_builder(Time.days(PROCESSED_IDS_TTL_DAYS))
            .set_update_type(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .set_state_visibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
            .build()
        )
        processed_descriptor = MapStateDescriptor(
            "processed_ids", Types.STRING(), Types.BOOLEAN()
        )
        processed_descriptor.enable_time_to_live(ttl)

        self._used_credit = ctx.get_state(used_credit_descriptor)
        self._processed = ctx.get_map_state(processed_descriptor)

    def process_element(self, value, ctx: "KeyedProcessFunction.Context"):
        card_account_id = ctx.get_current_key()
        if card_account_id == UNROUTABLE_KEY:
            LOG.warning("dropping unroutable record: %r", value)
            return

        # Reaching here means _routing_key already parsed this record.
        event = json.loads(value)
        if event.get("type") != PURCHASE_REQUESTED:
            # This job only decides on purchase requests; approved/declined
            # legs it emits itself pass through this topic too (fan-out) but
            # must never be reconsidered here.
            return

        current_used_credit = self._used_credit.value()
        state = CardState(
            used_credit=current_used_credit if current_used_credit is not None else 0,
            processed=_MapStateMembership(self._processed),  # type: ignore[arg-type]
        )

        decision = decide(state, event, now=datetime.now(timezone.utc))

        if decision.new_used_credit is not None:
            self._used_credit.update(decision.new_used_credit)
        for key in decision.dedup_keys:
            self._processed.put(key, True)

        for produced in decision.card_events:
            yield Row(card_account_id, json.dumps(produced))
        for status in decision.status_events:
            yield STATUS_TAG, Row(status["request_id"], json.dumps(status))


    def __contains__(self, request_id: str) -> bool:
        return self._map_state.contains(request_id)


def _row_field_schema(field_index: int) -> SerializationSchema:
    """Wrap the JAR's field-extracting schema so PyFlink can hand it to the sink.

    `SerializationSchema` is a thin holder around a JVM object, so constructing
    the Java class through py4j and wrapping it is all that is needed. The class
    lives on the Flink classpath (see Dockerfile), not in this process.
    """
    jvm = get_gateway().jvm
    return SerializationSchema(
        j_serialization_schema=jvm.com.banking.flink.RowFieldSerializationSchema(field_index)
    )


def _kafka_sink(topic: str) -> KafkaSink:
    """A Kafka sink that keys each record by field 0 and writes field 1 as the value.

    No partitioner is configured on purpose: Flink then leaves the partition
    unset on the ProducerRecord and the Kafka client's own murmur2 partitioner
    decides, which is what keeps these records on the same partitions the
    gateway writes to.
    """
    return (
        KafkaSink.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
            .set_topic(topic)
            .set_key_serialization_schema(_row_field_schema(KEY_FIELD))
            .set_value_serialization_schema(_row_field_schema(PAYLOAD_FIELD))
            .build()
        )
        # At-least-once is safe: domain.py deduplicates by request_id
        # (design §7's Flink-side processed_ids layer).
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .build()
    )


def build_job():
    env = StreamExecutionEnvironment.get_execution_environment()

    # Protects `used_credit` and `processed_ids` across restarts. This is
    # Flink's internal state consistency and is independent of the sinks'
    # at-least-once delivery guarantee, which domain.py's dedup already
    # makes safe.
    env.enable_checkpointing(CHECKPOINT_INTERVAL_MS, CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_checkpoint_storage_dir(CHECKPOINT_DIR)
    env.set_state_backend(EmbeddedRocksDBStateBackend())

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_topics(CARD_EVENTS_TOPIC)
        .set_group_id(CONSUMER_GROUP)
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    processed = (
        env.from_source(source, WatermarkStrategy.no_watermarks(), CARD_EVENTS_TOPIC)
        .key_by(_routing_key, key_type=Types.STRING())
        .process(CardProcessor(), output_type=RECORD_TYPE)
        .name("card-processor")
    )

    processed.sink_to(_kafka_sink(CARD_EVENTS_TOPIC)).name("card-events-sink")
    processed.get_side_output(STATUS_TAG).sink_to(
        _kafka_sink(PURCHASE_STATUS_TOPIC)
    ).name("purchase-status-sink")

    env.execute(JOB_NAME)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_job()
