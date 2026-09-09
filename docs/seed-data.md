# Demo Seed Data

Pure-event, idempotent seed tied to `AUTH0_SUB=auth0|6a90f3247c7a4be23a0edc80`.

## What it creates

- **Customer** `Demo User` (`identification_number=SEED-A0EDC80`, `dob 1990-01-15`, `gender M`) linked to the demo Auth0 sub. Reused if exists.
- **Accounts** (3× USD, via `AccountService.open_account`):
  - `USD-PRIMARY` — paying account for cards — `$5,000` opening credit
  - `USD-SAVINGS` — `$2,000`
  - `USD-EXTRA` — `$1,000`
  Opening balances are published as `incoming_payment` `credit:seed` on `account-events` (never a direct `UPDATE accounts.balance`) — Flink's `account-service` projects them to `account-balances` within one checkpoint (~5s).
- **Card Accounts** (2× via `CardAccountService.issue_card_account`, paying account = PRIMARY):
  - CardA limit `$5,000` — later backdated for batch `late_fee` scenario
  - CardB limit `$10,000` — clean
- **Purchases** (8× `purchase_requested` on `card-events`, keyed by `card_account_id`):
  - CardA 6 purchases `$45.00`–`$350.00` (mix 1 and 3 installments)
  - CardB 2 purchases `$100`/`$250`
  Flink `card-service` authorizes against the live limit and emits `purchase_approved` → `card_movements` consumer inserts rows.
- **Transfers** (2× `transfer_requested` on `account-events`): PRIMARY→SAVINGS `$200`, SAVINGS→PRIMARY `$50`
- **Deposit** (1× `deposit` on `account-events`): `$300` to PRIMARY
- **Backdating** (only direct DB tweak): after publishing, the seed waits ~8s for Flink, then polls up to 30s and `UPDATE card_movements.occurred_at/created_at` (+ `installments.due_date`) to ~45 days ago, so the batch `close_statement` sees a prior period and `run_due_date_check` can generate a `late_fee`. This preserves event-sourcing — the ledger events were the source; the timestamp tweak only makes the batch demo deterministic.

## Prerequisites

- Postgres + Kafka healthy, `db-migrate` completed (`alembic upgrade head`), Flink jobs running.
- `AUTH0_SEED_SUB` env (default `auth0|6a90f3247c7a4be23a0edc80`) or pass `--auth0-sub`.

## Run

### Automatic on `docker compose up`

`docker-compose.yml` adds a one-shot `seed` service (`restart: "no"`, `bash -c "sleep 10 && python -m openbankapi.seed.run --auth0-sub $AUTH0_SEED_SUB"`). It depends on `db-migrate`, `kafka-init`, `kafka` and `postgres` healthy, so it runs once per `up` and is idempotent — re-running `up` without `--reset` is a no-op.

```bash
docker compose up --build
docker compose logs seed   # verify
```

To disable auto-seed: comment out the `seed:` service. To require opt-in instead: add `profiles: ["seed", "demo"]` to that service and run `docker compose --profile seed up`.

### CLI

```bash
# Inside container
docker compose exec openbankapi python -m openbankapi.seed.run --auth0-sub auth0|6a90f3247c7a4be23a0edc80
docker compose exec openbankapi python -m openbankapi.seed.demo --auth0-sub ...  # alias

# Or via one-off seed container (works even if service is commented out)
docker compose run --rm seed python -m openbankapi.seed.run --auth0-sub auth0|6a90f3247c7a4be23a0edc80 --reset
docker compose run --rm seed python -m openbankapi.seed.run --auth0-sub ... --no-backdate
docker compose run --rm seed python -m openbankapi.seed.run --auth0-sub ... --skip-kafka --reset  # DB only, for tests

# Local (host) — needs DB/Kafka reachable
python -m openbankapi.seed.run --auth0-sub auth0|6a90f3247c7a4be23a0edc80 --reset
python -m openbankapi.seed.demo --auth0-sub auth0|6a90f3247c7a4be23a0edc80

# Legacy opening-balance seed still works (package migration preserves it)
python -m openbankapi.seed 1234567890123456=500000
```

**Flags:** `--auth0-sub` (required), `--reset` (delete+recreate), `--scenario demo` (only demo), `--no-backdate`, `--skip-kafka`.

## Idempotency

Check-before-create at each step. If a customer for the sub already has 2 `card_accounts`, the run skips all publishes. Use `--reset` to force a clean reseed (deletes card movements/installments/statements/cards/card_accounts/transactions/deposits/accounts before recreating the customer).

## Verification

```bash
# After Flink checkpoint (~5s)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/accounts
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/cards
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/transactions?account_number=..."
# Kafka UI: http://localhost:8080 — topics account-events, card-events, purchase-status

# Batch late_fee demo
docker compose exec batch-worker python -m openbankapi.batch.run_once
# Expect statements for CardA with late_fees_total = $35 when previous minimum unpaid
```

## Tradeoff: backdating

`CardMovementConsumer` inserts with `occurred_at = ts` from the event, where `ts` is `now` at publish time (see `card_movement_consumer.py:_insert_for`). There is no wire field to ask Flink to backdate — `ts` *is* `now` by contract. To make the batch close see a prior period without fabricating a second event stream, the seed publishes with real `now` (so Flink's flow stays pure-event) and then `UPDATE occurred_at` after the consumer has inserted. The alternative — publishing with a past `ts` and hoping Flink's `now` vs `ts` distinction doesn't matter — would still need an `UPDATE` because the consumer uses the event's `ts` verbatim for `occurred_at`.

## File map

- `openbankapi/seed/__init__.py` — re-exports legacy `main()` (`python -m openbankapi.seed 1234=500`)
- `openbankapi/seed/__main__.py` — enables `python -m openbankapi.seed` as package
- `openbankapi/seed/run.py` — demo CLI and orchestration
- `openbankapi/seed/demo.py` — alias for `seed.run`
- `openbankapi/seed/catalog.py` — purchase catalogue
- `openbankapi/seed/backdate.py` — backdate helper (only direct DB tweak)
