/**
 * Stress test for openbankapi's two async write paths: card purchases and
 * account transfers.
 *
 * Both endpoints return 202 immediately (they only publish a Kafka event) —
 * the real work happens later in the Flink jobs. This script measures TWO
 * separate latencies per request:
 *
 *   - accept latency:   POST -> 202 (should stay flat under load, it's just
 *                        a Kafka produce)
 *   - e2e latency:       POST -> status resolves to a terminal state, via
 *                        polling GET /.../status (this is where the pipeline
 *                        bottleneck under load actually shows up)
 *
 * Usage:
 *   BASE_URL=http://localhost:8000 k6 run load-tests/purchases-and-transfers.js
 *
 * Transfers require a write:admin / read:admin bearer token (purchases do
 * not). Without BEARER_TOKEN the transfer scenario is skipped automatically.
 *
 *   BASE_URL=http://localhost:8000 \
 *   BEARER_TOKEN=eyJ... \
 *   k6 run load-tests/purchases-and-transfers.js
 *
 * Tune load with env vars (defaults are deliberately small for a laptop):
 *   PURCHASE_VUS, TRANSFER_VUS   (default 5 each)
 *   DURATION                     (default 1m)
 *   POLL_TIMEOUT_S               (default 10, matches WEBSOCKET_TIMEOUT_SECONDS)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const BEARER_TOKEN = __ENV.BEARER_TOKEN || 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InpBdmpnN3ZvTnEyUkZNWE04clRxbCJ9.eyJpc3MiOiJodHRwczovL2Rldi1la3dnMWV5dmZqcm9mMHRvLnVzLmF1dGgwLmNvbS8iLCJzdWIiOiJhdXRoMHw2YTkwZjMyNDdjN2E0YmUyM2EwZWRjODAiLCJhdWQiOlsiaHR0cHM6Ly9vcGVuYmFuay5hcGkvY29tL2F1dGgiLCJodHRwczovL2Rldi1la3dnMWV5dmZqcm9mMHRvLnVzLmF1dGgwLmNvbS91c2VyaW5mbyJdLCJpYXQiOjE3ODk0ODg4NzEsImV4cCI6MTc4OTU3NTI3MSwic2NvcGUiOiJvcGVuaWQgcHJvZmlsZSBlbWFpbCIsImF6cCI6ImN3R2U4blFoS1A2RVlwbUNzZUxkM3lPSERXSVUxWW5wIiwicGVybWlzc2lvbnMiOlsiYWRtaW46YmF0Y2giLCJyZWFkOmFkbWluIiwid3JpdGU6YWRtaW4iXX0.WYI_esHqPTSyAUgemluL6gtdobe7TordxnoCxRVggG2Lzw0pSlHSElKU5fHP7N71rfxDYaieN3K__k89HSjEkTE5GYk3FLXQK69EOjN1Q-0lvAQDRv66kzI_75AIi0X6s2nUuWv0_pbf6LrKJrNUj3Zx3WC3Z1Y0nDLXLYWs7vS1OI1jh2bHosLueCelW9nKoanMslzYXo0N5KY-iSAi6N93A3vsrNFczsOH6SVyvMllxGBDfUyXTDPUb8-JmBFqjHjbcD7ha-IhPKSGwWo-FaniJPT8rWh9AENmzz__wjYx_d3DQ_MmOw-Kuba9d2KJHuBYA4kWnUwjd4AxZhMo1g';
const PURCHASE_VUS = Number(__ENV.PURCHASE_VUS || 500);
const TRANSFER_VUS = Number(__ENV.TRANSFER_VUS || 500);
const DURATION = __ENV.DURATION || '1m';
const POLL_TIMEOUT_S = Number(__ENV.POLL_TIMEOUT_S || 10);
const POLL_INTERVAL_S = Number(__ENV.POLL_INTERVAL_S || 0.25);

const purchaseE2ELatency = new Trend('purchase_e2e_latency_ms', true);
const transferE2ELatency = new Trend('transfer_e2e_latency_ms', true);
const purchaseUnresolved = new Counter('purchase_unresolved_total');
const transferUnresolved = new Counter('transfer_unresolved_total');

const scenarios = {
  purchases: {
    executor: 'ramping-vus',
    exec: 'purchaseFlow',
    startVUs: 0,
    stages: [
      { duration: '15s', target: PURCHASE_VUS },
      { duration: DURATION, target: PURCHASE_VUS },
      { duration: '10s', target: 0 },
    ],
  },
};

if (BEARER_TOKEN) {
  scenarios.transfers = {
    executor: 'ramping-vus',
    exec: 'transferFlow',
    startVUs: 0,
    stages: [
      { duration: '15s', target: TRANSFER_VUS },
      { duration: DURATION, target: TRANSFER_VUS },
      { duration: '10s', target: 0 },
    ],
  };
}

export const options = {
  scenarios,
  thresholds: {
    // Accept latency should stay fast — if this creeps up, the bottleneck
    // moved into the HTTP layer itself (DB pool exhaustion on the write
    // path, uvicorn worker saturation), not just the async pipeline.
    'http_req_duration{endpoint:purchase_accept}': ['p(95)<500'],
    'http_req_duration{endpoint:transfer_accept}': ['p(95)<500'],
  },
};

function authHeaders() {
  return BEARER_TOKEN ? { Authorization: `Bearer ${BEARER_TOKEN}` } : {};
}

export function setup() {
  const cardsRes = http.get(`${BASE_URL}/cards?limit=50`, {
    headers: authHeaders(),
  });
  if (cardsRes.status !== 200) {
    throw new Error(
      `setup: GET /cards failed (${cardsRes.status}) — is the seed data loaded? ${cardsRes.body}`
    );
  }
  const cards = cardsRes
    .json('items')
    .filter((c) => String(c.status).toLowerCase() === 'active')
    .map((c) => ({ card_number: c.card_number, card_id: c.id }));

  if (cards.length === 0) {
    throw new Error('setup: no active cards found — run the seed script first.');
  }

  let accounts = [];
  if (BEARER_TOKEN) {
    const acctRes = http.get(`${BASE_URL}/accounts/all?limit=50`, {
      headers: authHeaders(),
    });
    if (acctRes.status !== 200) {
      throw new Error(
        `setup: GET /accounts/all failed (${acctRes.status}) — bad/expired token? ${acctRes.body}`
      );
    }
    accounts = acctRes
      .json('items')
      .filter((a) => String(a.status).toLowerCase() === 'active')
      .map((a) => a.account_number);

    if (accounts.length < 2) {
      throw new Error('setup: need at least 2 ACTIVE accounts for transfers — check seed data.');
    }
  }

  return { cards, accounts };
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

// Polls a status endpoint until it leaves "pending" or POLL_TIMEOUT_S elapses.
// Returns { resolved: bool, elapsedMs: number, finalStatus: string }.
function pollUntilResolved(statusUrl, headers = {}) {
  const start = Date.now();
  let lastStatus = 'pending';
  while ((Date.now() - start) / 1000 < POLL_TIMEOUT_S) {
    const res = http.get(statusUrl, { headers, tags: { endpoint: 'status_poll' } });
    if (res.status === 200) {
      lastStatus = res.json('status');
      if (lastStatus !== 'pending') {
        return { resolved: true, elapsedMs: Date.now() - start, finalStatus: lastStatus };
      }
    }
    sleep(POLL_INTERVAL_S);
  }
  return { resolved: false, elapsedMs: Date.now() - start, finalStatus: lastStatus };
}

export function purchaseFlow(data) {
  const card = pick(data.cards);
  const body = JSON.stringify({
    card_id: card.card_id,
    amount: (Math.random() * 490 + 10).toFixed(2), // 10.00 - 500.00
    currency: 'USD',
    description: 'k6 load test purchase',
    installments: 1,
  });

  const res = http.post(`${BASE_URL}/cards/${card.card_number}/purchases`, body, {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'purchase_accept' },
  });

  const accepted = check(res, {
    'purchase accepted (202)': (r) => r.status === 202,
  });
  if (!accepted) {
    sleep(1);
    return;
  }

  const requestId = res.json('request_id');
  const outcome = pollUntilResolved(`${BASE_URL}/purchases/${requestId}/status`);
  if (outcome.resolved) {
    purchaseE2ELatency.add(outcome.elapsedMs);
  } else {
    purchaseUnresolved.add(1);
  }

  sleep(1);
}

export function transferFlow(data) {
  const [source, destination] = shuffleTwo(data.accounts);
  const body = JSON.stringify({
    source_account: source,
    destination_account: destination,
    amount: Math.floor(Math.random() * 49000 + 1000), // cents
    description: 'k6 load test transfer',
  });

  const res = http.post(`${BASE_URL}/transfer`, body, {
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    tags: { endpoint: 'transfer_accept' },
  });

  const accepted = check(res, {
    'transfer accepted (202)': (r) => r.status === 202,
  });
  if (!accepted) {
    sleep(1);
    return;
  }

  const requestId = res.json('request_id');
  const outcome = pollUntilResolved(`${BASE_URL}/transfer/${requestId}/status`, authHeaders());
  if (outcome.resolved) {
    transferE2ELatency.add(outcome.elapsedMs);
  } else {
    transferUnresolved.add(1);
  }

  sleep(1);
}

function shuffleTwo(accounts) {
  const source = pick(accounts);
  let destination = pick(accounts);
  while (destination === source && accounts.length > 1) {
    destination = pick(accounts);
  }
  return [source, destination];
}
