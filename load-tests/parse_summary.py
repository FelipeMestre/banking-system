"""Flattens one k6 --summary-export JSON into a single CSV row.

k6's summary JSON keys metrics by name, including per-tag sub-metrics for any
tag combination referenced by a threshold (e.g. `http_req_duration{endpoint:purchase_accept}`),
which is exactly what purchases-and-transfers.js's thresholds produce.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def _trend(metrics: dict, name: str, field: str = "p(95)") -> float | None:
    m = metrics.get(name)
    return m.get(field) if m else None


def _counter(metrics: dict, name: str) -> int:
    m = metrics.get(name)
    return int(m["count"]) if m and "count" in m else 0


def _rate(metrics: dict, name: str, field: str = "rate") -> float | None:
    m = metrics.get(name)
    return m.get(field) if m else None


def row_from_summary(summary_path: str, replicas: int, purchase_vus: int, transfer_vus: int, run_label: str) -> dict:
    data = json.loads(Path(summary_path).read_text())
    metrics = data.get("metrics", {})

    return {
        "run_label": run_label,
        "replicas": replicas,
        "purchase_vus": purchase_vus,
        "transfer_vus": transfer_vus,
        "total_vus": purchase_vus + transfer_vus,
        "iterations": _counter(metrics, "iterations"),
        "http_reqs": _counter(metrics, "http_reqs"),
        "throughput_rps": round(_rate(metrics, "http_reqs", "rate") or 0, 2),
        "http_req_failed_rate": round((_rate(metrics, "http_req_failed") or 0) * 100, 3),
        "purchase_accept_p95_ms": _trend(metrics, "http_req_duration{endpoint:purchase_accept}"),
        "purchase_accept_avg_ms": _trend(metrics, "http_req_duration{endpoint:purchase_accept}", "avg"),
        "transfer_accept_p95_ms": _trend(metrics, "http_req_duration{endpoint:transfer_accept}"),
        "transfer_accept_avg_ms": _trend(metrics, "http_req_duration{endpoint:transfer_accept}", "avg"),
        "purchase_e2e_p95_ms": _trend(metrics, "purchase_e2e_latency_ms"),
        "transfer_e2e_p95_ms": _trend(metrics, "transfer_e2e_latency_ms"),
        "purchase_unresolved": _counter(metrics, "purchase_unresolved_total"),
        "transfer_unresolved": _counter(metrics, "transfer_unresolved_total"),
    }


def main() -> None:
    if len(sys.argv) != 7:
        print(
            "usage: parse_summary.py <summary.json> <replicas> <purchase_vus> "
            "<transfer_vus> <run_label> <output_csv>",
            file=sys.stderr,
        )
        raise SystemExit(1)

    summary_path, replicas, purchase_vus, transfer_vus, run_label, output_csv = sys.argv[1:]
    row = row_from_summary(summary_path, int(replicas), int(purchase_vus), int(transfer_vus), run_label)

    out_path = Path(output_csv)
    is_new = not out_path.exists()
    with out_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    main()
