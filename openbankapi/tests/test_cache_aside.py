"""Cache-aside behaviour (spec §8.2)."""
from __future__ import annotations

from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeCache

_CUSTOMER_BODY = {
    "identification_number": "ID-CACHE-1",
    "first_name": "Monte",
    "last_name": "Video",
    "date_of_birth": "1990-01-01",
}


def _make_customer(h, identification_number: str = "ID-CACHE-1"):
    body = dict(_CUSTOMER_BODY, identification_number=identification_number)
    return h.client.post("/customers", json=body).json()["id"]


def test_a_miss_populates_the_cache(harness):
    customer_id = _make_customer(harness)

    harness.client.get(f"/customers/{customer_id}")

    assert f"customer:{customer_id}" in harness.cache.store


def test_a_hit_does_not_reach_the_repository(harness):
    customer_id = _make_customer(harness)
    harness.client.get(f"/customers/{customer_id}")
    loads_after_first = harness.customers.loads

    harness.client.get(f"/customers/{customer_id}")

    assert harness.customers.loads == loads_after_first


def test_a_write_invalidates_the_entry(harness):
    customer_id = _make_customer(harness)
    harness.client.get(f"/customers/{customer_id}")

    harness.client.put(
        f"/customers/{customer_id}",
        json={"first_name": "Salto", "last_name": "Video", "date_of_birth": "1990-01-01"},
    )

    assert f"customer:{customer_id}" not in harness.cache.store
    assert harness.client.get(f"/customers/{customer_id}").json()["first_name"] == "Salto"


def test_a_failing_cache_degrades_to_a_miss_not_a_500():
    """A cache that can take the API down is not a cache."""
    h = build(cache=FakeCache(failing=True))
    with h.client:
        customer_id = _make_customer(h)
        response = h.client.get(f"/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json()["first_name"] == "Monte"


def test_a_404_is_not_cached(harness):
    import uuid

    missing = uuid.uuid4()
    assert harness.client.get(f"/customers/{missing}").status_code == 404
    assert f"customer:{missing}" not in harness.cache.store
