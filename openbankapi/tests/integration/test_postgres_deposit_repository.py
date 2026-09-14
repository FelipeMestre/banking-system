"""RED for Task 1.3 / 1.5 — deposits contract + repo idempotency."""
from __future__ import annotations

import uuid


def test_deposits_table_exists():
    from openbankapi.infra.database.schemas.models import DepositORM

    assert DepositORM.__tablename__ == "deposits"
    cols = {c.key for c in DepositORM.__table__.columns}
    assert "movement_id" in cols
    assert "admin_id" in cols
    assert "reason" in cols
    # PK is gen_random_uuid
    assert DepositORM.__table__.c.id.server_default is not None
    # movement_id unique constraint / FK
    # check FK exists
    fks = [str(fk.target_fullname) for fk in DepositORM.__table__.foreign_keys]
    assert "transactions.id" in fks or any("transactions" in fk for fk in fks)
    # unique on movement_id
    uniques = []
    for c in DepositORM.__table__.constraints:
        if hasattr(c, "columns"):
            uniques.append({col.key for col in c.columns})
    # movement_id should be unique (either UniqueConstraint or unique=True)
    assert DepositORM.__table__.c.movement_id.unique is True or any(
        "movement_id" in s for s in uniques
    )


def test_deposits_fk_no_audit_cols_on_transactions():
    from openbankapi.infra.database.schemas.models import TransactionORM

    cols = {c.key for c in TransactionORM.__table__.columns}
    assert "admin_id" not in cols
    assert "reason" not in cols


def test_deposit_repository_insert_idempotent():
    """Repository insert is ON CONFLICT DO NOTHING on movement_id."""
    import asyncio

    from openbankapi.infra.database.interfaces.deposit_repository import IDepositRepository
    from openbankapi.infra.database.repositories.postgres_deposit_repository import (
        PostgresDepositRepository,
    )
    from unittest.mock import AsyncMock, MagicMock

    async def scenario():
        fake_session = AsyncMock()
        # capture executed statement
        executed = []

        async def fake_execute(stmt):
            executed.append(stmt)
            # simulate compiled SQL contains ON CONFLICT
            return MagicMock()

        fake_session.execute = fake_execute
        fake_session.flush = AsyncMock()

        repo = PostgresDepositRepository(fake_session)  # type: ignore[arg-type]
        mid = uuid.uuid4()
        await repo.insert(movement_id=mid, admin_id="admin-42", reason="cash branch 42")
        await repo.insert(movement_id=mid, admin_id="admin-42", reason="cash branch 42")
        assert len(executed) == 2
        # both statements should have ON CONFLICT clause
        sqls = [str(s.compile(compile_kwargs={"literal_binds": True})) for s in executed]
        for sql in sqls:
            assert "ON CONFLICT" in sql.upper()
            assert "movement_id" in sql

        # also check interface exists
        assert hasattr(IDepositRepository, "insert")

    asyncio.run(scenario())


def test_deposit_repository_on_conflict_movement_id():
    import inspect

    from openbankapi.infra.database.repositories.postgres_deposit_repository import (
        PostgresDepositRepository,
    )

    src = inspect.getsource(PostgresDepositRepository.insert)
    assert "on_conflict_do_nothing" in src
    assert "movement_id" in src
