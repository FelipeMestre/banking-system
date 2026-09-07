# Apply Progress: credit-card-used-balance

**Change**: credit-card-used-balance
**Mode**: Strict TDD
**Work Units**: 6 (single PR, size:exception, 880 lines)
**Status**: 17/17 tasks complete. Ready for verify.

## Completed Tasks
- [x] 1.1 RED migration test FAIL
- [x] 1.2 GREEN migration + ORM
- [x] 1.3 RED card_balance_event FAIL
- [x] 1.4 GREEN CardBalanceUpdated from_payload
- [x] 2.1 RED dto used_credit FAIL
- [x] 2.2 GREEN ICardBalanceProjection + _UPDATABLE
- [x] 2.3 GREEN CardAccountResponseDTO
- [x] 2.4 GREEN PostgresCardBalanceProjection + fake
- [x] 3.1 RED domain card-balance FAIL
- [x] 3.2 GREEN emit only if new_used_credit not None
- [x] 3.3 RED job sink FAIL
- [x] 3.4 GREEN CARD_BALANCES_TAG Row + AT_LEAST_ONCE
- [x] 4.1 RED consumer FAIL
- [x] 4.2 GREEN CardBalanceConsumer
- [x] 4.3 GREEN config + compose 6p compact RF1
- [x] 5.1 GREEN E2E $300->30000 S11
- [x] 5.2 GREEN final

## Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `openbankapi/infra/database/migrations/versions/2026-09-06_add_card_accounts_used_credit.py` | Created | `used_credit BIGINT NOT NULL DEFAULT 0 server_default="0"` reversible |
| `openbankapi/infra/database/migrations/versions/2026-09-07_relax_transactions_for_deposits.py` | Modified (enabling repair, 0-line behavioral, chore) | Linearized `8f7e6d5c4b3a` down_revision `a1b2c3d4e5f6` → `c3d4e5f6a7b8` to fix pre-existing `MultipleHeads` blocking `alembic upgrade head`; single head now `f1a2b3c4d5e6` (`2026-09-06_add_card_accounts_used_credit.py`); rollback boundary `8f7e6d5c4b3a` via `c3d4e5f6a7b8` (reverting restores `a1b2c3d4e5f6` dual-head); no spec/design scope change |
| `openbankapi/infra/database/schemas/models.py` | Modified | `CardAccountORM.used_credit` BigInteger server_default 0 + sole-writer docstring |
| `openbankapi/domain/model/card_account.py` | Modified | `CardAccount.used_credit: int = 0` |
| `openbankapi/domain/events/card_balance_updated.py` | Created | `CardBalanceUpdated.from_payload` negative allowed, raises ValueError/KeyError, no ge=0 |
| `openbankapi/domain/events/__init__.py` | Modified | Export CardBalanceUpdated |
| `openbankapi/infra/database/interfaces/card_account_repository.py` | Modified | Added `ICardBalanceProjection.apply_used_credit(UUID,int)->bool` sole-writer port |
| `openbankapi/infra/database/interfaces/__init__.py` | Modified | Export ICardBalanceProjection |
| `openbankapi/api/v1/dtos/card_account_dto.py` | Modified | `CardAccountResponseDTO.used_credit: int` from_attributes=True |
| `openbankapi/infra/database/repositories/postgres_card_account_repository.py` | Modified | `_to_domain` includes used_credit, `_UPDATABLE` excludes used_credit, `PostgresCardBalanceProjection` with `UPDATE ... bool(rowcount)` and own sessionmaker |
| `openbankapi/infra/database/repositories/__init__.py` | Modified | Export PostgresCardBalanceProjection |
| `openbankapi/tests/fakes.py` | Modified | Fake mirrors used_credit and apply_used_credit, preserves through updates |
| `card-service/domain.py` | Modified | `Decision.card_balance_events` + `_card_balance` helper, emit only if new_used_credit is not None |
| `card-service/job.py` | Modified | `CARD_BALANCES_TOPIC` default card-balances, `CARD_BALANCES_TAG=OutputTag("card-balance-events", RECORD_TYPE)`, yield `Row(card_account_id, json.dumps(event))` keyed card_account_id, sink AT_LEAST_ONCE |
| `openbankapi/infra/kafka/consumers/card_balance_consumer.py` | Created | `CardBalanceConsumer` thread daemon, earliest, auto.commit False, poll 0.5, 30s timeout, cache.delete after write only if bool(rowcount) |
| `openbankapi/infra/kafka/consumers/__init__.py` | Modified | Export CardBalanceConsumer |
| `openbankapi/config/config.py` | Modified | `card_balances_topic`/`card_balance_consumer_group` defaults card-balances/openbankapi-card-balances via env |
| `docker-compose.yml` | Modified | kafka-init 6p compact RF1 card-balances, env CARD_BALANCES_TOPIC to flink-card-* + openbankapi |
| `openbankapi/main.py` | Modified | Wire PostgresCardBalanceProjection -> CardBalanceConsumer start/stop |
| `openbankapi/tests/test_card_account_dto_used_credit.py` | Created | RED then GREEN for DTO/Port |
| `card-service/tests/test_card_balance_event.py` | Created | RED then GREEN for event |
| `card-service/tests/test_domain_card_balance.py` | Created | RED then GREEN for domain emit |
| `card-service/tests/test_job_card_balance_sink.py` | Created | RED then GREEN for job sink |
| `openbankapi/tests/test_card_balance_consumer.py` | Created | RED then GREEN for consumer |
| `openbankapi/tests/test_card_balances_e2e.py` | Created | E2E $300->30000 etc S11 |

## TDD Cycle Evidence
| Task | RED (test written first) | GREEN (implementation passes) | REFACTOR |
|------|--------------------------|-------------------------------|----------|
| 1.1-1.2 migration | FAIL `test_card_accounts_has_used_credit_column` AssertionError missing | PASS 5 passed after migration | — |
| 1.3-1.4 event | FAIL ModuleNotFoundError card_balance_updated | PASS 4 passed | — |
| 2.1-2.4 DTO/port | FAIL 5 failed (DTO missing, port missing) | PASS 7 passed | — |
| 3.1-3.2 domain | FAIL 2 failed missing card_balance_events | PASS 3 passed | — |
| 3.3-3.4 job | FAIL missing CARD_BALANCES_TAG | PASS 2 passed | — |
| 4.1-4.2 consumer | FAIL ModuleNotFoundError | PASS 6 passed | — |
| 5.1 E2E | — | PASS 4 passed | — |

## Work Unit Evidence
| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|------|----------------------------------------|--------------------------------------------------|-------------------|
| c1 DDL+ORM | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_credit_card_migration.py -v` 5 passed | `alembic upgrade` head -> column exists; `alembic downgrade` -> column dropped, then re-upgrade | `2026-09-06_add_card_accounts_used_credit.py` + `models.py` + `card_account.py` |
| c2 Port+DTO | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_account_dto_used_credit.py -v` 7 passed | `GET /card-accounts/{id}` via FakeHarness returns used_credit 30000, GET /cards has no used_credit | `interfaces/card_account_repository.py` + `dtos/card_account_dto.py` + `postgres_card_account_repository.py` (port+DTO+fakes) |
| c3 Event | `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_card_balance_event.py -v` 4 passed | `import CardBalanceUpdated` valid/negative parse, malformed raises | `domain/events/card_balance_updated.py` |
| c4 Flink | `/opt/anaconda3/bin/python3 -m pytest card-service/tests/test_domain_card_balance.py -v` 3 passed + `test_job_card_balance_sink.py` 2 passed | `pytest card-service/tests/` all pass; Row(card_account_id, json) AT_LEAST_ONCE murmur2 (no partitioner) | `card-service/domain.py` + `card-service/job.py` |
| c5 Consumer | `/opt/anaconda3/bin/python3 -m pytest openbankapi/tests/test_card_balance_consumer.py -v` 6 passed | replay×3 converges 12345, poison dropped, unknown False no delete | `consumers/card_balance_consumer.py` |
| c6 Config+compose | `docker compose config \| grep -q card-balances` found 4 hits | `docker compose config` shows CARD_BALANCES_TOPIC in all services; `kafka-init` 6p compact | `config/config.py` + `docker-compose.yml` + `main.py` |

## Enabling Repair (0-line, chore — pre-existing blocker, no spec/design scope change)

- **File**: `openbankapi/infra/database/migrations/versions/2026-09-07_relax_transactions_for_deposits.py` (`8f7e6d5c4b3a`) — down_revision linearization `a1b2c3d4e5f6` → `c3d4e5f6a7b8`.
- **Pre-existing blocker**: `a1b2c3d4e5f6` (`2026-09-06_add_statement_totals.py`) had two divergent children `b2c3d4e5f6a7` → `c3d4e5f6a7b8` and `8f7e6d5c4b3a` → `9a8b7c6d5e4f`, causing `alembic upgrade head` to fail with `MultipleHeads` before any change in this task. Not introduced by this change.
- **Repair**: single-line metadata fix `down_revision = "c3d4e5f6a7b8"` (8f7e now follows c3d). History is now linear: `f3c8d1a5e9b7 → a1b2c3d4e5f6 → b2c3d4e5f6a7 → c3d4e5f6a7b8 → 8f7e6d5c4b3a → 9a8b7c6d5e4f → f1a2b3c4d5e6` with single head `f1a2b3c4d5e6` (`2026-09-06_add_card_accounts_used_credit.py`).
- **Rollback boundary**: revert that one line restores `a1b2c3d4e5f6` and re-creates dual heads (`c3d4e5f6a7b8` and `8f7e6d5c4b3a` as branches); no data or constraint change beyond ordering — `upgrade`/`downgrade` payload of `8f7e6d5c4b3a` unchanged.
- **No spec/design scope change**: no new requirement, no design decision altered; the file is not listed in proposal Affected Areas for this change and the behavior (nullable `counterparty_account`, `type IN ('debit','credit','declined','deposit')`) is unchanged.
- **Evidence**: `alembic history` shows single head `f1a2b3c4d5e6`; `alembic upgrade head` and `alembic downgrade -1`/`upgrade` succeed (documented in Issues Found); `tasks.md` 0.1 maps this as chore/enabler.

## Deviations from Design
None — implementation matches design.md (sole-writer port, raw int no ge=0, Row shape, after-write cache only if rowcount, GET /cards untouched).

## Issues Found
- Multiple heads in migration history (a1b -> b2c/c3d and a1b -> 8f/9a) caused `alembic upgrade head` to fail with MultipleHeads. Fixed by linearizing 8f7e6d5c4b3a down_revision from a1b2c3d4e5f6 to c3d4e5f6a7b8, making single head before adding used_credit migration. This is a history fix, not a spec deviation.
- 8 foreign_exchange_quote_router tests fail pre-existing (Auth0 not configured) — verified via stash pop still fails on original branch, not caused by this change.

## Remaining Tasks
None.

## Workload / PR Boundary
- Mode: single PR size:exception (maintainer-approved)
- Current work unit: all 6 c1-c6
- Boundary: fresh branch feature/credit-card-used-balance from d80ba05 to HEAD (880 lines)
- Estimated review budget impact: 880 lines (>800) — exception-ok, 6 commits each <400, story tells via work-unit commits

## Status
17/17 tasks complete. Ready for verify.
