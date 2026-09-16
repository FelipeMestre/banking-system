#!/usr/bin/env bash
# Runs purchases-and-transfers.js across a matrix of (replica count x VU level)
# and records one row per run in a CSV — the data needed to answer "how does
# this system scale as we add openbankapi replicas".
#
# Usage:
#   BEARER_TOKEN=eyJ... ./load-tests/run-scaling-sweep.sh
#
# Tunables (env vars, all optional):
#   REPLICA_LEVELS   space-separated openbankapi replica counts to test (default: "1 2 4")
#   VU_LEVELS        space-separated *total* VU counts per run, split evenly
#                     between purchases/transfers (default: "20 50 100 200")
#   RUN_DURATION     k6 DURATION per run, e.g. "30s" (default: "30s")
#   BASE_URL         (default: http://localhost:8000 — nginx, not openbankapi directly)
#   BEARER_TOKEN     required to include the transfer scenario; purchase-only
#                     runs still happen without it
#   OUTPUT_CSV       where rows are appended (default: load-tests/scaling-results.csv)
#   COOLDOWN_SECONDS pause between runs so one run's tail doesn't bleed into
#                     the next's numbers (default: 10)
#
# Requires: docker compose stack already up, k6, python3.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

REPLICA_LEVELS=${REPLICA_LEVELS:-"1 2 4"}
VU_LEVELS=${VU_LEVELS:-"20 50 100 200"}
RUN_DURATION=${RUN_DURATION:-"30s"}
BASE_URL=${BASE_URL:-"http://localhost:8000"}
BEARER_TOKEN=${BEARER_TOKEN:-""}
OUTPUT_CSV=${OUTPUT_CSV:-"load-tests/scaling-results.csv"}
COOLDOWN_SECONDS=${COOLDOWN_SECONDS:-10}

SCRIPT_DIR="load-tests"
K6_SCRIPT="${SCRIPT_DIR}/purchases-and-transfers.js"
TMP_SUMMARY=$(mktemp -t k6-summary-XXXXXX.json)
trap 'rm -f "$TMP_SUMMARY"' EXIT

if [ -z "$BEARER_TOKEN" ]; then
  echo "WARNING: no BEARER_TOKEN set — transfer scenario will be skipped on every run, only purchase data will be recorded." >&2
fi

wait_for_api() {
  local retries=30
  until curl -sf "${BASE_URL}/cards?limit=1" > /dev/null 2>&1; do
    retries=$((retries - 1))
    if [ "$retries" -le 0 ]; then
      echo "openbankapi did not become healthy behind ${BASE_URL} in time" >&2
      exit 1
    fi
    sleep 2
  done
}

echo "Sweep plan: replicas=[${REPLICA_LEVELS}] x total_vus=[${VU_LEVELS}], ${RUN_DURATION} per run"
echo "Results will be appended to ${OUTPUT_CSV}"
echo

for replicas in $REPLICA_LEVELS; do
  echo "== Scaling openbankapi to ${replicas} replica(s) =="
  docker compose up -d --scale "openbankapi=${replicas}" --no-recreate --no-deps openbankapi
  wait_for_api

  for total_vus in $VU_LEVELS; do
    purchase_vus=$((total_vus / 2))
    transfer_vus=$((total_vus - purchase_vus))
    run_label="r${replicas}_vu${total_vus}"

    echo "-- Run ${run_label}: ${replicas} replicas, ${purchase_vus} purchase VUs, ${transfer_vus} transfer VUs, ${RUN_DURATION} --"

    BASE_URL="$BASE_URL" \
    BEARER_TOKEN="$BEARER_TOKEN" \
    PURCHASE_VUS="$purchase_vus" \
    TRANSFER_VUS="$transfer_vus" \
    DURATION="$RUN_DURATION" \
      k6 run --summary-export="$TMP_SUMMARY" "$K6_SCRIPT" \
      || echo "  (thresholds crossed — expected once you're past the system's comfortable ceiling; run recorded anyway)"

    python3 "${SCRIPT_DIR}/parse_summary.py" \
      "$TMP_SUMMARY" "$replicas" "$purchase_vus" "$transfer_vus" "$run_label" "$OUTPUT_CSV"

    echo "  recorded -> ${OUTPUT_CSV}"
    sleep "$COOLDOWN_SECONDS"
  done
  echo
done

echo "Sweep complete. Results in ${OUTPUT_CSV}"
