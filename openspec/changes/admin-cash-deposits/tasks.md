# Tasks: admin-cash-deposits

## Preflight

| Field | Value |
|-------|-------|
| change | admin-cash-deposits |
| execution_mode | auto |
| artifact_store.mode | openspec |
| delivery_strategy | single-pr |
| chain_strategy | n/a (single-pr) |
| review_budget_lines | 3000 |
| design §7 | 7 work units ~1100 lines |
| test strategy §8 | Strict TDD `/opt/anaconda3/bin/python3 -m pytest` |

delivery_strategy: single-pr
chain_strategy: n/a (single-pr)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1100 (migrations 80, models 30, repos 120, waiter/consumer 160, config/app 60, DTO/router 140, Flink 120, compose 30, tests 350) |
| 400-line budget risk | High (1100 > 400) |
| 3000-line budget risk | Low (1100 < 3000) |
| Chained PRs recommended | No |
| Suggested split | single PR — 7 commits PR-ready if overage |
| Delivery strategy | single-pr |
| Chain strategy | n/a (single-pr) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: n/a (single-pr)
400-line budget risk: High
3000-line budget risk: Low

> Single-PR holds (<3000). 400-guard High but absorbed; commits slice-ready. Do NOT chain — orchestrator owns strategy.

## Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Relax `transactions` | PR1 c1 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_transaction_model_deposit.py -v` | `alembic upgrade/downgrade` | `2026-09-07_relax_transactions_for_deposits.py` + `models.py` |
| 2 | `deposits` table + repo | PR1 c2 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_postgres_deposit_repository.py -v` | `psql \d deposits` | `2026-09-07_add_deposits_table.py`, `DepositORM`, `interfaces/deposit_repository.py`, `repos/postgres_deposit_repository.py` |
| 3 | `deposit-status` waiter/consumer + wiring | PR1 c3 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_status_registry.py openbankapi/tests/unit/test_deposit_status_consumer.py -v` | `docker compose config \| grep deposit-status` | `status_registry.py` alias, `config.py`, `consumers/deposit_status_consumer.py`, `dependencies.py`, `app.py`, `main.py` |
| 4 | `POST /admin/deposits` DTO/router | PR1 c4 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_deposit_dto.py openbankapi/tests/integration/test_deposit_router.py -v` | `httpx AsyncClient POST /admin/deposits` fakes | `dtos/deposit_dto.py`, `routers/deposit_router.py`, `api/v1/main.py` |
| 5 | Flink `domain.py`/`job.py` | PR1 c5 | `/opt/anaconda3/bin/python3 -m pytest account-service/tests/test_domain_deposit.py -v` | `pytest account-service/tests/` | `account-service/domain.py`, `account-service/job.py` |
| 6 | `TransactionConsumer` routing | PR1 c6 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_transaction_consumer_deposit.py -v` | FakeSession redelivery×2 | `consumers/transaction_consumer.py`, `repos/postgres_transaction_repository.py` |
| 7 | Compose/kafka-init | PR1 c7 | `docker compose config` | `kafka-topics --describe` | `docker-compose.yml` |

## Phase 1: Foundation — DB & Repo (WU1-2)

TDD: RED must FAIL before GREEN. Use `pg_insert ON CONFLICT DO NOTHING RETURNING`, `gen_random_uuid`, `BigInteger` cents, `deposits_movement_id_key/fkey`.

- [x] 1.1 RED — `transactions` relax guard — Files: `openbankapi/tests/unit/test_transaction_model_deposit.py` — G: `TransactionORM` CHECK `('debit','credit','declined')` NOT NULL — W: insert `type='deposit'` `counterparty=None` `50000` — T: rejects — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_transaction_model_deposit.py -v` FAIL
- [x] 1.2 GREEN — Relax migration+model — Files: `openbankapi/infra/database/migrations/versions/2026-09-07_relax_transactions_for_deposits.py`, `openbankapi/infra/database/schemas/models.py` — G: `counterparty: Mapped[str|None]` CHECK `IN ('debit','credit','declined','deposit')` — W: `alembic upgrade head` insert EUR `1234567890123456` `50000` NULL — T: succeeds; downgrade removes `deposit` rows restores NOT NULL — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_transaction_model_deposit.py -v` PASS
- [x] 1.3 RED — `deposits` contract — Files: `openbankapi/tests/integration/test_postgres_deposit_repository.py` — G: no table — W: `IDepositRepository.insert(movement_id, admin-42, 'cash branch 42')` assert `ON CONFLICT(movement_id)` — T: fails — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_postgres_deposit_repository.py -v` FAIL
- [x] 1.4 GREEN — `deposits` table — Files: `openbankapi/infra/database/migrations/versions/2026-09-07_add_deposits_table.py`, `openbankapi/infra/database/schemas/models.py` — G: `deposits(id UUID PK gen_random_uuid, movement_id UUID UNIQUE FK transactions(id) CASCADE, admin_id VARCHAR(100), reason VARCHAR(300), created_at TIMESTAMPTZ)` — W: inspect `transactions` — T: no `admin_id`/`reason` cols — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_postgres_deposit_repository.py::test_deposits_fk_exists -v`
- [x] 1.5 GREEN — Repo impl — Files: `openbankapi/infra/database/interfaces/deposit_repository.py`, `openbankapi/infra/database/repositories/postgres_deposit_repository.py`, `openbankapi/infra/database/repositories/__init__.py` — G: `movement_id` from `50000` tx — W: `insert` twice — T: 1 row (`ON CONFLICT DO NOTHING`) — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_postgres_deposit_repository.py -v`

## Phase 2: App — Waiter/Consumer + Config (WU3)

Reuse `StatusRegistry`; per-process uuid4 group.

- [ ] 2.1 RED — Registry — Files: `openbankapi/tests/integration/test_deposit_status_registry.py` — G: `StatusRegistry(10_000)` — W: `wait_for('xyz',0.2)` no resolve → `None`; `resolve_threadsafe({request_id:'xyz', approved, new_balance:150000})` → resolves — T: fails before alias — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_status_registry.py -v` FAIL
- [ ] 2.2 GREEN — Alias+DI — Files: `openbankapi/infra/kafka/status_registry.py`, `openbankapi/config/dependencies.py` — G: `DepositStatusRegistry=StatusRegistry` + `get_deposit_status_registry` `DepositStatusRegistryDep` — W: import — T: alias is same class — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_status_registry.py::test_alias -v`
- [ ] 2.3 RED — Consumer dispatch — Files: `openbankapi/tests/unit/test_deposit_status_consumer.py` — G: missing `DepositStatusConsumer` — W: fake raw `{"request_id":"r1","status":"approved","new_balance":145540}` — T: not resolved — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_deposit_status_consumer.py -v` FAIL
- [ ] 2.4 GREEN — Consumer — Files: `openbankapi/infra/kafka/consumers/deposit_status_consumer.py` — G: `auto.commit=False` `earliest` `poll 0.5` `group openbankapi-deposit-status-{uuid4}` — W: `_dispatch(json.loads(raw))→resolve_threadsafe` — T: `wait_for('r1',10.0)` resolves — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_deposit_status_consumer.py -v`
- [ ] 2.5 GREEN — Config/app — Files: `openbankapi/config/config.py`, `openbankapi/app.py`, `openbankapi/main.py` — G: `deposit_status_topic='deposit-status'` — W: `create_app(...,deposit_status_registry)` `lifespan.bind_loop` — T: `app.state.deposit_status_registry` bound — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_status_registry.py openbankapi/tests/unit/test_deposit_status_consumer.py -v`

## Phase 3: API — DTO + Router (WU4)

Cents, `WriteAdminDep=require_permissions('write:admin')`, `admin_id=claims['sub']`.

- [ ] 3.1 RED — DTO — Files: `openbankapi/tests/unit/test_deposit_dto.py` — G: `DepositRequestDTO` `^[0-9]{16}$` `amount>0` `EUR|GBP|USD` `reason<=300` — W: `amount 0/-1`, `123`, `JPY`, `x*301` — T: 422 `amount must be positive` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_deposit_dto.py -v` FAIL
- [ ] 3.2 GREEN — DTOs — Files: `openbankapi/api/v1/dtos/deposit_dto.py` — G: EUR `1234567890123456` `50000` — W: `DepositRequestDTO(50000)` + `DepositResponseDTO(approved True, amount_applied 50000, applied_rate None, new_balance 150000)` omit-null — T: valid — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/unit/test_deposit_dto.py -v`
- [ ] 3.3 RED — Router — Files: `openbankapi/tests/integration/test_deposit_router.py` — G: fakes `account_repo/publisher/fx_cache/registry` — W: POST `9999999999999999 50000`→404 no publish; `0`→422; stopped `50000`→504 zero rows; happy `50000`→200 — T: fails — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_router.py -v` FAIL
- [ ] 3.4 GREEN — Router impl — Files: `openbankapi/api/v1/routers/deposit_router.py` — G: bal `100000` EUR — W: POST `{"account_number":"1234567890123456","amount":50000,"currency":"EUR","reason":"cash branch 42"}` `sub admin-42` → same `50000` null `150000`; cross USD `50000` `rates EUR 0.92`→`45540` `USD_EUR` `0.9108` margin `0.01`; timeout `10.0`→504 — T: 200/404/422/504 correct — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_router.py -v`
- [ ] 3.5 GREEN — Wiring — Files: `openbankapi/api/v1/main.py` — G: `api_router.include_router(deposit_router.router)` — W: `GET /openapi.json` — T: has `POST /admin/deposits` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_deposit_router.py::test_openapi_has_deposit -v`

## Phase 4: Flink — `domain.py`/`job.py` (WU5)

No `conversion_service` import. `dedup_key(request_id,LEG_DEPOSIT)` TTL7d.

- [ ] 4.1 RED — Domain — Files: `account-service/tests/test_domain_deposit.py` — G: bal `100000` `r1 45540` — W: `decide(deposit r1)` — T: `new_balance 145540` 1 `balance_event` 1 `deposit_confirmed` 1 `deposit-status approved`; `50000`→`150000` omit rate; `r1:LEG_DEPOSIT` redelivered→noop — V: `/opt/anaconda3/bin/python3 -m pytest account-service/tests/test_domain_deposit.py -v` FAIL
- [ ] 4.2 GREEN — `domain.py` — Files: `account-service/domain.py` — G: `LEG_DEPOSIT='deposit'` — W: `_on_deposit` `dedup_key`+`is_processed` — T: `Decision(new_balance, dedup_keys, account_events, status_events, balance_events)` — V: `/opt/anaconda3/bin/python3 -m pytest account-service/tests/test_domain_deposit.py -v`
- [ ] 4.3 RED — Job sink — Files: `account-service/tests/test_job_deposit_sink.py` — G: no `DEPOSIT_STATUS_TAG` — W: `process_element` yields `status_events` — T: no side output — V: `/opt/anaconda3/bin/python3 -m pytest account-service/tests/test_job_deposit_sink.py -v` FAIL
- [ ] 4.4 GREEN — `job.py` — Files: `account-service/job.py` — G: `DEPOSIT_STATUS_TAG OutputTag('deposit-status-events')` `DEPOSIT_STATUS_TOPIC='deposit-status'` — W: `account_events→account-events` `shard_key_of(account_id)` + `Row(request_id, json.dumps(status))` `_kafka_sink(DEPOSIT_STATUS_TOPIC)` key0 — T: `approved new_balance` routed — V: `/opt/anaconda3/bin/python3 -m pytest account-service/tests/test_job_deposit_sink.py account-service/tests/test_domain_deposit.py -v`

## Phase 5: Persistence — `TransactionConsumer` (WU6)

Orphan guard: `RETURNING id` first; `None`→skip `applied_rates`/`deposits`.

- [ ] 5.1 RED — Routing — Files: `openbankapi/tests/integration/test_transaction_consumer_deposit.py` — G: `deposit_confirmed r2 50000` — W: `_apply` fake session — T: `transactions deposit 50000 NULL` `deposits admin-42`; cross `45540`→`applied_rates` set; duplicate `(r1,1234567890123456,deposit)`→`None` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_transaction_consumer_deposit.py -v` FAIL
- [ ] 5.2 GREEN — Impl — Files: `openbankapi/infra/kafka/consumers/transaction_consumer.py`, `openbankapi/infra/database/repositories/postgres_transaction_repository.py` — G: `deposit_confirmed→deposit` `counterparty None` `pg_insert(...).on_conflict_do_nothing(...).returning(id)` — W: `None`→return; `applied_rate`→insert+`UPDATE` same `begin()` then `deposit_repo.insert ON CONFLICT` — T: idempotent — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_transaction_consumer_deposit.py -v`
- [ ] 5.3 GREEN — Idempotent — Files: `openbankapi/tests/integration/test_transaction_consumer_deposit.py` — G: redelivery×2 `r1` — W: dispatch twice — T: 1 `transactions` 1 `deposits` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/integration/test_transaction_consumer_deposit.py::test_redelivery_idempotent -v`

## Phase 6: Infra — Compose (WU7)

- [ ] 6.1 GREEN — Compose — Files: `docker-compose.yml` — G: `kafka-init` `deposit-status` 3p `delete` `604800000` — W: `docker compose config` — T: has topic + `DEPOSIT_STATUS_TOPIC` envs Flink/API — V: `docker compose config | grep -q deposit-status`

## Phase 7: Verification — Spec §11 & §12

- [ ] 7.1 GREEN — §11 order — Files: `openbankapi/tests/integration/test_deposit_router.py`, `account-service/tests/test_domain_deposit.py`, `openbankapi/tests/integration/test_transaction_consumer_deposit.py`, `openbankapi/tests/contract/test_deposit_events.py` — G: 1) EUR `50000` bal `100000`→+`50000` 1/1; 2) cross `get_rates 0.92`→`45540`; 3) FK conditional; 4) timeout→504 zero; 5) redelivery×2→1/1 — T: pass — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/ account-service/tests/test_domain_deposit.py -v`
- [ ] 7.2 GREEN — Events+audit — Files: `openbankapi/tests/contract/test_deposit_events.py` — G: `deposit→account-events` key `shard_key_of` has `request_id account_id 50000 EUR amount_applied leg LEG_DEPOSIT ts` murmur2; `deposit_confirmed` omit null; `deposit-status` key `request_id` 3p `approved new_balance` — W: inspect `transactions` — T: no `admin_id`/`reason` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/contract/test_deposit_events.py -v`
- [ ] 7.3 Final — Checklist — Files: `openspec/changes/admin-cash-deposits/specs/admin-cash-deposits/spec.md` (read-only) — G: any §12 unchecked — W: release — T: blocked — V: `ruff check --fix openbankapi && ruff format openbankapi && /opt/anaconda3/bin/python3 -m pytest -q`
