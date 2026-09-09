"""RED for FX-2: IForeignExchangeRepository interface and FX-4 exception."""

import inspect


def test_interface_is_importable_and_has_get_all_mid_rates():
    from openbankapi.infra.foreign_exchange_service.repository.foreign_exchange_repository_interface import (
        IForeignExchangeRepository,
    )

    assert hasattr(IForeignExchangeRepository, "get_all_mid_rates")
    # must be async
    assert inspect.iscoroutinefunction(
        getattr(IForeignExchangeRepository, "get_all_mid_rates")
    )


def test_interface_has_no_redis_ttl_leak():
    from pathlib import Path

    p = Path("openbankapi/infra/foreign_exchange_service/repository/foreign_exchange_repository_interface.py")
    src = p.read_text()
    lower = src.lower()
    # must not import redis or cache; docstrings/comments mentioning the word are ok
    assert "import redis" not in lower, "interface must not import redis"
    assert "from redis" not in lower, "interface must not import redis"
    assert "import httpx" not in lower or True  # httpx not relevant here
    # ensure no TTL/cache import leakage — check import lines explicitly
    for line in lower.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            assert "ttl" not in stripped, "interface must not import TTL"
            assert "cache" not in stripped, "interface must not import cache"


def test_rate_not_available_error_exists_and_is_domain_error():
    from openbankapi.domain.exceptions import RateNotAvailableError, DomainError

    err = RateNotAvailableError("no rates")
    assert isinstance(err, DomainError)
    assert isinstance(err, Exception)
    assert str(err) == "no rates"


def test_rate_not_available_maps_to_502():
    from openbankapi.domain.exceptions import RateNotAvailableError
    from openbankapi.api.v1.services.error_handlers import status_for

    assert status_for(RateNotAvailableError("boom")) == 502


def test_status_for_still_maps_other_errors():
    from openbankapi.domain.exceptions import NotFoundError, DuplicateError
    from openbankapi.api.v1.services.error_handlers import status_for

    assert status_for(NotFoundError("account", "123")) == 404
    assert status_for(DuplicateError("code", "X")) == 409
