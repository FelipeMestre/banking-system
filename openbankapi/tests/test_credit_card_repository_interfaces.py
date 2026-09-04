"""RED for Credit Cards Phase 1: repository ports as `Protocol`s (T9).

`typing.Protocol`, not `abc.ABC` — matches this codebase's real convention
(`IAccountRepository`, `IAppliedRateRepository`), confirmed via
`applied_rate_repository.py`'s own docstring precedent.
"""
from __future__ import annotations

import inspect
from typing import Protocol, runtime_checkable

from openbankapi.infra.database.interfaces.card_account_repository import (
    ICardAccountRepository,
)
from openbankapi.infra.database.interfaces.card_repository import ICardRepository


def test_card_account_repository_is_a_runtime_checkable_protocol():
    assert issubclass(ICardAccountRepository, Protocol)
    assert getattr(ICardAccountRepository, "_is_runtime_protocol", False) is True


def test_card_repository_is_a_runtime_checkable_protocol():
    assert issubclass(ICardRepository, Protocol)
    assert getattr(ICardRepository, "_is_runtime_protocol", False) is True


def test_card_account_repository_has_expected_methods():
    methods = {"create", "get_by_id", "list_by_customer", "update_status", "update_limit"}
    for name in methods:
        assert hasattr(ICardAccountRepository, name), f"missing {name}"
        assert inspect.iscoroutinefunction(getattr(ICardAccountRepository, name))


def test_card_repository_has_expected_methods():
    methods = {"create", "get_by_number", "get_active_for_account", "mark_replaced", "update_status"}
    for name in methods:
        assert hasattr(ICardRepository, name), f"missing {name}"
        assert inspect.iscoroutinefunction(getattr(ICardRepository, name))


def test_a_conforming_object_satisfies_the_protocol_at_runtime():
    class _Impl:
        async def create(self, **kwargs):
            ...

        async def get_by_id(self, card_account_id):
            ...

        async def list_by_customer(self, customer_id, *, limit, offset):
            ...

        async def update_status(self, card_account_id, *, status):
            ...

        async def update_limit(self, card_account_id, *, credit_limit):
            ...

    assert isinstance(_Impl(), ICardAccountRepository)
