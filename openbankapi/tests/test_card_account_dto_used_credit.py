"""RED for card-accounts used_credit DTO and projection port (Phase 2)."""
from __future__ import annotations

import uuid

import pytest
from pydantic import BaseModel

from openbankapi.api.v1.dtos.card_account_dto import CardAccountResponseDTO
from openbankapi.domain.model import CardAccount, CardAccountStatus
from openbankapi.infra.database.interfaces.card_account_repository import ICardAccountRepository
from openbankapi.infra.database.repositories.postgres_card_account_repository import PostgresCardAccountRepository


def test_dto_has_used_credit_raw_int_no_ge0():
    data = {
        "id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "paying_account_id": uuid.uuid4(),
        "credit_limit": "1000.00",
        "status": "active",
        "used_credit": -5000,
    }
    dto = CardAccountResponseDTO.model_validate(data)
    assert dto.used_credit == -5000
    # ensure no ge=0 validation clamps negative
    negative = CardAccountResponseDTO.model_validate({**data, "used_credit": -10000})
    assert negative.used_credit == -10000


def test_dto_from_attributes_true():
    assert CardAccountResponseDTO.model_config.get("from_attributes") is True


def test_dto_all_five_returns_surface_used_credit():
    """POST /card-accounts, GET /{id}, GET list, PUT /{id}, POST /{id}/status must all surface used_credit.
    This is checked via model_validate on a CardAccount domain object (the repository's _to_domain output).
    """
    account = CardAccount(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        paying_account_id=uuid.uuid4(),
        credit_limit=1000,
        status=CardAccountStatus.ACTIVE,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        used_credit=30000,
    )
    dto = CardAccountResponseDTO.model_validate(account)
    assert dto.used_credit == 30000


def test_get_cards_not_expose_used_credit():
    """GET /cards must not expose used_credit — check Card DTOs lack it."""
    from openbankapi.api.v1.dtos.card_dto import CardIssuedDTO, CardMaskedDTO

    for dto_cls in (CardIssuedDTO, CardMaskedDTO):
        assert "used_credit" not in dto_cls.model_fields, f"{dto_cls.__name__} must not have used_credit"


def test_icard_balance_projection_exists():
    from openbankapi.infra.database.interfaces.card_account_repository import ICardBalanceProjection

    assert hasattr(ICardBalanceProjection, "apply_used_credit")
    # check protocol signature: should be async and return bool
    import inspect

    sig = inspect.signature(ICardBalanceProjection.apply_used_credit)
    params = list(sig.parameters.keys())
    assert "card_account_id" in params
    assert "used_credit" in params


def test_icard_account_repository_has_no_writer_and_updatable_excludes_used_credit():
    # ICardAccountRepository must not expose used_credit writer
    assert not hasattr(ICardAccountRepository, "apply_used_credit")
    assert not hasattr(ICardAccountRepository, "update_used_credit")
    # PostgresCardAccountRepository._UPDATABLE must exclude used_credit
    updatable = getattr(PostgresCardAccountRepository, "_UPDATABLE", None)
    assert updatable is not None, "_UPDATABLE must be defined"
    assert "used_credit" not in updatable


def test_fake_mirrors_used_credit_and_apply():
    from openbankapi.tests.fakes import FakeCardAccountRepository

    repo = FakeCardAccountRepository()
    assert hasattr(repo, "apply_used_credit"), "Fake must mirror apply_used_credit"
    # check fake can store used_credit
    import asyncio

    async def scenario():
        customer_id = uuid.uuid4()
        paying_account_id = uuid.uuid4()
        repo.known_customers.add(customer_id)
        repo.known_accounts.add(paying_account_id)
        account = await repo.create(customer_id=customer_id, paying_account_id=paying_account_id, credit_limit=1000)
        assert account.used_credit == 0
        result = await repo.apply_used_credit(account.id, 30000)
        assert result is True
        fetched = await repo.get_by_id(account.id)
        assert fetched.used_credit == 30000
        # unknown id returns False
        unknown = await repo.apply_used_credit(uuid.uuid4(), 5000)
        assert unknown is False
        # negative allowed
        await repo.apply_used_credit(account.id, -5000)
        fetched2 = await repo.get_by_id(account.id)
        assert fetched2.used_credit == -5000

    asyncio.run(scenario())
