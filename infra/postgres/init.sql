-- OpenBankAPI relational schema.
--
-- The spec (§3) names these tables and columns in Spanish; this project keeps
-- all code, including DDL, in English. The mapping is one-to-one:
--   locaciones -> locations   sucursales -> branches
--   clientes   -> customers   cuentas    -> accounts
--
-- This script is the ONLY thing that creates these tables. There is no Alembic
-- and no `Base.metadata.create_all` (spec §10): the ORM mappings in
-- `openbankapi/infra/database/models.py` describe tables they never own. Two
-- sources of DDL is how a schema and its mapping silently drift apart.
--
-- The official Postgres image replays /docker-entrypoint-initdb.d/* exactly
-- once, when the data volume is empty. Editing this file therefore does nothing
-- to a running stack -- `docker compose down -v` is what re-runs it.
--
-- Constraint names are deliberately left to Postgres's own defaults
-- (`<table>_<column>_key`, `<table>_<column>_fkey`, `<table>_<column>_check`).
-- `openbankapi/infra/database/errors.py` translates a violation by reading the
-- constraint name off the driver error, so a hand-picked name here would break
-- that mapping. Do not name these constraints.

-- gen_random_uuid() is built into Postgres 13+, so on the pinned postgres:16
-- image this line is a no-op. It stays because it costs nothing and keeps the
-- script correct if the image pin is ever moved backwards.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tables are created parent-first: `branches` references `locations`, and
-- `accounts` references both `customers` and `branches`.

-- §3.2 -- the geographic grouping a branch belongs to.
CREATE TABLE locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.3 -- a branch. `code` is the business key; the UUID is internal.
CREATE TABLE branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    location_id UUID NOT NULL REFERENCES locations(id),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.4 -- a customer. There is no `age` column on purpose: an age is computed
-- from `date_of_birth` at read time, because a stored one is wrong the day
-- after it is written. `date_of_birth` and `gender` are personal data and must
-- never reach an application log.
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identification_number VARCHAR(20) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.5 -- an account.
--
-- `account_number` is not just an identifier: it is the Kafka partition key
-- used by every topic in §4, with no mapping table in between. The CHECK is
-- what keeps that key well-formed at the storage layer, and CHAR(16) means
-- leading zeros survive -- `0000000000000001` and `1` are different shards.
--
-- `balance` is a read-model projection, never state this database owns. Flink's
-- keyed state is the source of truth; the only writer here is the
-- `account-balances` consumer (§3.6). No CRUD endpoint may write it.
CREATE TABLE accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_number CHAR(16) UNIQUE NOT NULL
        CHECK (account_number ~ '^[0-9]{16}$'),
    currency CHAR(3) NOT NULL,                   -- ISO 4217: USD, ARS, UYU...
    customer_id UUID NOT NULL REFERENCES customers(id),
    branch_id UUID NOT NULL REFERENCES branches(id),
    balance BIGINT NOT NULL DEFAULT 0,           -- cents. READ-ONLY. See above.
    status VARCHAR(20) NOT NULL DEFAULT 'active',-- active | blocked | closed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes.
--
-- The three business keys (`branches.code`, `customers.identification_number`,
-- `accounts.account_number`) already have unique indexes -- UNIQUE builds one --
-- so `GET /accounts/{account_number}`, the hottest single-row read in the
-- system, is covered without anything extra here.
--
-- What Postgres does NOT create automatically is an index on the referencing
-- side of a foreign key. Without these, listing a customer's accounts is a
-- sequential scan, and so is the FK re-check Postgres runs when a parent row is
-- updated.
CREATE INDEX idx_branches_location_id ON branches (location_id);
CREATE INDEX idx_accounts_customer_id ON accounts (customer_id);
CREATE INDEX idx_accounts_branch_id ON accounts (branch_id);

-- Every list endpoint pages with `ORDER BY created_at DESC, id DESC` -- the tie
-- break on `id` is what makes an offset page stable when two rows share a
-- timestamp. These indexes are that exact ordering, so a page is a range scan
-- rather than a sort of the whole table.
CREATE INDEX idx_locations_created_at ON locations (created_at DESC, id DESC);
CREATE INDEX idx_branches_created_at ON branches (created_at DESC, id DESC);
CREATE INDEX idx_customers_created_at ON customers (created_at DESC, id DESC);
CREATE INDEX idx_accounts_created_at ON accounts (created_at DESC, id DESC);

-- The fees account (§5's example value, and this project's FEES_ACCOUNT
-- default). Its row has to exist before any transfer, or the fee credit that
-- Flink emits has nowhere to land in the read model -- the balance-sync
-- consumer would update zero rows, forever. balance stays 0 here: this is the
-- account's *row*, not its balance. A balance only ever comes from
-- account-balances (§3.6).
INSERT INTO locations (id, name) VALUES ('00000000-0000-0000-0000-000000000001', 'SYSTEM');
INSERT INTO branches (id, code, name, location_id)
    VALUES ('00000000-0000-0000-0000-000000000001', 'SYS', 'System branch',
            '00000000-0000-0000-0000-000000000001');
INSERT INTO customers (id, identification_number, first_name, last_name, date_of_birth)
    VALUES ('00000000-0000-0000-0000-000000000001', 'SYSTEM', 'System', 'Account', DATE '1970-01-01');
INSERT INTO accounts (account_number, currency, customer_id, branch_id)
    VALUES ('0000000000000001', 'USD', '00000000-0000-0000-0000-000000000001',
            '00000000-0000-0000-0000-000000000001');
