package com.banking.flink;

import org.apache.flink.api.common.serialization.SerializationSchema;
import org.apache.flink.types.Row;

import java.nio.charset.StandardCharsets;

/**
 * Serializes a single field of a {@link Row} to UTF-8 bytes.
 *
 * <p>A Kafka sink hands the same element to both the key serializer and the value serializer, so
 * writing a per-record key requires a schema that can pick one field out of that element. PyFlink
 * ships four serialization schemas and none of them can: they all serialize the element as a whole.
 * Its {@code KafkaSinkBuilder} exposes no partitioner either, so from Python alone a DataStream
 * Kafka sink can only write key-less records.
 *
 * <p>That matters here because the Kafka message key is the account shard. Without it, one
 * account's events scatter across partitions, several source subtasks read them concurrently, and
 * the strictly-ordered per-account processing the ledger depends on is gone.
 *
 * <p>This class is the smallest thing that closes the gap: field 0 becomes the key, field 1 the
 * value. It must be Java because a serialization schema is shipped to every TaskManager through
 * Java serialization, which a Python callback cannot survive.
 */
public class RowFieldSerializationSchema implements SerializationSchema<Row> {

    private static final long serialVersionUID = 1L;

    private final int fieldIndex;

    public RowFieldSerializationSchema(int fieldIndex) {
        if (fieldIndex < 0) {
            throw new IllegalArgumentException("fieldIndex must not be negative: " + fieldIndex);
        }
        this.fieldIndex = fieldIndex;
    }

    @Override
    public byte[] serialize(Row element) {
        if (element == null) {
            return null;
        }
        Object field = element.getField(fieldIndex);
        // A null key is legal in Kafka; it just means "no key", so let it through
        // rather than failing the job.
        return field == null ? null : field.toString().getBytes(StandardCharsets.UTF_8);
    }
}
