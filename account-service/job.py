"""Account Service — PyFlink DataStream job (spec §5).

Consumes `account-events`, keyed by account, applies the ledger rules from
`domain.py` against Flink keyed state, and writes back to `account-events`
(the fan-out legs) and `transfer-status` (the client-facing confirmations).

Deviations from the §5.7 sketch, all forced by the real PyFlink API — see
README.md for the reasoning:

* Side outputs are emitted by yielding `(tag, value)`. PyFlink's
  `KeyedProcessFunction.Context` has no `output()` method.
* `set_key_serialization_schema` takes a JVM-backed `SerializationSchema`, not
  the sketch's Python lambda, and PyFlink ships no schema that can pick one
  field out of a record. `RowFieldSerializationSchema` (see java/) supplies one,
  and is reached through py4j.
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

from domain import LedgerState, decide, shard_key_of

LOG = logging.getLogger("account-service")

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092")
ACCOUNT_EVENTS_TOPIC = os.getenv("ACCOUNT_EVENTS_TOPIC", "account-events")
TRANSFER_STATUS_TOPIC = os.getenv("TRANSFER_STATUS_TOPIC", "transfer-status")
ACCOUNT_BALANCES_TOPIC = os.getenv("ACCOUNT_BALANCES_TOPIC", "account-balances")
# Credit Cards Phase 3: `card_payment_received` fans out to card-service's own
# `card-events` topic (a NEW topic for this job — it previously never wrote to
# it), and the payment's own approval status fans out to `card-payment-status`
# (spec: kafka-topics, account-service-payment-handling).
CARD_EVENTS_TOPIC = os.getenv("CARD_EVENTS_TOPIC", "card-events")
CARD_PAYMENT_STATUS_TOPIC = os.getenv("CARD_PAYMENT_STATUS_TOPIC", "card-payment-status")
CONSUMER_GROUP = os.getenv("ACCOUNT_SERVICE_GROUP_ID", "account-service")
CHECKPOINT_INTERVAL_MS = int(os.getenv("CHECKPOINT_INTERVAL_MS", "5000"))
CHECKPOINT_DIR = os.getenv("CHECKPOINT_DIR", "file:///tmp/flink-checkpoints")
PROCESSED_IDS_TTL_DAYS = int(os.getenv("PROCESSED_IDS_TTL_DAYS", "7"))
JOB_NAME = "account-service"

# Every record leaving this job is a (Kafka message key, JSON payload) pair. The
# key is what routes the record to its account's shard on the way out — see §5.4.
RECORD_TYPE = Types.ROW_NAMED(["kafka_key", "payload"], [Types.STRING(), Types.STRING()])
STATUS_TAG = OutputTag("status-events", RECORD_TYPE)

# The read model cannot learn a balance from `transfer-status`: that feed only
# ever names the source account, so a credit landing on a destination or fees
# account would be invisible to OpenBankAPI (spec §3.6).
BALANCES_TAG = OutputTag("balance-events", RECORD_TYPE)

# Credit Cards Phase 3: a payment's `card_payment_received` leg is NOT an
# account-events record — it belongs on card-service's own keyed stream
# (`card_account_id`, not this account's own key), so it is a side output
# sunk to a DIFFERENT topic entirely, mirroring `STATUS_TAG`/`BALANCES_TAG`'s
# existing pattern exactly.
CARD_TAG = OutputTag("card-events", RECORD_TYPE)
CARD_STATUS_TAG = OutputTag("card-payment-status-events", RECORD_TYPE)

KEY_FIELD, PAYLOAD_FIELD = 0, 1

# A record that is malformed, or that names no account, still has to be keyed
# somewhere: key_by runs before the operator, so an exception there would
# crash-loop the whole job on one poison message instead of dropping it.
UNROUTABLE_KEY = "__unroutable__"


def _routing_key(record: str) -> str:
    try:
        return shard_key_of(json.loads(record))
    except (TypeError, ValueError, KeyError):
        return UNROUTABLE_KEY


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _MapStateMembership:
    """Adapts Flink's MapState to the `in` protocol `domain.LedgerState` expects."""

    __slots__ = ("_map_state",)

    def __init__(self, map_state):
        self._map_state = map_state

    def __contains__(self, key: str) -> bool:
        return self._map_state.contains(key)


class AccountProcessor(KeyedProcessFunction):
    """One instance per keyed subtask; state below is scoped per account (§5.2)."""

    def open(self, ctx: RuntimeContext):
        balance_descriptor = ValueStateDescriptor("balance", Types.LONG())

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

        self._balance = ctx.get_state(balance_descriptor)
        self._processed = ctx.get_map_state(processed_descriptor)

    def process_element(self, value, ctx: "KeyedProcessFunction.Context"):
        account = ctx.get_current_key()
        if account == UNROUTABLE_KEY:
            LOG.warning("dropping unroutable record: %r", value)
            return

        # Reaching here means _routing_key already parsed this record.
        event = json.loads(value)
        state = LedgerState(
            balance=self._balance.value(),
            processed=_MapStateMembership(self._processed),
        )

        decision = decide(account, event, state, now=_now())

        if decision.new_balance is not None:
            self._balance.update(decision.new_balance)
        for key in decision.dedup_keys:
            self._processed.put(key, True)

        for produced in decision.account_events:
            yield Row(shard_key_of(produced), json.dumps(produced))
        for status in decision.status_events:
            yield STATUS_TAG, Row(status["request_id"], json.dumps(status))
        for balance in decision.balance_events:
            yield BALANCES_TAG, Row(balance["account_id"], json.dumps(balance))
        for card_event in decision.card_events:
            yield CARD_TAG, Row(card_event["card_account_id"], json.dumps(card_event))
        for card_status in decision.card_status_events:
            yield CARD_STATUS_TAG, Row(card_status["request_id"], json.dumps(card_status))


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
        # The book's algorithm tolerates at-least-once because domain.py
        # deduplicates by (request_id, leg); see §5.6.
        .set_delivery_guarantee(DeliveryGuarantee.AT_LEAST_ONCE)
        .build()
    )


def build_job():
    env = StreamExecutionEnvironment.get_execution_environment()

    # Protects `balance` and `processed_ids` across restarts. This is Flink's
    # internal state consistency and is independent of the sinks' at-least-once
    # delivery guarantee, which the dedup logic in domain.py already makes safe.
    env.enable_checkpointing(CHECKPOINT_INTERVAL_MS, CheckpointingMode.EXACTLY_ONCE)
    env.get_checkpoint_config().set_checkpoint_storage_dir(CHECKPOINT_DIR)
    env.set_state_backend(EmbeddedRocksDBStateBackend())

    source = (
        KafkaSource.builder()
        .set_bootstrap_servers(BOOTSTRAP_SERVERS)
        .set_topics(ACCOUNT_EVENTS_TOPIC)
        .set_group_id(CONSUMER_GROUP)
        .set_starting_offsets(KafkaOffsetsInitializer.earliest())
        .set_value_only_deserializer(SimpleStringSchema())
        .build()
    )

    processed = (
        env.from_source(source, WatermarkStrategy.no_watermarks(), ACCOUNT_EVENTS_TOPIC)
        .key_by(_routing_key, key_type=Types.STRING())
        .process(AccountProcessor(), output_type=RECORD_TYPE)
        .name("account-processor")
    )

    processed.sink_to(_kafka_sink(ACCOUNT_EVENTS_TOPIC)).name("account-events-sink")
    processed.get_side_output(STATUS_TAG).sink_to(
        _kafka_sink(TRANSFER_STATUS_TOPIC)
    ).name("transfer-status-sink")
    # Keyed by account_id so the compacted topic retains the latest balance per
    # account, which is exactly what the read-model consumer needs (spec §4.3).
    processed.get_side_output(BALANCES_TAG).sink_to(
        _kafka_sink(ACCOUNT_BALANCES_TOPIC)
    ).name("account-balances-sink")
    processed.get_side_output(CARD_TAG).sink_to(
        _kafka_sink(CARD_EVENTS_TOPIC)
    ).name("card-events-sink")
    processed.get_side_output(CARD_STATUS_TAG).sink_to(
        _kafka_sink(CARD_PAYMENT_STATUS_TOPIC)
    ).name("card-payment-status-sink")

    env.execute(JOB_NAME)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_job()
