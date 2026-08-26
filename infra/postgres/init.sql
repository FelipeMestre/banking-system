-- OpenBankAPI relational schema (spec §3).
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

-- Tables are created parent-first: `sucursales` references `locaciones`, and
-- `cuentas` references both `clientes` and `sucursales`.

-- §3.2 -- the geographic grouping a branch belongs to.
CREATE TABLE locaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(150) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.3 -- a branch. `codigo` is the business key; the UUID is internal.
CREATE TABLE sucursales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(10) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    locacion_id UUID NOT NULL REFERENCES locaciones(id),
    activa BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.4 -- a customer. There is no `age` column on purpose: an age is computed
-- from `fecha_nacimiento` at read time, because a stored one is wrong the day
-- after it is written. `fecha_nacimiento` and `genero` are personal data and
-- must never reach an application log.
CREATE TABLE clientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_identificacion VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    genero VARCHAR(20),
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- §3.5 -- an account.
--
-- `numero_cuenta` is not just an identifier: it is the Kafka partition key used
-- by every topic in §4, with no mapping table in between. The CHECK is what
-- keeps that key well-formed at the storage layer, and CHAR(16) means leading
-- zeros survive -- `0000000000000001` and `1` are different shards.
--
-- `saldo` is a read-model projection, never state this database owns. Flink's
-- keyed state is the source of truth; the only writer here is the
-- `account-balances` consumer (§3.6). No CRUD endpoint may write it.
CREATE TABLE cuentas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_cuenta CHAR(16) UNIQUE NOT NULL
        CHECK (numero_cuenta ~ '^[0-9]{16}$'),
    moneda CHAR(3) NOT NULL,                     -- ISO 4217: USD, ARS, UYU...
    cliente_id UUID NOT NULL REFERENCES clientes(id),
    sucursal_id UUID NOT NULL REFERENCES sucursales(id),
    saldo BIGINT NOT NULL DEFAULT 0,             -- cents. READ-ONLY. See above.
    estado VARCHAR(20) NOT NULL DEFAULT 'activa',-- activa | bloqueada | cerrada
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes.
--
-- The three business keys (`sucursales.codigo`, `clientes.numero_identificacion`,
-- `cuentas.numero_cuenta`) already have unique indexes -- UNIQUE builds one --
-- so `GET /cuentas/{numero_cuenta}`, the hottest single-row read in the system,
-- is covered without anything extra here.
--
-- What Postgres does NOT create automatically is an index on the referencing
-- side of a foreign key. Without these, listing a customer's accounts is a
-- sequential scan, and so is the FK re-check Postgres runs when a parent row is
-- updated.
CREATE INDEX idx_sucursales_locacion_id ON sucursales (locacion_id);
CREATE INDEX idx_cuentas_cliente_id ON cuentas (cliente_id);
CREATE INDEX idx_cuentas_sucursal_id ON cuentas (sucursal_id);

-- Every list endpoint pages with `ORDER BY created_at DESC, id DESC` -- the tie
-- break on `id` is what makes an offset page stable when two rows share a
-- timestamp. These indexes are that exact ordering, so a page is a range scan
-- rather than a sort of the whole table.
CREATE INDEX idx_locaciones_created_at ON locaciones (created_at DESC, id DESC);
CREATE INDEX idx_sucursales_created_at ON sucursales (created_at DESC, id DESC);
CREATE INDEX idx_clientes_created_at ON clientes (created_at DESC, id DESC);
CREATE INDEX idx_cuentas_created_at ON cuentas (created_at DESC, id DESC);

-- The fees account (§5's example value, and this project's FEES_ACCOUNT
-- default). Its row has to exist before any transfer, or the fee credit that
-- Flink emits has nowhere to land in the read model -- the balance-sync
-- consumer would update zero rows, forever. saldo stays 0 here: this is the
-- account's *row*, not its balance. A balance only ever comes from
-- account-balances (§3.6).
INSERT INTO locaciones (id, nombre) VALUES ('00000000-0000-0000-0000-000000000001', 'SYSTEM');
INSERT INTO sucursales (id, codigo, nombre, locacion_id)
    VALUES ('00000000-0000-0000-0000-000000000001', 'SYS', 'System branch',
            '00000000-0000-0000-0000-000000000001');
INSERT INTO clientes (id, numero_identificacion, nombre, apellido, fecha_nacimiento)
    VALUES ('00000000-0000-0000-0000-000000000001', 'SYSTEM', 'System', 'Account', DATE '1970-01-01');
INSERT INTO cuentas (numero_cuenta, moneda, cliente_id, sucursal_id)
    VALUES ('0000000000000001', 'USD', '00000000-0000-0000-0000-000000000001',
            '00000000-0000-0000-0000-000000000001');
