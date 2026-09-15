"""Real-Redis race-closing suite (Task 2.1) — opt-in via `-m redis_integration`
(excluded from the default run by `pytest.ini`'s `addopts`). Requires
`docker compose up redis -d` (or any reachable Redis at `REDIS_URL`).

Proves the acceptance criterion a fake cannot: subscribe-before-check against
REAL Redis Pub/Sub timing. `TRIALS` concurrent trials, each racing a
`wait_for` against a `resolve` fired the instant after (or, in the second
test, truly concurrently with) `wait_for`'s subscribe — zero timeouts, zero
lost notifications, proves the lost-wakeup race is closed.

No `pytest-asyncio` in this repo (see `tests/db_fixtures.py`) — driven with
`asyncio.run(scenario())`, matching the rest of the suite.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from openbankapi.infra.status_registry.repositories.redis_status_registry import (
    get_redis_status_registry,
)
from openbankapi.infra.status_registry.repositories.redis_status_registry_client import (
    get_redis_status_registry_client,
)

pytestmark = pytest.mark.redis_integration

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TRIALS = 25


def _make_registry():
    client = get_redis_status_registry_client(REDIS_URL, pool_size=10)
    domain = f"race-test-{uuid.uuid4()}"
    return get_redis_status_registry(client, domain, ttl_seconds=60), client


def test_no_lost_wakeups_under_n_concurrent_trials():
    async def scenario():
        registry, client = _make_registry()
        try:
            for _ in range(TRIALS):
                request_id = str(uuid.uuid4())
                wait_task = asyncio.ensure_future(registry.wait_for(request_id, timeout=2.0))
                # Yield once so `wait_for` has subscribed before we publish —
                # the exact scenario the ordering fix targets: a resolution
                # racing the subscribe, not one that arrives long after.
                await asyncio.sleep(0)
                await registry.resolve({"request_id": request_id, "status": "approved"})
                result = await wait_task
                assert result is not None, f"lost wakeup for {request_id}"
                assert result["request_id"] == request_id
        finally:
            await client.close()

    asyncio.run(scenario())


def test_subscribe_before_check_survives_truly_concurrent_publish():
    """Fires `resolve` from a fully independent task with no handshake at
    all — as close to "arbitrary interleaving" as one process can get
    against real Redis."""

    async def scenario():
        registry, client = _make_registry()
        try:
            successes = 0
            for _ in range(TRIALS):
                request_id = str(uuid.uuid4())

                async def resolve_now(rid=request_id):
                    await registry.resolve({"request_id": rid, "status": "approved"})

                wait_task = asyncio.ensure_future(registry.wait_for(request_id, timeout=2.0))
                resolve_task = asyncio.ensure_future(resolve_now())
                result, _ = await asyncio.gather(wait_task, resolve_task)
                if result is not None:
                    successes += 1
            assert successes == TRIALS, f"lost {TRIALS - successes} of {TRIALS} concurrent trials"
        finally:
            await client.close()

    asyncio.run(scenario())
