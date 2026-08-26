"""Cache-aside behaviour (spec §8.2)."""
from __future__ import annotations

from openbankapi.tests.conftest import build
from openbankapi.tests.fakes import FakeCache


def _make_location(h):
    return h.client.post("/locations", json={"name": "Montevideo"}).json()["id"]


def test_a_miss_populates_the_cache(harness):
    location_id = _make_location(harness)

    harness.client.get(f"/locations/{location_id}")

    assert f"location:{location_id}" in harness.cache.store


def test_a_hit_does_not_reach_the_repository(harness):
    location_id = _make_location(harness)
    harness.client.get(f"/locations/{location_id}")
    loads_after_first = harness.locations.loads

    harness.client.get(f"/locations/{location_id}")

    assert harness.locations.loads == loads_after_first


def test_a_write_invalidates_the_entry(harness):
    location_id = _make_location(harness)
    harness.client.get(f"/locations/{location_id}")

    harness.client.put(f"/locations/{location_id}", json={"name": "Salto"})

    assert f"location:{location_id}" not in harness.cache.store
    assert harness.client.get(f"/locations/{location_id}").json()["name"] == "Salto"


def test_a_failing_cache_degrades_to_a_miss_not_a_500():
    """A cache that can take the API down is not a cache."""
    h = build(cache=FakeCache(failing=True))
    with h.client:
        location_id = _make_location(h)
        response = h.client.get(f"/locations/{location_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Montevideo"


def test_a_404_is_not_cached(harness):
    import uuid

    missing = uuid.uuid4()
    assert harness.client.get(f"/locations/{missing}").status_code == 404
    assert f"location:{missing}" not in harness.cache.store
