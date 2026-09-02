"""RED for FX-3: FrankfurterRepository via httpx."""

import asyncio
import json

import httpx
import pytest


def _make_transport(handler):
    return httpx.MockTransport(handler)


def test_array_parsed_skip_usd():
    """Frankfurter returns array with USD row — repo must skip USD and return EUR/GBP."""
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )

    payload = [
        {"date": "2026-09-01", "base": "USD", "quote": "USD", "rate": 1.0},
        {"date": "2026-09-01", "base": "USD", "quote": "EUR", "rate": 0.8613},
        {"date": "2026-09-01", "base": "USD", "quote": "GBP", "rate": 0.74},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        # spec params
        assert request.url.params["base"] == "USD"
        assert request.url.params["quotes"] == "EUR,GBP"
        return httpx.Response(200, json=payload)

    transport = _make_transport(handler)
    # We need to inject transport into the repository's internal AsyncClient.
    # The repo creates its own AsyncClient; tests patch httpx.AsyncClient to use MockTransport.
    from unittest.mock import patch

    config = ForeignExchangeConfig()

    original_async_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        result = asyncio.run(repo.get_all_mid_rates())

    assert result == {"EUR": 0.8613, "GBP": 0.74}


def test_empty_after_usd_filter_raises():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )
    from openbankapi.domain.exceptions import RateNotAvailableError
    from unittest.mock import patch

    payload: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = _make_transport(handler)
    config = ForeignExchangeConfig()

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        with pytest.raises(RateNotAvailableError):
            asyncio.run(repo.get_all_mid_rates())


def test_only_usd_returns_raises():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )
    from openbankapi.domain.exceptions import RateNotAvailableError
    from unittest.mock import patch

    payload = [{"date": "2026-09-01", "base": "USD", "quote": "USD", "rate": 1.0}]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = _make_transport(handler)
    config = ForeignExchangeConfig()

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        with pytest.raises(RateNotAvailableError):
            asyncio.run(repo.get_all_mid_rates())


def test_timeout_propagates():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )
    from unittest.mock import patch

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    transport = _make_transport(handler)
    config = ForeignExchangeConfig()

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        with pytest.raises(httpx.ConnectTimeout):
            asyncio.run(repo.get_all_mid_rates())


def test_http_5xx_propagates_via_raise_for_status():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )
    from unittest.mock import patch

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    transport = _make_transport(handler)
    config = ForeignExchangeConfig()

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(repo.get_all_mid_rates())


def test_uses_config_timeout():
    """Repo must pass config.request_timeout_seconds to AsyncClient."""
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )
    from openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository import (
        FrankfurterRepository,
    )
    from unittest.mock import patch

    captured = {}

    payload = [
        {"quote": "EUR", "rate": 0.9},
        {"quote": "GBP", "rate": 0.8},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = _make_transport(handler)
    config = ForeignExchangeConfig(request_timeout_seconds=7.5)

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    with patch("openbankapi.infra.foreign_exchange_service.repository.frankfurter_repository.httpx.AsyncClient", PatchedAsyncClient):
        repo = FrankfurterRepository(config)
        result = asyncio.run(repo.get_all_mid_rates())

    assert captured["timeout"] == 7.5
    assert result == {"EUR": 0.9, "GBP": 0.8}


def test_no_redis_import():
    from pathlib import Path

    src = Path("openbankapi/infra/foreign_exchange_service/repository/frankfurter_repository.py").read_text().lower()
    assert "import redis" not in src
    assert "from redis" not in src
    # should not import cache service
    assert "icacheservice" not in src
    assert "cache_service" not in src


def test_uses_httpx_async_client():
    from pathlib import Path

    src = Path("openbankapi/infra/foreign_exchange_service/repository/frankfurter_repository.py").read_text()
    assert "httpx.AsyncClient" in src
    assert "requests" not in src.lower()
