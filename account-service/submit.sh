#!/usr/bin/env bash
# Submits the PyFlink job once the cluster can actually run it (spec §8).
set -euo pipefail

JOBMANAGER="${FLINK_JOBMANAGER:-flink-jobmanager:8081}"

# Waiting for the JobManager alone is not enough: a job submitted before any
# TaskManager has registered sits without slots until Flink gives up on it.
echo "waiting for a TaskManager to register at ${JOBMANAGER} ..."
until curl -sf "http://${JOBMANAGER}/overview" \
  | python3 -c "import sys, json; sys.exit(0 if json.load(sys.stdin).get('taskmanagers', 0) > 0 else 1)" 2>/dev/null; do
  sleep 2
done

# Resubmitting on top of a live job would run two ledgers over one topic.
if curl -sf "http://${JOBMANAGER}/jobs/overview" \
  | python3 -c "import sys, json; sys.exit(0 if any(j['state'] == 'RUNNING' for j in json.load(sys.stdin)['jobs']) else 1)" 2>/dev/null; then
  echo "a job is already RUNNING; nothing to submit"
  exit 0
fi

# `CHECKPOINT_DIR` matches job.py's own default exactly (same env var, same
# fallback) — the "file://" URI is what Flink itself wrote checkpoints under,
# so resuming has to hand back a path in that same form, not a bare filesystem
# path. `find`/`glob` still need the bare path, hence stripping it below.
CHECKPOINT_DIR="${CHECKPOINT_DIR:-file:///tmp/flink-checkpoints}"
CHECKPOINT_ROOT="${CHECKPOINT_DIR#file://}"

# Find the newest COMPLETE checkpoint (one with an `_metadata` file) across
# every job-id subdirectory under the checkpoint root — a resumed job gets a
# brand-new job-id and writes its own new subdirectory each time, so "newest"
# can never be a fixed path. Numeric `chk-<N>` ordering, not mtime: reliable
# regardless of clock/filesystem timestamp behavior on a bind-mounted volume.
LATEST_CHECKPOINT="$(python3 - "$CHECKPOINT_ROOT" <<'PYEOF'
import glob
import os
import re
import sys

root = sys.argv[1]
best_dir, best_n = None, -1
for meta in glob.glob(os.path.join(root, "*", "chk-*", "_metadata")):
    chk_dir = os.path.dirname(meta)
    match = re.search(r"chk-(\d+)$", chk_dir)
    if not match:
        continue
    n = int(match.group(1))
    if n > best_n:
        best_n, best_dir = n, chk_dir
print(best_dir or "")
PYEOF
)"

SUBMIT_ARGS=(-d -m "${JOBMANAGER}")
if [ -n "$LATEST_CHECKPOINT" ]; then
  echo "resuming account-service from checkpoint: ${LATEST_CHECKPOINT}"
  SUBMIT_ARGS+=(-s "file://${LATEST_CHECKPOINT}")
else
  echo "no checkpoint found under ${CHECKPOINT_ROOT}; starting account-service fresh"
fi

echo "submitting account-service ..."
exec /opt/flink/bin/flink run "${SUBMIT_ARGS[@]}" \
  --pyFiles /opt/account_service/domain.py \
  -py /opt/account_service/job.py
