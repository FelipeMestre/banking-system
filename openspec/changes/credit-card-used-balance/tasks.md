# Tasks: credit-card-used-balance

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~680 |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

## Suggested Work Units

| Unit | Goal | PR | Test | Harness | Rollback |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | DDL+ORM | c1 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_credit_card_migration.py -v` | `alembic upgrade` | `2026-09-06_add_card_accounts_used_credit.py` |
| 2 | Port+DTO | c2 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_dto_used_credit.py -v` | `GET /card-accounts/{id}` | `interfaces/card_account_repository.py` |
| 3 | Event | c3 | `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_card_balance_event.py -v` | `import` | `domain/events/card_balance_updated.py` |
| 4 | Flink | c4 | `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_domain_card_balance.py -v` | `pytest card-service/tests/` | `card-service/job.py` |
| 5 | Consumer | c5 | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_balance_consumer.py -v` | `replay×3` | `consumers/card_balance_consumer.py` |
| 6 | Config+compose | c6 | `docker compose config | grep card-balances` | `kafka-topics --describe` | `docker-compose.yml` |

## Phase 1: Foundation

- [x] 1.1 RED `openbankapi/tests/test_credit_card_migration.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_credit_card_migration.py -v` FAIL
- [x] 1.2 GREEN `used_credit BIGINT NOT NULL DEFAULT 0 server_default="0"`  + ORM sole-writer docstring + `CardAccount.used_credit` — `openbankapi/infra/database/migrations/versions/2026-09-06_add_card_accounts_used_credit.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_credit_card_migration.py -v` PASS
- [x] 1.3 RED `card-service/tests/test_card_balance_event.py` (canonical; `openbankapi/tests/test_card_balance_event.py` is identical duplicate added in same commit aff2570) — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_card_balance_event.py -v` FAIL
- [x] 1.4 GREEN `from_payload` negative allowed — `openbankapi/domain/events/card_balance_updated.py` — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_card_balance_event.py -v` PASS

## Phase 2: Ports & DTO

- [x] 2.1 RED `openbankapi/tests/test_card_account_dto_used_credit.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_dto_used_credit.py -v` FAIL
- [x] 2.2 GREEN `ICardBalanceProjection`; `_UPDATABLE` excludes `used_credit` — `openbankapi/infra/database/interfaces/card_account_repository.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_dto_used_credit.py -v` PASS
- [x] 2.3 GREEN `CardAccountResponseDTO.used_credit` `from_attributes=True` 5 returns `GET /cards` excludes — `openbankapi/api/v1/dtos/card_account_dto.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_dto_used_credit.py -v` PASS
- [x] 2.4 GREEN `PostgresCardBalanceProjection` `bool(rowcount)` + fake — `openbankapi/infra/database/repositories/postgres_card_account_repository.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_service.py -v` PASS

## Phase 3: Flink

- [x] 3.1 RED `card-service/tests/test_domain_card_balance.py` — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_domain_card_balance.py -v` FAIL
- [x] 3.2 GREEN emit only if `new_used_credit is not None` not decline/`noop()` — `card-service/domain.py` — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_domain_card_balance.py -v` PASS
- [x] 3.3 RED `card-service/tests/test_job_card_balance_sink.py` — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_job_card_balance_sink.py -v` FAIL
- [x] 3.4 GREEN `CARD_BALANCES_TAG` `Row(card_account_id,json.dumps(event))` `Row[kafka_key,payload]` keyed `card_account_id` `AT_LEAST_ONCE` murmur2_random — `card-service/job.py` — V: `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_job_card_balance_sink.py -v` PASS

## Phase 4: Consumer & Platform

- [x] 4.1 RED `openbankapi/tests/test_card_balance_consumer.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_balance_consumer.py -v` FAIL
- [x] 4.2 GREEN `openbankapi-card-balances` `earliest` `auto.commit=False` `poll(0.5)` `30s` after-write `cache.delete` only if `bool(rowcount)` — `openbankapi/infra/kafka/consumers/card_balance_consumer.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_balance_consumer.py -v` PASS
- [x] 4.3 GREEN `card_balances_topic` `card-balances`; `kafka-init` 6p `compact` `--replication-factor 1` RF1; env `flink-card-*`+`openbankapi` — `openbankapi/config/config.py`, `docker-compose.yml` — V: `docker compose config | grep -q card-balances` PASS

## Phase 5: Verification

- [x] 5.1 GREEN E2E $300→30000 S11 — `openbankapi/tests/test_card_balances_e2e.py` — V: `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_balances_e2e.py -v` PASS
- [x] 5.2 GREEN final — `openspec/changes/credit-card-used-balance/specs/card-accounts/spec.md` (read-only) — V: `/opt/anaconda3/bin/python3 -m pytest -q` PASS

## Enabling Repair (0-line chore — pre-existing blocker, no behavioral change)

- [x] 0.1 Chore/enabler: Linearize `openbankapi/infra/database/migrations/versions/2026-09-07_relax_transactions_for_deposits.py` (`8f7e6d5c4b3a`) down_revision `a1b2c3d4e5f6` → `c3d4e5f6a7b8` to fix pre-existing `MultipleHeads` blocking `alembic upgrade head`; single head now `f1a2b3c4d5e6` (`2026-09-06_add_card_accounts_used_credit.py`); rollback boundary is `8f7e6d5c4b3a` via `c3d4e5f6a7b8` (reverting restores `a1b2c3d4e5f6` and re-creates dual heads `c3d4e5f6a7b8`/`8f7e6d5c4b3a`); no spec/design scope change — Evidence: `alembic history` linear `f3c8d1a5e9b7 → a1b2c3d4e5f6 → b2c3d4e5f6a7 → c3d4e5f6a7b8 → 8f7e6d5c4b3a → 9a8b7c6d5e4f → f1a2b3c4d5e6` single head; `alembic upgrade head` succeeds then `downgrade`/`upgrade` verified
