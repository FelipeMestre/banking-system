# --- stage 1: the field-extracting serialization schema -----------------------
# Built here so nobody needs a JDK or Maven on their machine. Runs natively on
# the build host (bytecode is portable), not under the emulated runtime platform.
# This is a self-contained duplicate of account-service/java's own build (design
# §2's explicit "sibling, not modification" choice), not a shared artifact.
FROM --platform=$BUILDPLATFORM maven:3.9-eclipse-temurin-17 AS java-build
WORKDIR /build
COPY java/ ./
RUN mvn -B -q -DskipTests package

# --- stage 2: the PyFlink card service (design §2) ----------------------------
# The Flink version is pinned because PyFlink must match the cluster it builds
# the JobGraph for; keep it in step with requirements.txt and java/pom.xml.
#
# The platform is pinned to amd64 because PyPI publishes no aarch64 Linux wheel
# for apache-flink: on Apple Silicon pip would fall back to compiling the Cython
# extensions from source. Emulation costs startup time, nothing else here.
FROM --platform=linux/amd64 flink:1.20.5-java17

ENV FLINK_KAFKA_CONNECTOR_VERSION=3.3.0-1.20

# Python runtime for PyFlink.
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-dev curl && \
    ln -sf /usr/bin/python3 /usr/bin/python && \
    rm -rf /var/lib/apt/lists/*

# The Kafka connector is Java: it has to be on the Flink classpath before the
# JVM starts, so pip cannot supply it.
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${FLINK_KAFKA_CONNECTOR_VERSION}.jar \
    https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${FLINK_KAFKA_CONNECTOR_VERSION}/flink-sql-connector-kafka-${FLINK_KAFKA_CONNECTOR_VERSION}.jar

# Same reason: job.py reaches this class through py4j, so it must already be on
# the classpath of the client, the JobManager and every TaskManager.
COPY --from=java-build /build/target/flink-row-field-schema-1.0.0.jar /opt/flink/lib/

COPY requirements.txt /opt/card_service/requirements.txt
RUN pip3 install --no-cache-dir -r /opt/card_service/requirements.txt

COPY . /opt/card_service
RUN chmod +x /opt/card_service/submit.sh

# The checkpoint directory is a named volume, and Docker seeds a fresh volume
# with the ownership of this path in the image. Without this it is created
# root-owned and the flink user cannot write checkpoints into it.
RUN mkdir -p /tmp/flink-checkpoints && chown -R flink:flink /tmp/flink-checkpoints
