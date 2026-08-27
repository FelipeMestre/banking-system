# OpenBankAPI — Backend

Implementation of [`openbankapi-spec-v2.md`](openbankapi-spec-v2.md) (which
supersedes [`system_spec.md`](system_spec.md)): a multishard payment flow built
on event logs and stream processing, with no distributed transaction, plus the
relational reference data and read model that v2 adds.

Backend and frontend. The Next.js app runs on the host, outside Compose, and
talks to the gateway directly (§7, §8).

## Layout

```
docker-compose.yml          Kafka (KRaft) + topic init + Flink + gateway + AKHQ
account-service/
  domain.py                 Pure ledger rules (§5.3) — no Flink imports
  job.py                    PyFlink wiring: source, keyed state, sinks (§5)
  java/                     One class: the field-extracting serialization schema
  submit.sh                 Waits for a task slot, then submits the job
  tests/test_domain.py      Ledger rules, incl. the §9 scenarios
openbankapi/                Domain-Driven Design layout (v2 §7.1)
  domain/model/             Entities: account, customer, branch, location
  domain/events/            Domain events, independent of any wire format
  domain/service/           Use cases: transfer, account
  domain/exceptions.py      Errors that carry meaning, not status codes
  controllers/              Routers + DTOs (the API contract)
  infra/database/           ORM, repository ports, Postgres implementations
  infra/cache/              ICacheService port + Redis adapter
  infra/kafka/              Publisher port, producer, both consumers
  main.py                   Composition root
  tests/                    Every layer, with fakes for every port
infra/postgres/init.sql     The four tables from v2 §3, in English
frontend/                   Next.js App Router + TypeScript (§7)
  app/page.tsx              The single page
  components/               Form, outcome view, and the state machine
  lib/gateway.ts            POST, WebSocket watch, status fallback
  lib/money.ts              Integer-cent formatting and parsing
```

## Running

```bash
docker compose up --build -d
```

Seed some balances (the ledger has no deposit concept — a balance is whatever
the account's event log says):

```bash
docker compose exec openbankapi python -m openbankapi.seed 1234567890123456=500000
```

Send a transfer:

```bash
curl -s -X POST localhost:8000/transfer -H 'content-type: application/json' -d '{"source_account":"acc-123","destination_account":"acc-456","amount":1100}'
```

Then poll `GET localhost:8000/transfer/<request_id>/status`, or hold
`ws://localhost:8000/ws/transfer/<request_id>`.

Or use the UI. The frontend is deliberately **not** in Compose (§8) — run it on
the host for fast iteration:

```bash
cd frontend && npm install && npm run dev
```

It talks to `http://localhost:8000` by default; override with
`NEXT_PUBLIC_GATEWAY_URL` in `frontend/.env.local`. The browser calls the
gateway directly, with no Route Handler or Server Action in between, because
the gateway already is the HTTP boundary (§7).

| Surface | URL |
|---|---|
| Gateway | http://localhost:8000 (docs at `/docs`) |
| Flink dashboard | http://localhost:8081 |
| AKHQ (Kafka UI) | http://localhost:8080 |
| Kafka (from host) | `localhost:9092` |

## Tests

```bash
python3 -m pytest              # backend: 46 tests
cd frontend && npm test        # frontend: 10 tests
```

No broker or cluster required for either — the ledger rules are pure functions,
Kafka sits behind a port the tests fake, and the frontend's money and wire
parsing are pure too.

## Where this departs from the spec

§10 says the §5.7 sketch is a design guide, not compilable code. It isn't. These
are the corrections, and why each one was forced.

**1. Per-record Kafka keys need ~30 lines of Java.**
The §5.7 sketch passes a lambda to `set_key_serialization_schema`. PyFlink does
`key_serialization_schema._j_serialization_schema` on that argument — it needs a
JVM-backed object, and a lambda has none. That is not the whole problem: a Kafka
sink hands the *same* element to both the key and the value serializer, PyFlink
ships four serialization schemas and none of them can pick one field out of an
element, and `KafkaSinkBuilder` exposes no partitioner. From Python alone, a
DataStream Kafka sink can only write key-less records.

This matters more than it looks. The Kafka key is not only the sharding demo of
§3.1 — it is what makes the ordering guarantee real. If one account's events
were spread across partitions, several source subtasks would read them in
parallel and their arrival order at the keyed operator would be
nondeterministic, which is exactly the lost update §9.5 tests for.

`java/` closes the gap with a single class, `RowFieldSerializationSchema`, that
serializes one field of a `Row` to UTF-8 bytes: field 0 becomes the key, field 1
the value. `job.py` constructs it through py4j and hands it to the normal
`KafkaSink`. It has to be Java rather than a Python callback because a
serialization schema is shipped to every TaskManager through Java
serialization.

The cost is honest: this is the one place the "no JVM code" goal of §0 does not
hold. It is bounded — nobody needs a JDK or Maven installed, because the JAR is
built in the image's first stage — but it is Java in the repository. The
alternative is a Table API sink (`key.format='raw'` + `key.fields`), which needs
no Java at all and was what this project used first; it works, at the cost of
bridging the DataStream through a `StreamTableEnvironment` and a
`StatementSet`. Either is defensible. This one keeps the job a plain DataStream
pipeline that reads the way §5 describes.

**2. Side outputs are `yield tag, value`, not `ctx.output(...)`.**
PyFlink's `KeyedProcessFunction.Context` has no `output()` method;
`process_element` is a generator.

**3. `from_source` needs a real `WatermarkStrategy`.** `None` raises.

**4. `StateTtlConfig.Time` does not exist.** It is
`pyflink.common.time.Time`.

**5. `key_by(lambda v: json.loads(v)["account_id"])` crashes on every
`transfer_requested`.** That event has no `account_id` field (§4) — it carries
`source_account`. `shard_key_of` handles both, leaving the wire format exactly as
§4 specifies.

**6. Deduplication is keyed by `(request_id, leg)`, not `request_id`.**
A request_id is not a unit of work — one transfer touches three accounts. With a
bare request_id:

- if `destination_account == fees_account`, the second credit is swallowed as a
  duplicate and the fee silently vanishes;
- if `source_account == destination_account`, the debit marks the id as
  processed and the matching credit is then discarded — money disappears.

Each emitted event now carries a `leg` (`debit`, `credit:destination`,
`credit:fees`), which is additive to the §4 schemas. Both cases are tested.

**7. A declined request is marked processed.** §5.3 marks only approved
requests. That leaves a real at-least-once hazard: a request declined for
insufficient funds, redelivered after the account is topped up, would be
approved the second time — the same request settling twice, differently. A
verdict is now final.

**8. The decline path emits its status through the loopback only.** §5.3 emits
`declined_payment` *and* a status event, so every decline produces two identical
verdicts on `transfer-status`. Dropping the direct emission makes decline
symmetric with approval: both statuses are published only once the outcome is
durably in the account's own log. Costs one extra Kafka hop of latency on the
decline path; flip it in `domain.py` if you would rather have the latency back.

**9. `GET /transfer/{id}/status` returns 200 `pending`, not 404.** §6 allows
either. The request exists and is in flight; 404 reads as "never heard of it".

**10. The WebSocket has a timeout** (30s, configurable). §6 holds the connection
open indefinitely, which leaks a connection per request that never resolves.
On timeout it answers `pending` and closes.

**11. The status consumer uses a unique group id per process.** Every gateway
instance has to see every partition of `transfer-status`; a shared group would
split partitions across instances, and a socket waiting on one instance would
never learn about a verdict delivered to another. Set `STATUS_CONSUMER_GROUP` to
pin it.

**12. `outgoing_payment.amount` is the full debit, not the transfer amount.**
The §4 example shows `1100` for a transfer of 1100 with a fee of 25, but the
source account was actually debited 1125. Recording 1100 leaves the fee
unaccounted for on the source's own log, and the ledger stops reconciling:
`sum(outgoing) == sum(incoming)` is what makes conservation checkable, and with
1100 it fails by exactly the fee.

**13. The gateway's producer is pinned to `murmur2_random`.**
Found by running it, not by reading it. librdkafka (the gateway) defaults to
`consistent_random`, which hashes keys with CRC32; the Java client (the Flink
sink) hashes with murmur2. On the default, `acc-123` went to partition 1 when
the gateway wrote it and partition 5 when Flink wrote it — one account's log
split across two shards. That is not cosmetic: two source subtasks then read
that account concurrently, arrival order at the keyed operator becomes
nondeterministic, and the sequential-per-account property the whole design rests
on is gone. `gateway/kafka_config.py` pins the Java-compatible partitioner, and
a test asserts it.

## Verified

All six §9 scenarios were run against the live stack:

| # | Scenario | Result |
|---|---|---|
| 1 | Happy path — 3 fan-out events, correct balances | pass |
| 2 | Insufficient funds — declined, no balance change | pass |
| 3 | Duplicate `transfer_requested` — one debit only | pass |
| 4 | Crash recovery — TaskManager killed mid-flight | pass |
| 5 | Two requests on one account — applied in order | pass |
| 6 | Sharding — one `account_id`, one partition | pass |

Scenario 4 killed `flink-taskmanager` with five transfers in flight. The job
restarted from its checkpoint and the crash produced a genuine at-least-once
redelivery — one leg appears twice on `account-events` — which the
`(request_id, leg)` guard absorbed: 52 legs were applied to a balance, each
exactly once. In every run the ledger was reconciled from the event log alone:
the total across all accounts equalled the seeded total, to the cent.

## Naming

Everything — schema, ORM, DTOs, routes, and the spec itself — uses English.
Earlier drafts of the spec named the domain in Spanish (`cuentas`, `saldo`,
`sucursales`); both were brought in line so there is one vocabulary, not a
mapping to hold in your head.

Two tests keep that honest rather than trusting a rename pass:

- `test_schema_alignment.py` parses `init.sql` and asserts the ORM maps exactly
  the columns the schema declares.
- `test_controller_dto_alignment.py` asserts every `body.<field>` a controller
  reads is declared by its DTO.

Both were written after a global rename passed all 77 tests while the live API
returned 500 twice. Fakes mirror whatever the code says, so only the real schema
can catch a mapping that drifted. The same rename also turned `deactivate` into
`deactivete` in eight places — `activa` is a substring of de-activa-te — and
every test still passed, because it was corrupted consistently.

## Frontend notes

- **Amounts are entered in cents**, matching the API, with a live formatted
  preview under the field. Converting in the UI would mean parsing a decimal
  into cents, which is the one place a float rounding error can quietly change
  the amount the ledger sees.
- **The verdict arrives over the WebSocket**; if the socket closes without
  delivering one, the page falls back to `GET /transfer/{id}/status`, the pull
  endpoint the gateway offers for exactly that case (§6).
- **A gateway timeout is not a decline.** When the socket answers `pending`, the
  page says "Still pending" and offers a re-check rather than claiming a
  verdict it did not receive.
- **A verdict for an abandoned transfer is dropped**, so a late message cannot
  overwrite the result of a newer request.

## Notes and known limits

- **The fee is flat** (`FEE_FLAT_CENTS`, default 25 — matching the §4 example),
  capped at the transfer amount. §6 left the model open; flat keeps every amount
  exact with no rounding rule to argue about.
- **Sinks are at-least-once**, per §5.6. Checkpointing is `EXACTLY_ONCE` for
  Flink's internal state, which is what protects `balance` and `processed_ids`.
- **`POST /transfer` does not wait for the broker ack**, per §6. A broker
  outage surfaces in the producer's delivery callback (logged), not in the HTTP
  response.
- **Balances are Flink state, not a queryable store.** There is no
  `GET /accounts/{id}/balance`; the spec does not define one. Inspect state
  through the emitted events in AKHQ.
- **`flink-job-submitter` skips submission if any job is already RUNNING**, so a
  compose restart cannot start a second ledger over the same topic.
