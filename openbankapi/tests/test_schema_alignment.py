"""The ORM mapping must match init.sql exactly.

This exists because a rename pass renamed the ORM and the fakes consistently and
every unit test still passed — while the live schema disagreed. Fakes mirror
whatever the code says, so they cannot catch a mapping that drifted away from
the database. Parsing the real DDL is the only check that can.

`init.sql` is the source of truth: it is the only thing that creates these
tables (spec §10).
"""
from __future__ import annotations

import pathlib
import re

import pytest

from openbankapi.infra.database.models import (
    AccountORM,
    BranchORM,
    CustomerORM,
    LocationORM,
)

INIT_SQL = pathlib.Path(__file__).resolve().parents[2] / "infra" / "postgres" / "init.sql"

MODELS = [LocationORM, BranchORM, CustomerORM, AccountORM]


def _columns_in_sql(table: str) -> set[str]:
    body = re.search(
        rf"CREATE TABLE {table} \((.*?)\n\);", INIT_SQL.read_text(), re.S
    )
    assert body, f"no CREATE TABLE for {table}"
    columns = set()
    for line in body.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.upper().startswith(("CHECK", "CONSTRAINT")):
            continue
        name = line.split()[0]
        if name.isidentifier():
            columns.add(name)
    return columns


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__tablename__)
def test_the_orm_maps_exactly_the_columns_the_schema_declares(model):
    declared = _columns_in_sql(model.__tablename__)
    mapped = {c.name for c in model.__table__.columns}
    assert mapped == declared, (
        f"{model.__tablename__} drifted: "
        f"only in ORM {sorted(mapped - declared)}, only in SQL {sorted(declared - mapped)}"
    )


def test_every_table_the_schema_declares_has_a_mapping():
    tables = set(re.findall(r"CREATE TABLE (\w+)", INIT_SQL.read_text()))
    assert tables == {m.__tablename__ for m in MODELS}


def test_nothing_spanish_survives_in_the_schema():
    """The spec names these in Spanish; the code is English throughout."""
    ddl = INIT_SQL.read_text()
    # Skip the comment block that documents the spec -> English mapping.
    ddl = "\n".join(l for l in ddl.splitlines() if not l.strip().startswith("--"))
    for term in ["cuenta", "cliente", "sucursal", "locacion", "saldo",
                 "moneda", "nombre", "apellido", "genero", "codigo", "estado"]:
        assert term not in ddl.lower(), f"{term!r} still in the schema"
