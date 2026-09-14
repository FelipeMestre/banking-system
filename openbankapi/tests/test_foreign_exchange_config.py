"""RED for FX-1: ForeignExchangeConfig must be frozen dataclass with correct defaults."""

import pytest


def test_defaults_match_spec():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )

    cfg = ForeignExchangeConfig()
    assert cfg.base_url == "https://api.frankfurter.dev/v2/rates"
    assert cfg.tracked_currencies == ["EUR", "GBP"]
    assert cfg.request_timeout_seconds == 10.0


def test_is_frozen():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )

    cfg = ForeignExchangeConfig()
    with pytest.raises((AttributeError, TypeError)):
        cfg.base_url = "https://example.com"  # type: ignore[misc]


def test_custom_values_overrides_defaults():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )

    cfg = ForeignExchangeConfig(
        base_url="https://example.com/rates",
        tracked_currencies=["JPY"],
        request_timeout_seconds=5.0,
    )
    assert cfg.base_url == "https://example.com/rates"
    assert cfg.tracked_currencies == ["JPY"]
    assert cfg.request_timeout_seconds == 5.0


def test_tracked_currencies_default_is_not_shared_mutable():
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )

    a = ForeignExchangeConfig()
    b = ForeignExchangeConfig()
    # must not be same list object (default_factory isolation)
    assert a.tracked_currencies is not b.tracked_currencies


def test_no_redis_ttl_knowledge():
    """Config must not know about Redis or TTL — only its 3 fields."""
    from openbankapi.infra.foreign_exchange_service.config.foreign_exchange_config import (
        ForeignExchangeConfig,
    )

    cfg = ForeignExchangeConfig()
    assert not hasattr(cfg, "ttl")
    assert not hasattr(cfg, "redis_url")
    assert not hasattr(cfg, "cache_ttl")
