#!/usr/bin/env bash
# Submits the PyFlink job once the cluster can actually run it.
set -euo pipefail

JOBMANAGER="${FLINK_JOBMANAGER:-flink-card-jobmanager:8081}"

# Waiting for the JobManager alone is not enough: a job submitted before any
# TaskManager has registered sits without slots until Flink gives up on it.
echo "waiting for a TaskManager to register at ${JOBMANAGER} ..."
until curl -sf "http://${JOBMANAGER}/overview" \
  | python3 -c "import sys, json; sys.exit(0 if json.load(sys.stdin).get('taskmanagers', 0) > 0 else 1)" 2>/dev/null; do
  sleep 2
done

# Resubmitting on top of a live job would run two authorization ledgers over
# one topic.
if curl -sf "http://${JOBMANAGER}/jobs/overview" \
  | python3 -c "import sys, json; sys.exit(0 if any(j['state'] == 'RUNNING' for j in json.load(sys.stdin)['jobs']) else 1)" 2>/dev/null; then
  echo "a job is already RUNNING; nothing to submit"
  exit 0
fi

echo "submitting card-service ..."
exec /opt/flink/bin/flink run -d -m "${JOBMANAGER}" \
  --pyFiles /opt/card_service/domain.py \
  -py /opt/card_service/job.py
